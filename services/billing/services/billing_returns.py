'''
    Returns of an invoiced sale: the Nota de Crédito-Débito.

    The order is the one the invoice follows, for the same reason: nothing
    moves until the SIN has accepted the document. Everything that can refuse
    the return —a cancelled sale, an invoice the SIN does not hold, more units
    than were sold, a deadline passed, a drawer without the cash— refuses it
    before the tax office is asked. Once the SIN accepts, the return is undone
    in full: the units go back to the batches they left, last taken first, and
    the money goes back by the means the buyer paid with; the cash part leaves
    the till of whoever gives it back.

    A note can be cancelled at the SIN until the ninth of the next month, as
    an invoice can; that undoes the return the other way round.

    The note lives inside its sale (`credit_notes`), next to the invoice it
    adjusts: a sale has few returns and is always read whole.
'''
import gzip
from dataclasses import dataclass
from datetime import date
from typing import Any, Final

from boto3.resources.base import ServiceResource

from models.billing import SALES_TABLE
from schemas.billing import (
    BillingError,
    Buyer,
    CufInput,
    InvoiceLine,
    Payment,
    PaymentMethod,
    SaleAllocation,
    SaleLineOut,
    SaleStatus
)
from schemas.billing_cash import ExpenseIn, ExpenseType
from schemas.billing_returns import (
    INVOICE_TYPE_ADJUSTMENT,
    SECTOR_DOCUMENT_CREDIT_DEBIT,
    CreditNoteCancellation,
    CreditNoteDocument,
    CreditNoteIssuer,
    CreditNoteLineOut,
    CreditNoteOut,
    CreditNoteRef,
    CreditNotesResponse,
    ReturnError,
    SaleReturn
)
from schemas.billing_siat import InvoiceQrOut, InvoiceState, SaleInvoice, SiatCatalog, SiatCodesOut
from services import billing_siat_client as siat_client
from services.billing import (
    get_settings,
    new_id,
    now_iso,
    products_by_sku,
    take_counter,
    write_item
)
from services.billing_cash import (
    expected_cash,
    require_sale_session,
    require_till_open,
    void_movement,
    write_movement
)
from services.billing_credit_note_xml import as_sold_line, build_credit_note_xml
from services.billing_invoicing import _qr_url, cancellation_deadline, invoice_lines, qr_svg
from services.billing_mail import CreditNoteMail, send_credit_note, send_credit_note_cancellation
from services.billing_sales import _read_sale, _sale_out
from services.billing_siat import build_cuf, siat_stamp
from services.billing_siat_client import Emitter, InvoiceCancellation, InvoiceSubmission
from services.billing_siat_codes import current_codes, emitter_for, get_catalog
from services.billing_stock import draw_down, give_back
from services.exceptions import InvalidInputError, RegisterNotFoundError, ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

MONEY_DECIMALS = 2

# montoEfectivoCreditoDebito: the VAT rate the norm fixes, applied to what is
# returned (`docs/siat/SIAT.md`, «Nota de Crédito-Débito»).
VAT_RATE: Final[float] = 0.13

# A note past eighteen months from its invoice is not admitted (RND
# 102100000011, art. 36).
RETURN_DEADLINE_MONTHS: Final[int] = 18

# The note's number is its own sequence, apart from the invoices', and one per
# branch and point of sale like theirs.
CREDIT_NOTE_COUNTER_PREFIX = 'counter#credit_note#'


def return_deadline(issued_at: str) -> date:
    '''
        The last day a note can adjust an invoice.

        Args:
            issued_at (str): The invoice's fechaEmision.

        Returns:
            date: The same day, eighteen months later (the last day of that
                month when it is shorter).
    '''
    issued = date.fromisoformat(issued_at[:10])
    months = issued.month - 1 + RETURN_DEADLINE_MONTHS
    year, month = issued.year + months // 12, months % 12 + 1
    following = date(year + month // 12, month % 12 + 1, 1)
    return date(year, month, min(issued.day, (following - date(year, month, 1)).days))


def _returned_so_far(stored: dict[str, Any]) -> dict[str, list[SaleAllocation]]:
    '''
        The units already returned, per SKU, by the notes the SIN holds.

        Args:
            stored (dict[str, Any]): The sale as stored.

        Returns:
            dict[str, list[SaleAllocation]]: Allocations returned per SKU.
    '''
    returned: dict[str, list[SaleAllocation]] = {}
    for note in stored.get('credit_notes') or []:
        if note['state'] != InvoiceState.ACCEPTED.value:
            continue
        for line in note['lines']:
            returned.setdefault(line['sku'], []).extend(
                SaleAllocation(**allocation) for allocation in line['allocations'])
    return returned


def _take_back(
    line: SaleLineOut,
    returned: list[SaleAllocation],
    quantity: float
) -> list[SaleAllocation]:
    '''
        The allocations a returned quantity goes back to: the last batches the
        line took, minus what earlier returns already gave back.

        Args:
            line (SaleLineOut): The sold line.
            returned (list[SaleAllocation]): What earlier notes returned of it.
            quantity (float): Units returned now.

        Returns:
            list[SaleAllocation]: Units per batch, each with its own price.

        Raises:
            InvalidInputError: More units than are left to return.
    '''
    given: dict[str, float] = {}
    for allocation in returned:
        given[allocation.lot_id] = given.get(allocation.lot_id, 0) + allocation.quantity

    taken: list[SaleAllocation] = []
    pending = quantity
    for allocation in reversed(line.allocations):
        # A line takes each batch once, so what was given back of a batch is
        # what was given back of this allocation.
        units = min(max(allocation.quantity - given.get(allocation.lot_id, 0), 0), pending)
        if units <= 0:
            continue
        pending -= units
        taken.append(allocation.model_copy(update = {
            'quantity': units,
            'amount': round(units * allocation.unit_price, MONEY_DECIMALS)
        }))
        if pending <= 0:
            break
    if pending > 0:
        raise InvalidInputError(detail = ReturnError.RETURN_EXCEEDS_SOLD.value)
    return taken


def _returned_lines(
    stored: dict[str, Any],
    request: SaleReturn
) -> list[CreditNoteLineOut]:
    '''
        What comes back, line by line, with its share of each line discount.

        Args:
            stored (dict[str, Any]): The sale as stored.
            request (SaleReturn): What the buyer gives back.

        Returns:
            list[CreditNoteLineOut]: The returned lines.

        Raises:
            InvalidInputError: A SKU the sale did not sell, or more units of it
                than are left to return.
    '''
    sold = {line['sku']: SaleLineOut(**line) for line in stored['lines']}
    returned = _returned_so_far(stored)
    lines: list[CreditNoteLineOut] = []
    for wanted in request.body.lines:
        line = sold.get(wanted.sku)
        if line is None:
            raise InvalidInputError(detail = ReturnError.SKU_NOT_IN_SALE.value)
        allocations = _take_back(line, returned.get(wanted.sku, []), wanted.quantity)
        # A SKU repeated in one return counts what its earlier line took.
        returned.setdefault(wanted.sku, []).extend(allocations)
        amount = round(sum(allocation.amount for allocation in allocations), MONEY_DECIMALS)
        discount = round(line.discount * wanted.quantity / line.quantity, MONEY_DECIMALS)
        lines.append(CreditNoteLineOut(
            sku = line.sku, description = line.description, quantity = wanted.quantity,
            discount = discount, total = round(amount - discount, MONEY_DECIMALS),
            allocations = allocations
        ))
    return lines


def net_of_returns(stored: dict[str, Any]) -> dict[str, Any] | None:
    '''
        A sale as if what came back had never been sold: what the buyer kept.

        The sale itself is never edited —its invoice is the legal record—, so
        whoever counts sales (the dashboard) counts this instead. Only the
        notes the SIN holds count; a cancelled one gave everything back.

        Args:
            stored (dict[str, Any]): The sale as stored.

        Returns:
            dict[str, Any] | None: A copy with lines, totals and payments
                reduced; None when everything came back.
    '''
    notes = [note for note in stored.get('credit_notes') or []
             if note['state'] == InvoiceState.ACCEPTED.value]
    if not notes:
        return stored
    back: dict[str, dict[str, float]] = {}
    for note in notes:
        for line in note['lines']:
            row = back.setdefault(line['sku'], {'quantity': 0.0, 'discount': 0.0,
                                                'total': 0.0, 'cost': 0.0})
            row['quantity'] += line['quantity']
            row['discount'] += line['discount']
            row['total'] += line['total']
            row['cost'] += sum(allocation['quantity'] * allocation['unit_cost']
                               for allocation in line['allocations'])
    kept = []
    for line in stored['lines']:
        row = back.get(line['sku'], {'quantity': 0.0, 'discount': 0.0, 'total': 0.0, 'cost': 0.0})
        if line['quantity'] - row['quantity'] <= 0:
            continue
        kept.append({**line, **{key: round(line[key] - row[key], MONEY_DECIMALS)
                                for key in ('quantity', 'discount', 'total', 'cost')},
                     'subtotal': round(line['subtotal'] - row['total'] - row['discount'],
                                       MONEY_DECIMALS)})
    if not kept:
        return None
    refunded: dict[str, float] = {}
    for note in notes:
        for refund in note['refunds']:
            refunded[refund['method']] = refunded.get(refund['method'], 0) + refund['amount']
    parts = stored.get('payments') or [{'method': stored['payment_method'],
                                        'amount': stored['total']}]
    payments = [{**part, 'amount': round(part['amount'] - refunded.pop(part['method'], 0),
                                         MONEY_DECIMALS)} for part in parts]
    return {**stored, 'lines': kept,
            'payments': [part for part in payments if part['amount'] > 0],
            **{key: round(sum(line[key] for line in kept), MONEY_DECIMALS)
               for key in ('subtotal', 'discount', 'total', 'cost')}}


def _refunds(
    stored: dict[str, Any],
    amount: float
) -> list[Payment]:
    '''
        What goes back by each means the buyer paid with, in proportion to
        what each paid; the last means takes the rounding.

        Args:
            stored (dict[str, Any]): The sale as stored.
            amount (float): What is returned.

        Returns:
            list[Payment]: One refund per means with something to give back.
    '''
    parts = stored.get('payments') or [{'method': stored['payment_method'],
                                        'amount': stored['total']}]
    refunds: list[Payment] = []
    left = amount
    for index, part in enumerate(parts):
        share = (round(left, MONEY_DECIMALS) if index == len(parts) - 1
                 else round(amount * part['amount'] / stored['total'], MONEY_DECIMALS))
        left -= share
        if share > 0:
            refunds.append(Payment(method = part['method'], amount = share))
    return refunds


def _invoice_details(
    lines: list[SaleLineOut],
    products: dict[str, dict[str, Any]]
) -> list[InvoiceLine]:
    '''
        Lines as the SIN reads them, one per price, as the invoice carried them.

        Args:
            lines (list[SaleLineOut]): Sold or returned lines.
            products (dict[str, dict[str, Any]]): The catalogue, with SIN codes.

        Returns:
            list[InvoiceLine]: The details.
    '''
    return [detail for line in lines
            for detail in invoice_lines(line, products.get(line.sku, {}))]


def _check_returnable(stored: dict[str, Any] | None) -> SaleInvoice:
    '''
        The invoice a return adjusts, or why the sale cannot be returned.

        Args:
            stored (dict[str, Any] | None): The sale as stored.

        Returns:
            SaleInvoice: Its invoice.

        Raises:
            RegisterNotFoundError: No such sale in this shop.
            InvalidInputError: Cancelled, never invoiced, an invoice the SIN
                does not hold as accepted, or eighteen months past it.
    '''
    if stored is None:
        raise RegisterNotFoundError(detail = BillingError.SALE_NOT_FOUND.value)
    if stored['status'] != SaleStatus.ISSUED.value:
        raise InvalidInputError(detail = ReturnError.SALE_CANCELLED.value)
    if not stored.get('invoice'):
        raise InvalidInputError(detail = BillingError.SALE_NOT_INVOICED.value)
    invoice = SaleInvoice(**stored['invoice'])
    if invoice.state != InvoiceState.ACCEPTED:
        raise InvalidInputError(detail = ReturnError.INVOICE_NOT_ACCEPTED.value)
    if get_current_time_gmt().date() > return_deadline(invoice.issued_at):
        raise InvalidInputError(detail = ReturnError.RETURN_DEADLINE_PASSED.value)
    return invoice


@dataclass(frozen = True)
class _Stamp:
    '''
        What makes one note unique before the SIN: who issues it, with which
        codes, its number and its CUF, and the moment both carry.
    '''
    emitter: Emitter
    codes: SiatCodesOut
    number: int
    cuf: str
    issued_at: str


@dataclass(frozen = True)
class _IssuedNote:
    '''
        A note the SIN accepted: what identifies it, its XML and the answer.
    '''
    stamp: _Stamp
    xml: str
    reception_code: str | None
    siat_state: str | None


def _stamp_note(
    dynamodb_resource: ServiceResource,
    owner: str
) -> _Stamp:
    '''
        Takes the next note number and builds its CUF with the codes in force.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.

        Returns:
            _Stamp: The note's identity.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable: a note is only
                issued online.
    '''
    codes = current_codes(dynamodb_resource, owner)
    emitter = emitter_for(dynamodb_resource, owner)
    number = take_counter(dynamodb_resource, owner, f'{CREDIT_NOTE_COUNTER_PREFIX}'
                          f'{emitter.branch}#{emitter.point_of_sale or 0}')
    now = get_current_time_gmt()
    # The CUF carries milliseconds and the XML the same moment: cut once.
    moment = now.replace(microsecond = now.microsecond // 1000 * 1000)
    cuf = build_cuf(CufInput(nit = emitter.nit, issued_at = moment, invoice_number = number,
                             branch = emitter.branch, point_of_sale = emitter.point_of_sale or 0,
                             invoice_type = INVOICE_TYPE_ADJUSTMENT,
                             sector_document = SECTOR_DOCUMENT_CREDIT_DEBIT),
                    codes.control_code)
    return _Stamp(emitter = emitter, codes = codes, number = number, cuf = cuf,
                  issued_at = siat_stamp(moment))


def _issue_note(
    dynamodb_resource: ServiceResource,
    owner: str,
    stored: dict[str, Any],
    returned: list[CreditNoteLineOut],
    returned_by: str
) -> _IssuedNote:
    '''
        Builds the note's XML and hands it to the SIN.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            stored (dict[str, Any]): The sale as stored, with its invoice.
            returned (list[CreditNoteLineOut]): What comes back.
            returned_by (str): Who issues it.

        Returns:
            _IssuedNote: The note, accepted.

        Raises:
            InvalidInputError: A product not homologated, or SIAT_REFUSED.
            ServiceUnavailableError: The SIAT is unreachable.
    '''
    invoice = SaleInvoice(**stored['invoice'])
    products = products_by_sku(dynamodb_resource, owner)
    settings = get_settings(dynamodb_resource, owner)
    stamp = _stamp_note(dynamodb_resource, owner)
    amount = round(sum(line.total for line in returned), MONEY_DECIMALS)
    xml = build_credit_note_xml(
        CreditNoteIssuer(nit = stamp.emitter.nit, trade_name = settings.trade_name,
                         municipality = settings.municipality, phone = settings.phone,
                         branch = stamp.emitter.branch,
                         point_of_sale = stamp.emitter.point_of_sale,
                         address = stamp.codes.address, cufd = stamp.codes.cufd),
        CreditNoteDocument(
            number = stamp.number, cuf = stamp.cuf, issued_at = stamp.issued_at,
            buyer = Buyer(**(stored.get('buyer') or {})), invoice = invoice,
            original_total = stored['total'], returned_total = amount,
            tax_credit = round(amount * VAT_RATE, MONEY_DECIMALS),
            legend = invoice.legend, user = returned_by,
            original = _invoice_details([SaleLineOut(**line) for line in stored['lines']],
                                        products),
            returned = _invoice_details([as_sold_line(line) for line in returned], products)
        )
    )
    receipt = siat_client.send_credit_note(stamp.emitter, InvoiceSubmission(
        cuis = stamp.codes.cuis, cufd = stamp.codes.cufd,
        archive = gzip.compress(xml.encode('utf-8')), sent_at = stamp.issued_at
    ))
    if not receipt.accepted:
        error_msg = (f'SIAT refused credit note {stamp.number} of sale {stored["number"]} '
                     f'for {owner}: {receipt.messages or "no messages"}')
        logger.error(error_msg)
        raise InvalidInputError(detail = BillingError.SIAT_REFUSED.value)
    return _IssuedNote(stamp = stamp, xml = xml, reception_code = receipt.reception_code,
                       siat_state = receipt.state)


def return_sale(
    dynamodb_resource: ServiceResource,
    owner: str,
    request: SaleReturn,
    returned_by: str
) -> CreditNoteOut:
    '''
        Takes back all or part of an invoiced sale with a Nota de
        Crédito-Débito, and undoes it once the SIN accepts.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            request (SaleReturn): The sale and what comes back.
            returned_by (str): Who takes it back; the cash leaves their till.

        Returns:
            CreditNoteOut: The note, accepted.

        Raises:
            RegisterNotFoundError: No such sale in this shop.
            InvalidInputError: The sale cannot be returned (`_check_returnable`),
                a SKU it did not sell or more units than are left, no open
                till of today or not enough cash in it, a product not
                homologated, or the SIN refused the note.
            ServiceUnavailableError: The SIAT is unreachable; nothing changed.
    '''
    stored = _read_sale(dynamodb_resource, owner, request.sale_id)
    _check_returnable(stored)
    lines = _returned_lines(stored, request)
    amount = round(sum(line.total for line in lines), MONEY_DECIMALS)
    refunds = _refunds(stored, amount)
    cash = round(sum(refund.amount for refund in refunds
                     if refund.method is PaymentMethod.EFECTIVO), MONEY_DECIMALS)
    # Before the SIN: a return the drawer cannot pay must not reach it.
    session_id = require_sale_session(dynamodb_resource, owner, returned_by)
    if cash > expected_cash(dynamodb_resource, owner, session_id):
        raise InvalidInputError(detail = BillingError.EXPENSE_EXCEEDS_CASH.value)

    issued = _issue_note(dynamodb_resource, owner, stored, lines, returned_by)

    give_back(dynamodb_resource, owner, {line.sku: line.allocations for line in lines})
    movement_id = (write_movement(dynamodb_resource, owner, returned_by, session_id, ExpenseIn(
        expense_type = ExpenseType.REFUND, amount = cash, concept = stored['number']))
        if cash > 0 else None)
    stamp = issued.stamp
    note = CreditNoteOut(
        credit_note_id = new_id(), sale_id = request.sale_id, number = stamp.number,
        cuf = stamp.cuf, cufd = stamp.codes.cufd, issued_at = stamp.issued_at,
        qr_url = _qr_url(stamp.emitter.nit, stamp.cuf, stamp.number),
        state = InvoiceState.ACCEPTED, reception_code = issued.reception_code,
        siat_state = issued.siat_state, lines = lines, amount_returned = amount,
        tax_credit = round(amount * VAT_RATE, MONEY_DECIMALS), refunds = refunds,
        created_by = returned_by, created_at = now_iso(),
        refund_session_id = session_id if movement_id else None,
        refund_movement_id = movement_id
    )
    stored.setdefault('credit_notes', []).append(
        {**note.model_dump(mode = 'json'), 'xml': issued.xml})
    write_item(dynamodb_resource, SALES_TABLE, stored)
    note = _mail_note(dynamodb_resource, owner, stored, note)

    message = (f'Credit note {stamp.number} of sale {stored["number"]} accepted for '
               f'{owner}: returned {amount}.')
    logger.info(message)
    return note


def _mail_note(
    dynamodb_resource: ServiceResource,
    owner: str,
    stored: dict[str, Any],
    note: CreditNoteOut
) -> CreditNoteOut:
    '''
        Mails the note when the buyer gave an address, as the invoice was,
        and keeps when it went out. A failure leaves the note as it was: it is
        valid anyway, and the note shows it was not sent.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            stored (dict[str, Any]): The sale as stored, the note already in it.
            note (CreditNoteOut): The note.

        Returns:
            CreditNoteOut: The note, with when it was mailed.
    '''
    if not (stored.get('buyer') or {}).get('email'):
        return note
    item = next(item for item in stored['credit_notes']
                if item['credit_note_id'] == note.credit_note_id)
    if not send_credit_note(CreditNoteMail(_sale_out(stored), note), item['xml'],
                            get_settings(dynamodb_resource, owner)):
        return note
    item['emailed_at'] = now_iso()
    write_item(dynamodb_resource, SALES_TABLE, stored)
    return note.model_copy(update = {'emailed_at': item['emailed_at']})


def list_credit_notes(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str
) -> CreditNotesResponse:
    '''
        The returns of one sale.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            sale_id (str): The sale.

        Returns:
            CreditNotesResponse: Its notes, oldest first.

        Raises:
            RegisterNotFoundError: No such sale in this shop.
    '''
    stored = _read_sale(dynamodb_resource, owner, sale_id)
    if stored is None:
        raise RegisterNotFoundError(detail = BillingError.SALE_NOT_FOUND.value)
    # The XML stays in the table, as the invoice's does.
    items = [CreditNoteOut(**{key: value for key, value in note.items() if key != 'xml'})
             for note in stored.get('credit_notes') or []]
    return CreditNotesResponse(items = items, total = len(items))


def cancel_credit_note(
    dynamodb_resource: ServiceResource,
    owner: str,
    cancellation: CreditNoteCancellation,
    cancelled_by: str
) -> CreditNoteOut:
    '''
        Cancels a note at the SIN and undoes the return: the units leave their
        batches again and the refund stops counting in its till.

        The units are taken before the SIN is asked, as a sale takes them, and
        given back if it refuses: a shelf that sold them since cannot be left
        owing units to a note the SIN no longer holds.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            cancellation (CreditNoteCancellation): The sale, the note and why.
            cancelled_by (str): Who cancels it.

        Returns:
            CreditNoteOut: The note, cancelled.

        Raises:
            RegisterNotFoundError: No such sale or note in this shop.
            InvalidInputError: Already cancelled, past the ninth of the next
                month, the refund's till is closed, the units are no longer on
                the shelf, or the SIN refused.
            ServiceUnavailableError: The SIAT is unreachable; nothing changed.
    '''
    stored = _read_sale(dynamodb_resource, owner, cancellation.sale_id)
    if stored is None:
        raise RegisterNotFoundError(detail = BillingError.SALE_NOT_FOUND.value)
    position, note = next(((index, CreditNoteOut(**{key: value for key, value in item.items()
                                                    if key != 'xml'}))
                           for index, item in enumerate(stored.get('credit_notes') or [])
                           if item['credit_note_id'] == cancellation.credit_note_id),
                          (None, None))
    if note is None:
        raise RegisterNotFoundError(detail = ReturnError.CREDIT_NOTE_NOT_FOUND.value)
    if note.state != InvoiceState.ACCEPTED:
        raise InvalidInputError(detail = ReturnError.CREDIT_NOTE_CANCELLED.value)
    if get_current_time_gmt().date() > cancellation_deadline(note.issued_at):
        raise InvalidInputError(detail = BillingError.CANCELLATION_DEADLINE_PASSED.value)
    if note.refund_session_id:
        require_till_open(dynamodb_resource, owner, note.refund_session_id)

    units = {line.sku: line.allocations for line in note.lines}
    draw_down(dynamodb_resource, owner, units)
    try:
        receipt = siat_client.cancel_credit_note(
            emitter_for(dynamodb_resource, owner),
            _cancellation_request(dynamodb_resource, owner, note.cuf, cancellation.reason_code))
    except ServiceUnavailableError:
        give_back(dynamodb_resource, owner, units)
        raise
    if not receipt.accepted:
        give_back(dynamodb_resource, owner, units)
        error_msg = (f'SIAT refused to cancel credit note {note.number} of sale '
                     f'{stored["number"]} for {owner}: {receipt.messages or "no messages"}')
        logger.error(error_msg)
        raise InvalidInputError(detail = BillingError.SIAT_REFUSED.value)

    if note.refund_movement_id:
        void_movement(dynamodb_resource, owner, note.refund_session_id,
                      note.refund_movement_id, cancelled_by)
    cancelled = note.model_copy(update = {
        'state': InvoiceState.CANCELLED, 'cancellation_reason': cancellation.reason_code,
        'siat_state': receipt.state, 'cancelled_at': now_iso(), 'cancelled_by': cancelled_by
    })
    stored['credit_notes'][position].update(cancelled.model_dump(mode = 'json'))
    write_item(dynamodb_resource, SALES_TABLE, stored)
    if (stored.get('buyer') or {}).get('email'):
        reasons = {entry.code: entry.description for entry in get_catalog(
            dynamodb_resource, owner, SiatCatalog.CANCELLATION_REASONS).entries}
        send_credit_note_cancellation(
            CreditNoteMail(_sale_out(stored), cancelled),
            reasons.get(str(cancellation.reason_code), str(cancellation.reason_code)),
            get_settings(dynamodb_resource, owner))

    message = f'Credit note {note.number} of sale {stored["number"]} cancelled for {owner}.'
    logger.info(message)
    return cancelled


def _cancellation_request(
    dynamodb_resource: ServiceResource,
    owner: str,
    cuf: str,
    reason_code: int
) -> InvoiceCancellation:
    '''
        The SIN's cancellation of one document, with the codes in force today.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            cuf (str): The note's CUF.
            reason_code (int): Code of CANCELLATION_REASONS.

        Returns:
            InvoiceCancellation: The request.
    '''
    codes = current_codes(dynamodb_resource, owner)
    return InvoiceCancellation(cuis = codes.cuis, cufd = codes.cufd, cuf = cuf,
                               reason_code = reason_code)


def credit_note_qr(
    dynamodb_resource: ServiceResource,
    owner: str,
    ref: CreditNoteRef
) -> InvoiceQrOut:
    '''
        The QR a note prints, drawn from the link it stored.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            ref (CreditNoteRef): The sale and the note.

        Returns:
            InvoiceQrOut: The QR as inline SVG.

        Raises:
            RegisterNotFoundError: No such sale or note in this shop.
    '''
    note = next((item for item in list_credit_notes(dynamodb_resource, owner, ref.sale_id).items
                 if item.credit_note_id == ref.credit_note_id), None)
    if note is None:
        raise RegisterNotFoundError(detail = ReturnError.CREDIT_NOTE_NOT_FOUND.value)
    return InvoiceQrOut(sale_id = ref.sale_id, svg = qr_svg(note.qr_url))
