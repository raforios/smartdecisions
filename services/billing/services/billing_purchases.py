'''
    Pharmacy billing: the nota de compra.

    What a laboratory, importer or distributor delivered. Each line becomes one
    batch, with the cost it came in at and the price it will sell at — both set
    by that purchase, because the next delivery of the same product may carry
    different numbers.

    Receiving is the mirror of selling and much simpler: nothing can fail for
    lack of stock, so the note and its batches are written straight through.
'''
from typing import Any, Dict, List, Optional

from boto3.resources.base import ServiceResource

from models.billing import (
    LotItem,
    OWNER_KEY,
    PURCHASES_TABLE,
    PURCHASE_COUNTER_KEY,
    PURCHASE_SORT_KEY,
    PurchaseItem
)
from schemas.billing import (
    BillingError,
    PurchaseLineOut,
    PurchaseNoteIn,
    PurchaseNoteOut,
    PurchaseNotesResponse
)
from services.exceptions import RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.billing import (
    SortBounds,
    date_window,
    document_id,
    from_dynamo,
    get_settings,
    products_by_sku,
    new_id,
    next_number,
    now_iso,
    read_partition,
    write_item
)
from services.billing_stock import create_lot

MONEY_DECIMALS = 2


def receive_purchase(
    dynamodb_resource: ServiceResource,
    owner: str,
    note: PurchaseNoteIn,
    created_by: str
) -> PurchaseNoteOut:
    '''
        Records a delivery and puts its batches on the shelf.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            note (PurchaseNoteIn): What arrived.
            created_by (str): Who received it.

        Returns:
            PurchaseNoteOut: The recorded note with the batches it created.

        Raises:
            RegisterNotFoundError: A SKU is not in the catalogue.
    '''
    settings = get_settings(dynamodb_resource, owner)
    products = products_by_sku(dynamodb_resource, owner)

    stamp = now_iso()
    purchase_id = document_id(stamp)

    lines: List[PurchaseLineOut] = []
    for line in note.lines:
        if line.sku not in products:
            raise RegisterNotFoundError(detail = BillingError.PRODUCT_NOT_FOUND.value)

        lot = LotItem(
            owner = owner, sku = line.sku, lot_id = new_id(),
            unit_cost = line.unit_cost, sale_price = line.sale_price,
            quantity_received = line.quantity, quantity_remaining = line.quantity,
            received_at = stamp, lot_code = line.lot_code,
            expiry_date = line.expiry_date.isoformat() if line.expiry_date else None,
            purchase_id = purchase_id
        )
        create_lot(dynamodb_resource, owner, lot)
        lines.append(PurchaseLineOut(
            **line.model_dump(mode = 'json'), lot_id = lot.lot_id,
            total_cost = round(line.quantity * line.unit_cost, MONEY_DECIMALS)
        ))

    item = PurchaseItem(
        owner = owner, purchase_id = purchase_id,
        number = next_number(dynamodb_resource, owner,
                             PURCHASE_COUNTER_KEY, settings.purchase_series),
        supplier_name = note.supplier_name,
        supplier_document = note.supplier_document,
        invoice_number = note.invoice_number,
        invoice_date = note.invoice_date.isoformat() if note.invoice_date else None,
        notes = note.notes,
        lines = [line.model_dump(mode = 'json') for line in lines],
        total_cost = round(sum(line.total_cost for line in lines), MONEY_DECIMALS),
        created_by = created_by, created_at = stamp
    )
    write_item(dynamodb_resource, PURCHASES_TABLE, item.__dict__)

    message = (f'Purchase {item.number} received by {created_by} for {owner}: '
               f'{len(lines)} batch(es), cost {item.total_cost}.')
    logger.info(message)
    return _purchase_out(item.__dict__)


def get_purchase(
    dynamodb_resource: ServiceResource,
    owner: str,
    purchase_id: str
) -> PurchaseNoteOut:
    '''
        One delivery note.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            purchase_id (str): Note to read.

        Returns:
            PurchaseNoteOut: The note.

        Raises:
            RegisterNotFoundError: No such note in this pharmacy.
    '''
    response = dynamodb_resource.Table(PURCHASES_TABLE).get_item(
        Key = {OWNER_KEY: owner, PURCHASE_SORT_KEY: purchase_id}
    )
    stored = from_dynamo(response.get('Item'))
    if not stored:
        raise RegisterNotFoundError(detail = BillingError.PURCHASE_NOT_FOUND.value)
    return _purchase_out(stored)


def list_purchases(
    dynamodb_resource: ServiceResource,
    owner: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> PurchaseNotesResponse:
    '''
        The delivery notes of a window, newest first.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            date_from (str | None): First day, ISO date.
            date_to (str | None): Last day, ISO date.

        Returns:
            PurchaseNotesResponse: The notes.
    '''
    stored = read_partition(
        dynamodb_resource, PURCHASES_TABLE, owner,
        bounds = SortBounds(sort_key = PURCHASE_SORT_KEY,
                            between = date_window(date_from, date_to)),
        descending = True
    )
    items = [_purchase_out(row) for row in stored]
    return PurchaseNotesResponse(items = items, total = len(items))


def _purchase_out(stored: Dict[str, Any]) -> PurchaseNoteOut:
    '''
        A stored note as the API returns it.

        Args:
            stored (Dict[str, Any]): The purchase item.

        Returns:
            PurchaseNoteOut: The note.
    '''
    fields = {key: value for key, value in stored.items() if key != OWNER_KEY}
    fields['lines'] = [PurchaseLineOut(**line) for line in fields['lines']]
    return PurchaseNoteOut(**fields)
