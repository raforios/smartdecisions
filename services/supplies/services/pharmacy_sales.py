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
from typing import Any, Dict, List, Optional, Tuple

from boto3.resources.base import ServiceResource

from models.pharmacy import (
    LOTS_TABLE,
    OWNER_KEY,
    SALES_TABLE,
    SALE_COUNTER_KEY,
    SALE_SORT_KEY,
    SaleItem
)
from schemas.pharmacy import (
    Buyer,
    PharmacyError,
    SaleAllocation,
    SaleLineIn,
    SaleLineOut,
    SaleNoteIn,
    SaleNoteOut,
    SaleNotesResponse,
    SaleStatus
)
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.pharmacy import (
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
from services.pharmacy_stock import allocate, draw_down, give_back

# Money is rounded where it is charged, never where it is added: totals come
# from already-rounded line amounts, so the printed note adds up.
MONEY_DECIMALS = 2


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
            InvalidInputError: Repeated SKU, discount where discounts are off,
                a discount larger than its line, or not enough stock.
            RegisterNotFoundError: A SKU is not in the catalogue.
    '''
    settings = get_settings(dynamodb_resource, owner)
    _reject_repeated_lines(note.lines)

    lines, consumption = _price_lines(dynamodb_resource, owner, note,
                                      settings.discounts_enabled)
    draw_down(dynamodb_resource, owner, consumption)

    stamp = now_iso()
    money = _totals(lines)
    item = SaleItem(
        owner = owner,
        sale_id = document_id(stamp),
        number = next_number(dynamodb_resource, owner,
                             SALE_COUNTER_KEY, settings.sale_series),
        status = SaleStatus.ISSUED.value,
        payment_method = note.payment_method.value,
        lines = [line.model_dump(mode = 'json') for line in lines],
        created_by = created_by, created_at = stamp,
        buyer = note.buyer.model_dump(mode = 'json'), notes = note.notes,
        **money
    )
    write_item(dynamodb_resource, SALES_TABLE, item.__dict__)

    message = (f'Sale {item.number} issued by {created_by} for {owner}: '
               f'{len(lines)} line(s), total {money["total"]}.')
    logger.info(message)
    return _sale_out(item.__dict__)


def _price_lines(
    dynamodb_resource: ServiceResource,
    owner: str,
    note: SaleNoteIn,
    discounts_enabled: bool
) -> Tuple[List[SaleLineOut], Dict[str, List[SaleAllocation]]]:
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
            Tuple[List[SaleLineOut], Dict[str, List[SaleAllocation]]]: The
                priced lines and the units each SKU takes from each batch.

        Raises:
            RegisterNotFoundError: A SKU is not in the catalogue.
            InvalidInputError: The SKU is inactive or there is not enough stock.
    '''
    products = products_by_sku(dynamodb_resource, owner)
    lots = _available_lots_by_sku(dynamodb_resource, owner)

    lines: List[SaleLineOut] = []
    consumption: Dict[str, List[SaleAllocation]] = {}
    for line in note.lines:
        product = products.get(line.sku)
        if product is None:
            raise RegisterNotFoundError(detail = PharmacyError.PRODUCT_NOT_FOUND.value)
        if not product.get('is_active', True):
            raise InvalidInputError(detail = PharmacyError.PRODUCT_INACTIVE.value)

        allocations = allocate(lots.get(line.sku, []), line.quantity)
        consumption[line.sku] = allocations
        lines.append(_line_out(line, product['description'],
                               allocations, discounts_enabled))
    return lines, consumption


def _totals(lines: List[SaleLineOut]) -> Dict[str, float]:
    '''
        What the note adds up to.

        The sums are taken over line amounts that were already rounded where
        they are charged, so the printed note adds up to what it says.

        Args:
            lines (List[SaleLineOut]): The priced lines.

        Returns:
            Dict[str, float]: subtotal, discount, total and cost.
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
    cancelled_by: str
) -> SaleNoteOut:
    '''
        Cancels a note and returns its units to the batches they left.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sale_id (str): Note to cancel.
            cancelled_by (str): Who cancels it.

        Returns:
            SaleNoteOut: The cancelled note.

        Raises:
            RegisterNotFoundError: No such note in this pharmacy.
            InvalidInputError: The note was already cancelled.
    '''
    stored = _read_sale(dynamodb_resource, owner, sale_id)
    if stored is None:
        raise RegisterNotFoundError(detail = PharmacyError.SALE_NOT_FOUND.value)
    if stored['status'] == SaleStatus.CANCELLED.value:
        raise InvalidInputError(detail = PharmacyError.SALE_ALREADY_CANCELLED.value)

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
        raise RegisterNotFoundError(detail = PharmacyError.SALE_NOT_FOUND.value)
    return _sale_out(stored)


def list_sales(
    dynamodb_resource: ServiceResource,
    owner: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
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


def _reject_repeated_lines(lines: List[SaleLineIn]) -> None:
    '''
        A SKU twice in one note is a mistake at the till, not two sales: the
        second line would be priced against the batches the first already took.

        Args:
            lines (List[SaleLineIn]): Lines as sent.

        Raises:
            InvalidInputError: The same SKU appears more than once.
    '''
    seen = {line.sku for line in lines}
    if len(seen) != len(lines):
        raise InvalidInputError(detail = PharmacyError.DUPLICATE_LINE.value)


def _line_out(
    line: SaleLineIn,
    description: str,
    allocations: List[SaleAllocation],
    discounts_enabled: bool
) -> SaleLineOut:
    '''
        One sold line with its money.

        Args:
            line (SaleLineIn): The line as sent.
            description (str): What the product is called.
            allocations (List[SaleAllocation]): Units taken from each batch.
            discounts_enabled (bool): Whether this pharmacy allows discounts.

        Returns:
            SaleLineOut: The line as stored and printed.

        Raises:
            InvalidInputError: A discount arrived with discounts turned off, or
                one larger than the line it is discounting.
    '''
    if line.discount and not discounts_enabled:
        raise InvalidInputError(detail = PharmacyError.DISCOUNTS_DISABLED.value)

    subtotal = round(sum(allocation.amount for allocation in allocations), MONEY_DECIMALS)
    if line.discount > subtotal:
        raise InvalidInputError(detail = PharmacyError.DISCOUNT_ABOVE_LINE.value)

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
) -> Dict[str, List[Dict[str, Any]]]:
    '''
        Every batch with units left, grouped by SKU.

        One read for the whole note: a query per line turned a basket of twelve
        items into twelve round trips before anything was charged.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.

        Returns:
            Dict[str, List[Dict[str, Any]]]: {sku: lots}.
    '''
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in read_partition(dynamodb_resource, LOTS_TABLE, owner):
        if row.get('quantity_remaining', 0) > 0:
            grouped.setdefault(row['sku'], []).append(row)
    return grouped


def _read_sale(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str
) -> Optional[Dict[str, Any]]:
    '''
        One stored note, or None.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sale_id (str): Note to read.

        Returns:
            Dict[str, Any] | None: The item as stored.
    '''
    response = dynamodb_resource.Table(SALES_TABLE).get_item(
        Key = {OWNER_KEY: owner, SALE_SORT_KEY: sale_id}
    )
    return from_dynamo(response.get('Item'))


def _sale_out(stored: Dict[str, Any]) -> SaleNoteOut:
    '''
        A stored note as the API returns it.

        Args:
            stored (Dict[str, Any]): The sale item.

        Returns:
            SaleNoteOut: The note.
    '''
    fields = {key: value for key, value in stored.items() if key != OWNER_KEY}
    fields['buyer'] = Buyer(**(fields.get('buyer') or {}))
    fields['lines'] = [SaleLineOut(**line) for line in fields['lines']]
    return SaleNoteOut(
        **fields,
        margin = round(stored['total'] - stored['cost'], MONEY_DECIMALS)
    )
