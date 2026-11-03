'''
    Reverting the cancellation of an invoice or of a Nota de Crédito-Débito.

    The order is the one the cancellation follows, the other way round:
    everything that can refuse the reversal refuses it before the SIN is
    asked —a document not cancelled at the SIN, reverted once already, past
    the ninth of the next month, a till already closed, units no longer on the
    shelf—, and nothing moves until the SIN accepts.

    A sale reverted takes its units off the shelf again, before the SIN is
    asked, and its till counts it again because the sale is issued again. A
    note reverted gives its units back to the shelf and its refund leaves the
    till again, as a new movement: a voided one is never revived.
'''
from typing import Any

from boto3.resources.base import ServiceResource

from models.billing import SALES_TABLE
from schemas.billing import (
    BillingError,
    PaymentMethod,
    SaleAllocation,
    SaleNoteOut,
    SaleStatus,
    SiatReceipt
)
from schemas.billing_cash import ExpenseIn, ExpenseType
from schemas.billing_returns import CreditNoteOut, CreditNoteRef, ReturnError
from schemas.billing_reversals import ReversalError
from schemas.billing_siat import InvoiceState, SaleInvoice
from services import billing_siat_client as siat_client
from services.billing import get_settings, now_iso, write_item
from services.billing_cash import expected_cash, require_till_open, write_movement
from services.billing_invoicing import cancellation_deadline
from services.billing_mail import ReversalMail, send_reversal
from services.billing_returns import MONEY_DECIMALS, _returned_so_far, find_note
from services.billing_sales import _read_sale, _sale_out, read_invoiced_sale
from services.billing_siat_client import DocumentReversal
from services.billing_siat_codes import current_codes, emitter_for
from services.billing_stock import draw_down, give_back
from services.exceptions import InvalidInputError, ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt


def _check_revertible(
    state: InvoiceState,
    reverted_at: str | None,
    issued_at: str
) -> None:
    '''
        Why a cancelled document cannot be reverted, if it cannot.

        Args:
            state (InvoiceState): Where the document stands.
            reverted_at (str | None): When it was reverted, if ever.
            issued_at (str): Its fechaEmision.

        Raises:
            InvalidInputError: Not cancelled, reverted once already, or past
                the ninth of the month after it was issued.
    '''
    if state != InvoiceState.CANCELLED:
        raise InvalidInputError(detail = ReversalError.DOCUMENT_NOT_CANCELLED.value)
    if reverted_at:
        raise InvalidInputError(detail = ReversalError.ALREADY_REVERTED.value)
    if get_current_time_gmt().date() > cancellation_deadline(issued_at):
        raise InvalidInputError(detail = ReversalError.REVERSAL_DEADLINE_PASSED.value)


def _ask_sin(
    dynamodb_resource: ServiceResource,
    owner: str,
    cuf: str,
    number: int,
    credit_note: bool = False
) -> SiatReceipt:
    '''
        Asks the SIN to revert one cancellation, with the codes in force today.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            cuf (str): The document's CUF.
            number (int): Its number, for the log.
            credit_note (bool): A note rather than an invoice.

        Returns:
            SiatReceipt: The SIN's answer, accepted.

        Raises:
            InvalidInputError: SIAT_REFUSED, with the SIN's messages in the log.
            ServiceUnavailableError: The SIAT is unreachable.
    '''
    codes = current_codes(dynamodb_resource, owner)
    receipt = siat_client.revert_cancellation(
        emitter_for(dynamodb_resource, owner),
        DocumentReversal(cuis = codes.cuis, cufd = codes.cufd, cuf = cuf,
                         credit_note = credit_note)
    )
    if not receipt.accepted:
        error_msg = (f'SIAT refused to revert the cancellation of document {number} for '
                     f'{owner}: {receipt.messages or "no messages"}')
        logger.error(error_msg)
        raise InvalidInputError(detail = BillingError.SIAT_REFUSED.value)
    return receipt


def _tell_buyer(
    dynamodb_resource: ServiceResource,
    owner: str,
    stored: dict[str, Any],
    mail_of: ReversalMail
) -> None:
    '''
        Mails the reversal when the buyer gave an address; a failure is
        logged by the mail and leaves the document valid anyway.
    '''
    if (stored.get('buyer') or {}).get('email'):
        send_reversal(mail_of, get_settings(dynamodb_resource, owner))


def revert_sale_cancellation(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str,
    reverted_by: str
) -> SaleNoteOut:
    '''
        Makes a cancelled invoice valid again: its units leave the shelf once
        more and its till counts it again.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            sale_id (str): The cancelled sale.
            reverted_by (str): Who reverts it.

        Returns:
            SaleNoteOut: The sale, issued again.

        Raises:
            RegisterNotFoundError: No such sale in this shop.
            InvalidInputError: Never invoiced, not cancelled at the SIN,
                reverted once already, past the deadline, its till closed, its
                units no longer on the shelf, or the SIN refused.
            ServiceUnavailableError: The SIAT is unreachable; nothing changed.
    '''
    stored = read_invoiced_sale(dynamodb_resource, owner, sale_id)
    invoice = SaleInvoice(**stored['invoice'])
    _check_revertible(invoice.state, invoice.reverted_at, invoice.issued_at)
    if not invoice.cancelled_at_sin:
        raise InvalidInputError(detail = ReversalError.NOT_CANCELLED_AT_SIN.value)
    if stored.get('cash_session_id'):
        require_till_open(dynamodb_resource, owner, stored['cash_session_id'])

    consumption = {
        line['sku']: [SaleAllocation(**allocation) for allocation in line['allocations']]
        for line in stored['lines']
    }
    # Taken before the SIN is asked, as a sale takes them: a sale the shelf
    # can no longer serve must not become valid again.
    draw_down(dynamodb_resource, owner, consumption)
    try:
        receipt = _ask_sin(dynamodb_resource, owner, invoice.cuf, invoice.number)
    except (InvalidInputError, ServiceUnavailableError):
        give_back(dynamodb_resource, owner, consumption)
        raise

    stored['invoice'] = invoice.model_copy(update = {
        'state': InvoiceState.ACCEPTED, 'siat_state': receipt.state,
        'reverted_at': now_iso(), 'reverted_by': reverted_by
    }).model_dump(mode = 'json')
    stored.update(status = SaleStatus.ISSUED.value, cancelled_at = None, cancelled_by = None)
    write_item(dynamodb_resource, SALES_TABLE, stored)
    _tell_buyer(dynamodb_resource, owner, stored,
                ReversalMail(_sale_out(stored), invoice.number, invoice.cuf))

    message = f'Cancellation of sale {stored["number"]} reverted by {reverted_by} for {owner}.'
    logger.info(message)
    return _sale_out(stored)


def _check_note_fits(
    stored: dict[str, Any],
    note: CreditNoteOut
) -> None:
    '''
        Refuses a note whose units, added to the returns in force, would be
        more than the sale sold: a new return may have taken them since.

        Raises:
            InvalidInputError: RETURN_EXCEEDS_SOLD.
    '''
    sold: dict[str, float] = {}
    for line in stored['lines']:
        sold[line['sku']] = sold.get(line['sku'], 0) + line['quantity']
    returned = _returned_so_far(stored)
    for line in note.lines:
        already = sum(allocation.quantity for allocation in returned.get(line.sku, []))
        if already + line.quantity > sold.get(line.sku, 0):
            raise InvalidInputError(detail = ReturnError.RETURN_EXCEEDS_SOLD.value)


def revert_credit_note_cancellation(
    dynamodb_resource: ServiceResource,
    owner: str,
    ref: CreditNoteRef,
    reverted_by: str
) -> CreditNoteOut:
    '''
        Makes a cancelled note valid again: its units come back to the shelf
        and its cash refund leaves its till once more.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            ref (CreditNoteRef): The sale and the cancelled note.
            reverted_by (str): Who reverts it.

        Returns:
            CreditNoteOut: The note, accepted again.

        Raises:
            RegisterNotFoundError: No such sale or note in this shop.
            InvalidInputError: The sale was cancelled, the note is not
                cancelled, reverted once already, past the deadline, its units
                were returned again since, its till closed or short of the
                cash, or the SIN refused.
            ServiceUnavailableError: The SIAT is unreachable; nothing changed.
    '''
    stored = _read_sale(dynamodb_resource, owner, ref.sale_id)
    position, note = find_note(stored, ref.credit_note_id)
    if stored['status'] != SaleStatus.ISSUED.value:
        raise InvalidInputError(detail = ReturnError.SALE_CANCELLED.value)
    _check_revertible(note.state, note.reverted_at, note.issued_at)
    _check_note_fits(stored, note)
    cash = round(sum(refund.amount for refund in note.refunds
                     if refund.method is PaymentMethod.EFECTIVO), MONEY_DECIMALS)
    if note.refund_session_id:
        require_till_open(dynamodb_resource, owner, note.refund_session_id)
        if cash > expected_cash(dynamodb_resource, owner, note.refund_session_id):
            raise InvalidInputError(detail = BillingError.EXPENSE_EXCEEDS_CASH.value)

    receipt = _ask_sin(dynamodb_resource, owner, note.cuf, note.number, credit_note = True)

    give_back(dynamodb_resource, owner, {line.sku: line.allocations for line in note.lines})
    movement_id = (write_movement(dynamodb_resource, owner, reverted_by, note.refund_session_id,
                                  ExpenseIn(expense_type = ExpenseType.REFUND, amount = cash,
                                            concept = stored['number']))
                   if note.refund_session_id else None)
    reverted = note.model_copy(update = {
        'state': InvoiceState.ACCEPTED, 'siat_state': receipt.state,
        'refund_movement_id': movement_id, 'reverted_at': now_iso(),
        'reverted_by': reverted_by
    })
    stored['credit_notes'][position].update(reverted.model_dump(mode = 'json'))
    write_item(dynamodb_resource, SALES_TABLE, stored)
    _tell_buyer(dynamodb_resource, owner, stored,
                ReversalMail(_sale_out(stored), note.number, note.cuf, credit_note = True))

    message = (f'Cancellation of credit note {note.number} of sale {stored["number"]} '
               f'reverted by {reverted_by} for {owner}.')
    logger.info(message)
    return reverted
