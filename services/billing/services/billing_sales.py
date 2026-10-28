'''
    Pharmacy billing: the nota de venta.

    Issuing one is the only moment stock actually leaves the pharmacy, so the
    order matters: the batches are read and allocated, the units are drawn down
    under a condition, and only then is the note written. A note that exists
    without its stock movement would be a paper the shelf never paid for.

    A note is never edited. It can be cancelled, which returns exactly the
    units it took to exactly the batches they came from — that is why each line
    stores its allocations instead of just a quantity.
'''
from dataclasses import dataclass
from typing import Any

from boto3.resources.base import ServiceResource

from models.billing import (
    LOTS_TABLE,
    OWNER_KEY,
    SALES_TABLE,
    SALE_COUNTER_KEY,
    SALE_SORT_KEY,
    SaleItem
)
from schemas.billing import (
    Buyer,
    BillingError,
    PaymentMethod,
    SaleAllocation,
    SaleLineIn,
    SaleLineOut,
    SaleNoteIn,
    SaleNoteOut,
    SaleNotesResponse,
    SaleStatus,
    SettingsResponse
)
from schemas.billing_siat import InvoiceQrOut, InvoiceState, SaleInvoice
from services.billing_cash import require_sale_session
from services.billing_customers import remember_customer
from services.billing_payments import paid_by_card, primary_method, resolve_payments
from services.billing_invoicing import (
    InvoiceDraft,
    InvoicePlan,
    cancel_at_sin,
    cancellation_deadline,
    issue_invoice,
    prepare_invoice,
    qr_svg
)
from services.exceptions import (
    InvalidInputError,
    RegisterNotFoundError,
    ServiceUnavailableError
)
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt
from services.billing import (
    SortBounds,
    date_window,
    document_id,
    from_dynamo,
    get_settings,
    products_by_sku,
    next_number,
    now_iso,
    read_partition,
    write_item
)
from services.billing_siat import mask_card
from services.billing_stock import allocate, draw_down, give_back

# Money is rounded where it is charged, never where it is added: totals come
# from already-rounded line amounts, so the printed note adds up.
MONEY_DECIMALS = 2


@dataclass(frozen = True)
class PricedSale:
    '''
        A sale priced against its batches, before anything moves: the lines,
        the units each SKU takes from each batch, and the catalogue — which
        the invoice reads for the SIN codes, so it is read once.
    '''
    lines: list[SaleLineOut]
    consumption: dict[str, list[SaleAllocation]]
    products: dict[str, dict[str, Any]]

# The CI and the NIT in the SIN's catalogue of identity documents: the two the
# norm asks to be numeric.
NUMERIC_DOCUMENT_TYPES = (1, 5)


def issue_sale(
    dynamodb_resource: ServiceResource,
    owner: str,
    note: SaleNoteIn,
    created_by: str
) -> SaleNoteOut:
    '''
        Registers a sale over the counter and takes the units out of stock.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            note (SaleNoteIn): What is being sold.
            created_by (str): Who is at the till.

        Returns:
            SaleNoteOut: The issued note, ready to print.

        Raises:
            InvalidInputError: No open till of today for the seller, no
                buyer where the pharmacy requires one, repeated SKU, discount
                where discounts are off, a discount larger than its line, not
                enough stock, or an invoice that cannot be issued or that the
                SIN refused.
            RegisterNotFoundError: A SKU is not in the catalogue.
            ServiceUnavailableError: The shop invoices and the SIAT is
                unreachable.
    '''
    settings = get_settings(dynamodb_resource, owner)
    # Before any stock moves: a sale refused for want of a till must not have
    # touched a shelf.
    session_id = require_sale_session(dynamodb_resource, owner, created_by)
    _require_buyer(note, settings)
    _reject_repeated_lines(note.lines)

    priced = _price_lines(dynamodb_resource, owner, note, settings.discounts_enabled)
    money = _totals(priced.lines)
    payments = resolve_payments(note, money['total'])
    card = _masked_card(note, [payment.method for payment in payments])
    # Also before any stock moves: a sale that cannot be invoiced is refused
    # with the shelf untouched.
    plan = (prepare_invoice(dynamodb_resource, owner, settings,
                            InvoiceDraft(priced.lines, priced.products, payments))
            if settings.invoicing_enabled else None)
    draw_down(dynamodb_resource, owner, priced.consumption)

    stamp = now_iso()
    item = SaleItem(
        owner = owner,
        sale_id = document_id(stamp),
        number = next_number(dynamodb_resource, owner,
                             SALE_COUNTER_KEY, settings.sale_series),
        status = SaleStatus.ISSUED.value,
        payment_method = primary_method(payments).value,
        payments = [payment.model_dump(mode = 'json') for payment in payments],
        lines = [line.model_dump(mode = 'json') for line in priced.lines],
        created_by = created_by, created_at = stamp,
        buyer = note.buyer.model_dump(mode = 'json'), notes = note.notes,
        card_number = card, cash_session_id = session_id,
        **money
    )
    if plan is not None:
        _attach_invoice(dynamodb_resource, plan, item, priced.consumption)
    write_item(dynamodb_resource, SALES_TABLE, item.__dict__)
    if plan is not None:
        remember_customer(dynamodb_resource, owner, note.buyer, created_by)

    message = (f'Sale {item.number} issued by {created_by} for {owner}: '
               f'{len(priced.lines)} line(s), total {money["total"]}.')
    logger.info(message)
    return _sale_out(item.__dict__)


def _price_lines(
    dynamodb_resource: ServiceResource,
    owner: str,
    note: SaleNoteIn,
    discounts_enabled: bool
) -> PricedSale:
    '''
        Every line priced against the batches it will actually take.

        Nothing is written here: if a line cannot be covered this raises before
        a single unit has moved, which is what keeps a failed sale from leaving
        the shelf short.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            note (SaleNoteIn): What is being sold.
            discounts_enabled (bool): Whether this pharmacy allows discounts.

        Returns:
            PricedSale: The priced lines, the units each SKU takes from each
                batch, and the catalogue they were priced against.

        Raises:
            RegisterNotFoundError: A SKU is not in the catalogue.
            InvalidInputError: The SKU is inactive or there is not enough stock.
    '''
    products = products_by_sku(dynamodb_resource, owner)
    lots = _available_lots_by_sku(dynamodb_resource, owner)

    lines: list[SaleLineOut] = []
    consumption: dict[str, list[SaleAllocation]] = {}
    for line in note.lines:
        product = products.get(line.sku)
        if product is None:
            raise RegisterNotFoundError(detail = BillingError.PRODUCT_NOT_FOUND.value)
        if not product.get('is_active', True):
            raise InvalidInputError(detail = BillingError.PRODUCT_INACTIVE.value)

        allocations = allocate(lots.get(line.sku, []), line.quantity)
        consumption[line.sku] = allocations
        lines.append(_line_out(line, product['description'],
                               allocations, discounts_enabled))
    return PricedSale(lines = lines, consumption = consumption, products = products)


def _totals(lines: list[SaleLineOut]) -> dict[str, float]:
    '''
        What the note adds up to.

        The sums are taken over line amounts that were already rounded where
        they are charged, so the printed note adds up to what it says.

        Args:
            lines (list[SaleLineOut]): The priced lines.

        Returns:
            dict[str, float]: subtotal, discount, total and cost.
    '''
    return {
        'subtotal': round(sum(line.subtotal for line in lines), MONEY_DECIMALS),
        'discount': round(sum(line.discount for line in lines), MONEY_DECIMALS),
        'total': round(sum(line.total for line in lines), MONEY_DECIMALS),
        'cost': round(sum(line.cost for line in lines), MONEY_DECIMALS)
    }


def cancel_sale(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str,
    cancelled_by: str,
    reason_code: int | None = None
) -> SaleNoteOut:
    '''
        Cancels a note and returns its units to the batches they left.

        An invoiced note is cancelled at the SIN first: if the SIN refuses,
        nothing here changes, and the shelf never holds units of an invoice
        that is still in force.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sale_id (str): Note to cancel.
            cancelled_by (str): Who cancels it.
            reason_code (int | None): Code of CANCELLATION_REASONS; required
                when the note is an invoice.

        Returns:
            SaleNoteOut: The cancelled note.

        Raises:
            RegisterNotFoundError: No such note in this pharmacy.
            InvalidInputError: The note was already cancelled, an invoice came
                with no reason, or the SIN refused to cancel it.
            ServiceUnavailableError: The note is an invoice and the SIAT is
                unreachable.
    '''
    stored = _read_sale(dynamodb_resource, owner, sale_id)
    if stored is None:
        raise RegisterNotFoundError(detail = BillingError.SALE_NOT_FOUND.value)
    if stored['status'] == SaleStatus.CANCELLED.value:
        raise InvalidInputError(detail = BillingError.SALE_ALREADY_CANCELLED.value)
    if stored.get('invoice'):
        stored['invoice'] = _cancel_invoice(dynamodb_resource, owner,
                                            SaleInvoice(**stored['invoice']), reason_code)

    consumption = {
        line['sku']: [SaleAllocation(**allocation) for allocation in line['allocations']]
        for line in stored['lines']
    }
    give_back(dynamodb_resource, owner, consumption)

    stored['status'] = SaleStatus.CANCELLED.value
    stored['cancelled_at'] = now_iso()
    stored['cancelled_by'] = cancelled_by
    write_item(dynamodb_resource, SALES_TABLE, stored)

    message = f'Sale {stored["number"]} cancelled by {cancelled_by} for {owner}.'
    logger.info(message)
    return _sale_out(stored)


def _attach_invoice(
    dynamodb_resource: ServiceResource,
    plan: InvoicePlan,
    item: SaleItem,
    consumption: dict[str, list[SaleAllocation]]
) -> None:
    '''
        Issues the invoice of a sale about to be stored, and keeps it with it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            plan (InvoicePlan): What `prepare_invoice` gathered.
            item (SaleItem): The sale, still unwritten.
            consumption (dict[str, list[SaleAllocation]]): The units it took,
                to give back if the SIN refuses the invoice.

        Raises:
            InvalidInputError: The SIN refused the invoice.
    '''
    try:
        issued = issue_invoice(dynamodb_resource, item.owner, plan, _sale_out(item.__dict__))
    except (InvalidInputError, ServiceUnavailableError):
        # Refused, the sale is not issued: its units go back.
        give_back(dynamodb_resource, item.owner, consumption)
        raise
    item.invoice = issued.invoice.model_dump(mode = 'json')
    item.invoice_xml = issued.xml


def _cancel_invoice(
    dynamodb_resource: ServiceResource,
    owner: str,
    invoice: SaleInvoice,
    reason_code: int | None
) -> dict[str, Any]:
    '''
        Cancels the invoice of a note, where the SIN holds it.

        One issued offline is not at the SIN yet, and there is nothing to
        cancel there until its package is validated. One the SIN observed was
        never valid there, so it is cancelled here only.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            invoice (SaleInvoice): The invoice of the note.
            reason_code (int | None): Code of CANCELLATION_REASONS.

        Returns:
            dict[str, Any]: The invoice, cancelled, as the note stores it.

        Raises:
            InvalidInputError: No reason, an invoice still waiting for its
                package, past the ninth of the following month, or the SIN
                refused to cancel it.
    '''
    if reason_code is None:
        raise InvalidInputError(detail = BillingError.CANCELLATION_REASON_REQUIRED.value)
    if invoice.state == InvoiceState.OFFLINE:
        raise InvalidInputError(detail = BillingError.INVOICE_NOT_YET_AT_SIN.value)
    if get_current_time_gmt().date() > cancellation_deadline(invoice.issued_at):
        raise InvalidInputError(detail = BillingError.CANCELLATION_DEADLINE_PASSED.value)
    if invoice.state == InvoiceState.OBSERVED:
        cancelled = invoice.model_copy(update = {'state': InvoiceState.CANCELLED,
                                                 'cancellation_reason': reason_code})
    else:
        cancelled = cancel_at_sin(dynamodb_resource, owner, invoice, reason_code)
    return cancelled.model_dump(mode = 'json')


def get_sale(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str
) -> SaleNoteOut:
    '''
        One note, as it prints.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sale_id (str): Note to read.

        Returns:
            SaleNoteOut: The note.

        Raises:
            RegisterNotFoundError: No such note in this pharmacy.
    '''
    stored = _read_sale(dynamodb_resource, owner, sale_id)
    if stored is None:
        raise RegisterNotFoundError(detail = BillingError.SALE_NOT_FOUND.value)
    return _sale_out(stored)


def sale_qr(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str
) -> InvoiceQrOut:
    '''
        The QR the invoice of a sale prints.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sale_id (str): Note whose invoice is printed.

        Returns:
            InvoiceQrOut: The QR as inline SVG.

        Raises:
            RegisterNotFoundError: No such note in this pharmacy.
            InvalidInputError: SALE_NOT_INVOICED, an internal note.
    '''
    sale = get_sale(dynamodb_resource, owner, sale_id)
    if sale.invoice is None:
        raise InvalidInputError(detail = BillingError.SALE_NOT_INVOICED.value)
    return InvoiceQrOut(sale_id = sale_id, svg = qr_svg(sale.invoice.qr_url))


def list_sales(
    dynamodb_resource: ServiceResource,
    owner: str,
    date_from: str | None = None,
    date_to: str | None = None
) -> SaleNotesResponse:
    '''
        The notes of a window, newest first.

        The identifier starts with the issue timestamp, so a day is a bounded
        Query on the sort key and not a filter over everything the pharmacy
        ever sold.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            date_from (str | None): First day, ISO date.
            date_to (str | None): Last day, ISO date.

        Returns:
            SaleNotesResponse: Notes and what they add up to.
    '''
    stored = read_partition(
        dynamodb_resource, SALES_TABLE, owner,
        bounds = SortBounds(sort_key = SALE_SORT_KEY,
                            between = date_window(date_from, date_to)),
        descending = True
    )
    items = [_sale_out(row) for row in stored]
    charged = round(sum(item.total for item in items
                        if item.status == SaleStatus.ISSUED), MONEY_DECIMALS)
    return SaleNotesResponse(items = items, total = len(items), total_amount = charged)


def _require_buyer(
    note: SaleNoteIn,
    settings: SettingsResponse
) -> None:
    """
        Refuses a sale with no buyer document where the pharmacy needs one.

        Phase II of the Bolivian norm requires every invoice to be nominative
        whatever the amount, and it is explicit about what that means: the
        DOCUMENT NUMBER, not the name or business name (`docs/siat/SIAT.md`).
        So the document is demanded and the name is not — asking for both
        would refuse a sale the norm accepts, over a field the buyer is not
        obliged to give.

        It is a setting and not a constant because a pharmacy still issuing
        internal notes has to keep working until it is authorised. Invoicing
        demands it too, and also the document type: the XSD has no empty
        `codigoTipoDocumentoIdentidad`.

        Args:
            note (SaleNoteIn): What is being sold, with its buyer.
            settings (SettingsResponse): Whether this pharmacy must name the
                buyer, and whether it invoices.

        Raises:
            InvalidInputError: BUYER_REQUIRED when the document is missing.
    """
    if not (settings.buyer_required or settings.invoicing_enabled):
        return
    if not (note.buyer and (note.buyer.document or '').strip()):
        raise InvalidInputError(detail = BillingError.BUYER_REQUIRED.value)
    if settings.invoicing_enabled and note.buyer.document_type is None:
        raise InvalidInputError(detail = BillingError.BUYER_REQUIRED.value)
    # The norm: a CI or a NIT the SIN receives has to be a number.
    if settings.invoicing_enabled and note.buyer.document_type in NUMERIC_DOCUMENT_TYPES \
            and not note.buyer.document.strip().isdigit():
        raise InvalidInputError(detail = BillingError.BUYER_DOCUMENT_NOT_NUMERIC.value)


def _masked_card(
    note: SaleNoteIn,
    methods: list[PaymentMethod]
) -> str | None:
    """
        The card number as it may be stored: masked, or nothing at all.

        Two rules of the norm, both in `docs/siat/SIAT.md`. A card number may
        only travel when the payment method IS a card — sending one with a
        cash sale is an error the tax office reports. And when it does travel
        it goes with the middle digits zeroed, first and last four in clear.

        Masking here, at the boundary, is deliberate: the full number never
        reaches the table, the log or the printed note, so there is no copy of
        it to leak later.

        Args:
            note (SaleNoteIn): The sale as it arrived.
            methods (list[PaymentMethod]): The methods it was paid with.

        Returns:
            str | None: The masked number, or None when there is none.

        Raises:
            InvalidInputError: A card number without a card payment, or a
                number too short to be one.
    """
    raw = (note.card_number or '').strip()
    is_card = paid_by_card(methods)
    if not raw:
        return None
    if not is_card:
        raise InvalidInputError(detail = BillingError.CARD_WITHOUT_CARD_PAYMENT.value)
    try:
        return mask_card(raw)
    except ValueError as error:
        raise InvalidInputError(
            detail = BillingError.INVALID_CARD_NUMBER.value
        ) from error


def _reject_repeated_lines(lines: list[SaleLineIn]) -> None:
    '''
        A SKU twice in one note is a mistake at the till, not two sales: the
        second line would be priced against the batches the first already took.

        Args:
            lines (list[SaleLineIn]): Lines as sent.

        Raises:
            InvalidInputError: The same SKU appears more than once.
    '''
    seen = {line.sku for line in lines}
    if len(seen) != len(lines):
        raise InvalidInputError(detail = BillingError.DUPLICATE_LINE.value)


def _line_out(
    line: SaleLineIn,
    description: str,
    allocations: list[SaleAllocation],
    discounts_enabled: bool
) -> SaleLineOut:
    '''
        One sold line with its money.

        Args:
            line (SaleLineIn): The line as sent.
            description (str): What the product is called.
            allocations (list[SaleAllocation]): Units taken from each batch.
            discounts_enabled (bool): Whether this pharmacy allows discounts.

        Returns:
            SaleLineOut: The line as stored and printed.

        Raises:
            InvalidInputError: A discount arrived with discounts turned off, or
                one larger than the line it is discounting.
    '''
    if line.discount and not discounts_enabled:
        raise InvalidInputError(detail = BillingError.DISCOUNTS_DISABLED.value)

    subtotal = round(sum(allocation.amount for allocation in allocations), MONEY_DECIMALS)
    if line.discount > subtotal:
        raise InvalidInputError(detail = BillingError.DISCOUNT_ABOVE_LINE.value)

    cost = round(sum(allocation.quantity * allocation.unit_cost
                     for allocation in allocations), MONEY_DECIMALS)
    return SaleLineOut(
        sku = line.sku, description = description, quantity = line.quantity,
        discount = line.discount, allocations = allocations, subtotal = subtotal,
        total = round(subtotal - line.discount, MONEY_DECIMALS), cost = cost
    )


def _available_lots_by_sku(
    dynamodb_resource: ServiceResource,
    owner: str
) -> dict[str, list[dict[str, Any]]]:
    '''
        Every batch with units left, grouped by SKU.

        One read for the whole note: a query per line turned a basket of twelve
        items into twelve round trips before anything was charged.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.

        Returns:
            dict[str, list[dict[str, Any]]]: {sku: lots}.
    '''
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in read_partition(dynamodb_resource, LOTS_TABLE, owner):
        if row.get('quantity_remaining', 0) > 0:
            grouped.setdefault(row['sku'], []).append(row)
    return grouped


def _read_sale(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str
) -> dict[str, Any] | None:
    '''
        One stored note, or None.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sale_id (str): Note to read.

        Returns:
            dict[str, Any] | None: The item as stored.
    '''
    response = dynamodb_resource.Table(SALES_TABLE).get_item(
        Key = {OWNER_KEY: owner, SALE_SORT_KEY: sale_id}
    )
    return from_dynamo(response.get('Item'))


def _sale_out(stored: dict[str, Any]) -> SaleNoteOut:
    '''
        A stored note as the API returns it.

        Args:
            stored (dict[str, Any]): The sale item.

        Returns:
            SaleNoteOut: The note.
    '''
    # The XML stays in the table: it is the legal document a package and an
    # e-mail carry, not part of what a note answers.
    fields = {key: value for key, value in stored.items()
              if key not in (OWNER_KEY, 'invoice_xml')}
    fields['buyer'] = Buyer(**(fields.get('buyer') or {}))
    # Notes issued before payments were combined paid their total one way.
    fields['payments'] = fields.get('payments') or [
        {'method': stored['payment_method'], 'amount': stored['total']}
    ]
    fields['lines'] = [SaleLineOut(**line) for line in fields['lines']]
    return SaleNoteOut(
        **fields,
        margin = round(stored['total'] - stored['cost'], MONEY_DECIMALS)
    )
