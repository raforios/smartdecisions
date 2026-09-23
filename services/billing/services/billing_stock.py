'''
    Pharmacy billing: the lots and the rule that decides which units leave.

    A pharmacy does not sell "a box of amoxicillin": it sells the box that
    expires first. So stock is not a number on the product — it is the sum of
    its batches, and a sale walks them in expiry order (FEFO), which is PEPS
    with the clock instead of the calendar of arrival.

    The draw-down is a DynamoDB transaction conditioned on what is left of each
    batch. Two tills selling the last box at the same second is not a rare
    case at a counter: one of them has to be told there is no stock, and it has
    to be told before the paper prints.
'''
from decimal import Decimal
from typing import Any, Dict, List, Optional

from boto3.resources.base import ServiceResource
from botocore.exceptions import ClientError

from models.billing import LOTS_TABLE, LotItem, OWNER_KEY, LOT_SORT_KEY, lot_key
from schemas.billing import LotOut, LotPricePatch, LotsResponse, BillingError, SaleAllocation
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.billing import (
    SortBounds,
    expiry_order,
    from_dynamo,
    now_iso,
    read_partition,
    write_item
)


def create_lot(
    dynamodb_resource: ServiceResource,
    owner: str,
    lot: LotItem
) -> LotOut:
    '''
        Stores one batch as received.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            lot (LotItem): The batch, already priced and costed.

        Returns:
            LotOut: The stored batch.
    '''
    item = dict(lot.__dict__)
    item[OWNER_KEY] = owner
    item[LOT_SORT_KEY] = lot.sort_key
    write_item(dynamodb_resource, LOTS_TABLE, item)
    return _lot_out(item)


def lots_of(
    dynamodb_resource: ServiceResource,
    owner: str,
    sku: str,
    only_available: bool = True
) -> LotsResponse:
    '''
        The batches of one SKU, in the order they will be sold.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sku (str): Product to read.
            only_available (bool): Leave out exhausted batches.

        Returns:
            LotsResponse: Batches and the units they add up to.
    '''
    stored = read_partition(
        dynamodb_resource, LOTS_TABLE, owner,
        bounds = SortBounds(sort_key = LOT_SORT_KEY, begins_with = f'{sku}#')
    )
    rows = [row for row in stored
            if not only_available or row.get('quantity_remaining', 0) > 0]
    rows.sort(key = expiry_order)
    return LotsResponse(
        sku = sku,
        items = [_lot_out(row) for row in rows],
        available_quantity = sum(row['quantity_remaining'] for row in rows)
    )


def reprice_lot(
    dynamodb_resource: ServiceResource,
    owner: str,
    sku: str,
    lot_id: str,
    patch: LotPricePatch
) -> LotOut:
    '''
        Changes the shelf price of one batch.

        The cost is not touched: it is what the pharmacy paid, and rewriting it
        would rewrite the margin of every sale already made from the batch.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sku (str): Product the batch belongs to.
            lot_id (str): Batch to re-price.
            patch (LotPricePatch): The new price.

        Returns:
            LotOut: The batch after the change.

        Raises:
            RegisterNotFoundError: No such batch in this pharmacy.
    '''
    stored = _read_lot(dynamodb_resource, owner, sku, lot_id)
    if stored is None:
        raise RegisterNotFoundError(detail = BillingError.LOT_NOT_FOUND.value)

    stored['sale_price'] = patch.sale_price
    write_item(dynamodb_resource, LOTS_TABLE, stored)
    message = f'Lot {lot_id} of {sku} re-priced to {patch.sale_price} for {owner}.'
    logger.info(message)
    return _lot_out(stored)


def allocate(
    lots: List[Dict[str, Any]],
    quantity: float
) -> List[SaleAllocation]:
    '''
        Which batches cover a quantity, soonest expiry first.

        Args:
            lots (List[Dict[str, Any]]): Batches of one SKU with units left.
            quantity (float): Units being sold.

        Returns:
            List[SaleAllocation]: Units taken from each batch.

        Raises:
            InvalidInputError: The batches do not cover the quantity.
    '''
    pending = quantity
    taken: List[SaleAllocation] = []
    for lot in sorted(lots, key = expiry_order):
        if pending <= 0:
            break
        available = lot.get('quantity_remaining', 0)
        if available <= 0:
            continue
        units = min(pending, available)
        taken.append(SaleAllocation(
            lot_id = lot['lot_id'], lot_code = lot.get('lot_code'),
            expiry_date = lot.get('expiry_date'), quantity = units,
            unit_price = lot['sale_price'], unit_cost = lot['unit_cost'],
            amount = round(units * lot['sale_price'], 2)
        ))
        pending -= units

    if pending > 0:
        raise InvalidInputError(detail = BillingError.INSUFFICIENT_STOCK.value)
    return taken


def draw_down(
    dynamodb_resource: ServiceResource,
    owner: str,
    consumption: Dict[str, List[SaleAllocation]]
) -> None:
    '''
        Takes the allocated units out of their batches, all or nothing.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            consumption (Dict[str, List[SaleAllocation]]): Allocations per SKU.

        Raises:
            InvalidInputError: A batch no longer holds the units it was
                promised — another till got there first.
    '''
    _apply(dynamodb_resource, owner, consumption, sign = -1)


def give_back(
    dynamodb_resource: ServiceResource,
    owner: str,
    consumption: Dict[str, List[SaleAllocation]]
) -> None:
    '''
        Returns the units of a cancelled note to the batches they left.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            consumption (Dict[str, List[SaleAllocation]]): Allocations per SKU.
    '''
    _apply(dynamodb_resource, owner, consumption, sign = 1)


def _apply(
    dynamodb_resource: ServiceResource,
    owner: str,
    consumption: Dict[str, List[SaleAllocation]],
    sign: int
) -> None:
    '''
        Moves units in or out of the batches in a single transaction.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            consumption (Dict[str, List[SaleAllocation]]): Allocations per SKU.
            sign (int): -1 to sell, +1 to return.

        Raises:
            InvalidInputError: A conditional update failed because the batch no
                longer holds those units.
    '''
    operations: List[Dict[str, Any]] = []
    for sku, allocations in consumption.items():
        for allocation in allocations:
            operations.append(_update_operation(owner, sku, allocation, sign))

    if not operations:
        return

    try:
        dynamodb_resource.meta.client.transact_write_items(TransactItems = operations)
    except ClientError as error:
        if error.response['Error']['Code'] != 'TransactionCanceledException':
            raise
        error_msg = (f'Stock transaction rejected for {owner}: '
                     f'{error.response["Error"].get("Message")}')
        logger.warning(error_msg)
        raise InvalidInputError(
            detail = BillingError.INSUFFICIENT_STOCK.value
        ) from error


def _update_operation(
    owner: str,
    sku: str,
    allocation: SaleAllocation,
    sign: int
) -> Dict[str, Any]:
    '''
        The conditional update of one batch.

        DynamoDB cannot do arithmetic inside a condition, so the condition
        reads the stored remainder directly: a sale only goes through while the
        batch still holds the units it was promised.

        Args:
            owner (str): The pharmacy.
            sku (str): Product the batch belongs to.
            allocation (SaleAllocation): Units taken from that batch.
            sign (int): -1 to sell, +1 to return.

        Returns:
            Dict[str, Any]: One entry of a transact_write_items call.
    '''
    units = Decimal(str(allocation.quantity))
    expression = ('SET quantity_remaining = quantity_remaining - :units'
                  if sign < 0 else
                  'SET quantity_remaining = quantity_remaining + :units')
    condition = ('attribute_exists(lot_key) AND quantity_remaining >= :units'
                 if sign < 0 else 'attribute_exists(lot_key)')
    return {
        'Update': {
            'TableName': LOTS_TABLE,
            'Key': {OWNER_KEY: owner, LOT_SORT_KEY: lot_key(sku, allocation.lot_id)},
            'UpdateExpression': expression,
            'ConditionExpression': condition,
            'ExpressionAttributeValues': {':units': units}
        }
    }


def _read_lot(
    dynamodb_resource: ServiceResource,
    owner: str,
    sku: str,
    lot_id: str
) -> Optional[Dict[str, Any]]:
    '''
        One stored batch, or None.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sku (str): Product the batch belongs to.
            lot_id (str): Batch to read.

        Returns:
            Dict[str, Any] | None: The item as stored.
    '''
    response = dynamodb_resource.Table(LOTS_TABLE).get_item(
        Key = {OWNER_KEY: owner, LOT_SORT_KEY: lot_key(sku, lot_id)}
    )
    return from_dynamo(response.get('Item'))


def _lot_out(stored: Dict[str, Any]) -> LotOut:
    '''
        A stored batch as the API returns it.

        Args:
            stored (Dict[str, Any]): The lot item.

        Returns:
            LotOut: The batch.
    '''
    fields = {key: value for key, value in stored.items()
              if key not in (OWNER_KEY, LOT_SORT_KEY)}
    fields.setdefault('received_at', now_iso())
    return LotOut(**fields)
