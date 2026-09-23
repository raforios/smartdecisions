'''
    Pharmacy billing: the catalogue, the per-tenant settings and the document
    numbering, plus the few helpers the rest of the module shares.

    Everything here takes the DynamoDB resource as its first argument: the
    route resolves it through GET_DB_DEPENDENCY and hands it down, so nothing
    in the service reaches for a connection of its own.

    The relational side of SUPPLIES — the warehouse the Ministry runs — is
    untouched by this module and keeps its own engine in `db_connection_sql`.
'''
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from boto3.dynamodb.conditions import Key
from boto3.resources.base import ServiceResource

from models.pharmacy import (
    CONFIG_KEY,
    LOTS_TABLE,
    OWNER_KEY,
    PRODUCTS_TABLE,
    PRODUCT_SORT_KEY,
    PURCHASE_COUNTER_KEY,
    ProductItem,
    SALE_COUNTER_KEY,
    SETTINGS_TABLE,
    SETTING_SORT_KEY
)
from schemas.pharmacy import (
    PharmacyError,
    PharmacySettings,
    ProductIn,
    ProductOut,
    ProductPatch,
    ProductsResponse,
    SettingsResponse
)
from services.exceptions import RegisterAlreadyExistsError, RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt


def new_id() -> str:
    '''
        Identifier for a new item.

        Returns:
            str: A random UUID.
    '''
    return str(uuid4())


def now_iso() -> str:
    '''
        Current time in the service timezone, ISO 8601 to the second.

        Returns:
            str: Timestamp such as "2026-09-22T20:30:00-04:00".
    '''
    return get_current_time_gmt().isoformat(timespec = 'seconds')


def document_id(stamp: Optional[str] = None) -> str:
    '''
        Identifier of a sale or purchase note.

        It starts with the timestamp so the sort key orders documents by the
        moment they were issued: a date window is then a bounded Query instead
        of a filter over the whole partition.

        Args:
            stamp (str | None): Issue time; now when absent.

        Returns:
            str: "<timestamp>#<uuid>".
    '''
    return f'{stamp or now_iso()}#{new_id()}'


def from_dynamo(value: Any) -> Any:
    '''
        Turns the Decimals DynamoDB hands back into native numbers, recursively,
        so DTOs and arithmetic never meet a Decimal.

        Args:
            value (Any): An item, a list of items or a scalar as returned by boto3.

        Returns:
            Any: The same structure with int/float instead of Decimal.
    '''
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [from_dynamo(element) for element in value]
    if isinstance(value, dict):
        return {key: from_dynamo(element) for key, element in value.items()}
    return value


def to_dynamo(value: Any) -> Any:
    '''
        The inverse of `from_dynamo`: floats become Decimal so boto3 accepts
        the item. Ints and everything else pass through.

        Args:
            value (Any): An item, a list or a scalar about to be written.

        Returns:
            Any: The same structure with Decimal instead of float.
    '''
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [to_dynamo(element) for element in value]
    if isinstance(value, dict):
        return {key: to_dynamo(element) for key, element in value.items()}
    return value


def write_item(
    dynamodb_resource: ServiceResource,
    table_name: str,
    item: Dict[str, Any]
) -> None:
    '''
        Stores one item, converting floats on the way in.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Target table.
            item (Dict[str, Any]): Item to store.
    '''
    dynamodb_resource.Table(table_name).put_item(
        Item = to_dynamo({key: value for key, value in item.items() if value is not None})
    )


@dataclass
class SortBounds:
    '''
        How a query narrows the sort key of a partition.

        The three travel together — one attribute and the way it is bounded —
        so they go as one argument: the reader never has to work out which
        combination of loose parameters is meaningful.
    '''
    sort_key: str
    begins_with: Optional[str] = None
    between: Optional[Dict[str, str]] = None


def _key_condition(
    owner: str,
    bounds: Optional[SortBounds]
) -> Any:
    '''
        The key condition of a partition query.

        Args:
            owner (str): The pharmacy.
            bounds (SortBounds | None): How to narrow the sort key.

        Returns:
            Any: A boto3 key condition.
    '''
    condition = Key(OWNER_KEY).eq(owner)
    if bounds is None:
        return condition
    if bounds.begins_with:
        return condition & Key(bounds.sort_key).begins_with(bounds.begins_with)
    if bounds.between:
        low, high = bounds.between.get('from'), bounds.between.get('to')
        if low and high:
            return condition & Key(bounds.sort_key).between(low, high)
        if low:
            return condition & Key(bounds.sort_key).gte(low)
        if high:
            return condition & Key(bounds.sort_key).lte(high)
    return condition


def read_partition(
    dynamodb_resource: ServiceResource,
    table_name: str,
    owner: str,
    bounds: Optional[SortBounds] = None,
    descending: bool = False
) -> List[Dict[str, Any]]:
    '''
        Every item of one owner, optionally bounded on the sort key.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Target table.
            owner (str): The pharmacy.
            bounds (SortBounds | None): How to narrow the sort key.
            descending (bool): Newest first when True.

        Returns:
            List[Dict[str, Any]]: Matched items, Decimals already converted.
    '''
    table = dynamodb_resource.Table(table_name)
    items: List[Dict[str, Any]] = []
    arguments: Dict[str, Any] = {
        'KeyConditionExpression': _key_condition(owner, bounds),
        'ScanIndexForward': not descending
    }
    while True:
        response = table.query(**arguments)
        items.extend(response.get('Items', []))
        start_key = response.get('LastEvaluatedKey')
        if not start_key:
            break
        arguments['ExclusiveStartKey'] = start_key

    message = f'Query on {table_name} returned {len(items)} item(s).'
    logger.info(message)
    return from_dynamo(items)


def products_by_sku(
    dynamodb_resource: ServiceResource,
    owner: str
) -> Dict[str, Dict[str, Any]]:
    '''
        The catalogue keyed by SKU.

        One read serves a whole note: a query per line turned a basket of
        twelve items into twelve round trips before anything was charged.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.

        Returns:
            Dict[str, Dict[str, Any]]: {sku: product item}.
    '''
    return {row[PRODUCT_SORT_KEY]: row
            for row in read_partition(dynamodb_resource, PRODUCTS_TABLE, owner)}


def date_window(
    date_from: Optional[str],
    date_to: Optional[str]
) -> Optional[Dict[str, str]]:
    '''
        A pair of days as bounds on a document sort key.

        The key is "<timestamp>#<uuid>", so the upper bound has to sit after
        every stamp of its day — otherwise the last sales of the day fall
        outside their own window.

        Args:
            date_from (str | None): First day, ISO date.
            date_to (str | None): Last day, ISO date.

        Returns:
            Dict[str, str] | None: Bounds for `read_partition`, or None.
    '''
    if not date_from and not date_to:
        return None
    bounds: Dict[str, str] = {}
    if date_from:
        bounds['from'] = date_from
    if date_to:
        bounds['to'] = f'{date_to}T23:59:59\uffff'
    return bounds


# --- settings and numbering --------------------------------------------------

def get_settings(
    dynamodb_resource: ServiceResource,
    owner: str
) -> SettingsResponse:
    '''
        The pharmacy's own parameters, or SETTINGS_NOT_FOUND.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.

        Returns:
            SettingsResponse: Settings plus the current counters.

        Raises:
            RegisterNotFoundError: The pharmacy has not been set up yet.
    '''
    response = dynamodb_resource.Table(SETTINGS_TABLE).get_item(
        Key = {OWNER_KEY: owner, SETTING_SORT_KEY: CONFIG_KEY}
    )
    stored = from_dynamo(response.get('Item'))
    if not stored:
        raise RegisterNotFoundError(detail = PharmacyError.SETTINGS_NOT_FOUND.value)

    return SettingsResponse(
        **{key: value for key, value in stored.items()
           if key not in (OWNER_KEY, SETTING_SORT_KEY)},
        next_sale_number = _peek_counter(dynamodb_resource, owner, SALE_COUNTER_KEY),
        next_purchase_number = _peek_counter(dynamodb_resource, owner, PURCHASE_COUNTER_KEY)
    )


def save_settings(
    dynamodb_resource: ServiceResource,
    owner: str,
    settings: PharmacySettings
) -> SettingsResponse:
    '''
        Creates or replaces the pharmacy's parameters. Counters are not
        touched: renaming the shop must not restart its numbering.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            settings (PharmacySettings): Parameters as edited.

        Returns:
            SettingsResponse: What was stored.
    '''
    write_item(dynamodb_resource, SETTINGS_TABLE, {
        OWNER_KEY: owner, SETTING_SORT_KEY: CONFIG_KEY,
        **settings.model_dump(mode = 'json'), 'updated_at': now_iso()
    })
    message = f'Pharmacy settings stored for {owner}.'
    logger.info(message)
    return get_settings(dynamodb_resource, owner)


def _peek_counter(
    dynamodb_resource: ServiceResource,
    owner: str,
    counter_key: str
) -> int:
    '''
        The number the next document will take, without consuming it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            counter_key (str): Which counter.

        Returns:
            int: Next number, 1 when nothing was issued yet.
    '''
    response = dynamodb_resource.Table(SETTINGS_TABLE).get_item(
        Key = {OWNER_KEY: owner, SETTING_SORT_KEY: counter_key}
    )
    stored = from_dynamo(response.get('Item')) or {}
    return int(stored.get('last_number', 0)) + 1


def next_number(
    dynamodb_resource: ServiceResource,
    owner: str,
    counter_key: str,
    series: str
) -> str:
    '''
        Takes the next number of one counter, atomically.

        Each pharmacy numbers its own documents, and two tills selling at the
        same second must not both get number 41 — so the increment happens in
        DynamoDB and the caller is handed whatever came back.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            counter_key (str): Which counter.
            series (str): Prefix the pharmacy prints, e.g. "A".

        Returns:
            str: Formatted number, e.g. "A-000041".
    '''
    response = dynamodb_resource.Table(SETTINGS_TABLE).update_item(
        Key = {OWNER_KEY: owner, SETTING_SORT_KEY: counter_key},
        UpdateExpression = 'ADD last_number :one',
        ExpressionAttributeValues = {':one': 1},
        ReturnValues = 'UPDATED_NEW'
    )
    taken = int(from_dynamo(response['Attributes'])['last_number'])
    return f'{series}-{taken:06d}'


# --- catalogue ---------------------------------------------------------------

def create_product(
    dynamodb_resource: ServiceResource,
    owner: str,
    product: ProductIn
) -> ProductOut:
    '''
        Registers a SKU.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            product (ProductIn): The SKU as registered.

        Returns:
            ProductOut: The stored product, with no stock yet.

        Raises:
            RegisterAlreadyExistsError: The SKU is already in the catalogue.
    '''
    if _read_product(dynamodb_resource, owner, product.sku) is not None:
        raise RegisterAlreadyExistsError(detail = PharmacyError.SKU_ALREADY_EXISTS.value)

    stamp = now_iso()
    item = ProductItem(
        owner = owner, created_at = stamp, updated_at = stamp,
        **product.model_dump(mode = 'json')
    )
    write_item(dynamodb_resource, PRODUCTS_TABLE, item.__dict__)
    message = f'Product {product.sku} registered for {owner}.'
    logger.info(message)
    return ProductOut(**{key: value for key, value in item.__dict__.items()
                         if key != OWNER_KEY})


def update_product(
    dynamodb_resource: ServiceResource,
    owner: str,
    sku: str,
    patch: ProductPatch
) -> ProductOut:
    '''
        Changes what a SKU says about itself. The SKU is not among them.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sku (str): Product to change.
            patch (ProductPatch): Fields to change.

        Returns:
            ProductOut: The product after the change.

        Raises:
            RegisterNotFoundError: No such SKU in this pharmacy.
    '''
    stored = _read_product(dynamodb_resource, owner, sku)
    if stored is None:
        raise RegisterNotFoundError(detail = PharmacyError.PRODUCT_NOT_FOUND.value)

    changes = patch.model_dump(mode = 'json', exclude_none = True)
    stored.update(changes)
    stored['updated_at'] = now_iso()
    write_item(dynamodb_resource, PRODUCTS_TABLE, stored)
    message = f'Product {sku} of {owner} updated: {sorted(changes)}.'
    logger.info(message)
    return ProductOut(**{key: value for key, value in stored.items() if key != OWNER_KEY})


def list_products(
    dynamodb_resource: ServiceResource,
    owner: str,
    only_active: bool = False
) -> ProductsResponse:
    '''
        The catalogue with the stock its lots add up to.

        One query for the products and one for every lot of the pharmacy: the
        alternative — a query per SKU — turned a shelf of six hundred articles
        into six hundred round trips.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            only_active (bool): Leave out what was deactivated.

        Returns:
            ProductsResponse: Catalogue with availability.
    '''
    products = read_partition(dynamodb_resource, PRODUCTS_TABLE, owner)
    lots = read_partition(dynamodb_resource, LOTS_TABLE, owner)

    by_sku: Dict[str, List[Dict[str, Any]]] = {}
    for lot in lots:
        if lot.get('quantity_remaining', 0) > 0:
            by_sku.setdefault(lot['sku'], []).append(lot)

    items: List[ProductOut] = []
    for stored in sorted(products, key = lambda row: row[PRODUCT_SORT_KEY]):
        if only_active and not stored.get('is_active', True):
            continue
        items.append(_product_out(stored, by_sku.get(stored[PRODUCT_SORT_KEY], [])))

    return ProductsResponse(items = items, total = len(items))


def get_product(
    dynamodb_resource: ServiceResource,
    owner: str,
    sku: str
) -> ProductOut:
    '''
        One SKU with its availability.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sku (str): Product to read.

        Returns:
            ProductOut: The product.

        Raises:
            RegisterNotFoundError: No such SKU in this pharmacy.
    '''
    stored = _read_product(dynamodb_resource, owner, sku)
    if stored is None:
        raise RegisterNotFoundError(detail = PharmacyError.PRODUCT_NOT_FOUND.value)
    lots = [lot for lot in read_partition(
                dynamodb_resource, LOTS_TABLE, owner,
                bounds = SortBounds(sort_key = 'lot_key', begins_with = f'{sku}#'))
            if lot.get('quantity_remaining', 0) > 0]
    return _product_out(stored, lots)


def _read_product(
    dynamodb_resource: ServiceResource,
    owner: str,
    sku: str
) -> Optional[Dict[str, Any]]:
    '''
        The stored product item, or None.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The pharmacy.
            sku (str): Product to read.

        Returns:
            Dict[str, Any] | None: The item as stored.
    '''
    response = dynamodb_resource.Table(PRODUCTS_TABLE).get_item(
        Key = {OWNER_KEY: owner, PRODUCT_SORT_KEY: sku}
    )
    return from_dynamo(response.get('Item'))


def _product_out(
    stored: Dict[str, Any],
    lots: List[Dict[str, Any]]
) -> ProductOut:
    '''
        A stored product plus what its lots say about stock and price.

        Args:
            stored (Dict[str, Any]): The product item.
            lots (List[Dict[str, Any]]): Its lots with units left.

        Returns:
            ProductOut: The product as the API returns it.
    '''
    available = sum(lot['quantity_remaining'] for lot in lots)
    # The price that will actually be charged is the one on the batch that
    # leaves first, which is the one expiring soonest.
    ordered = sorted(lots, key = expiry_order)
    fields = {key: value for key, value in stored.items() if key != OWNER_KEY}
    fields.pop('available_quantity', None)
    return ProductOut(
        **fields,
        available_quantity = available,
        sale_price = ordered[0]['sale_price'] if ordered else None,
        next_expiry = ordered[0].get('expiry_date') if ordered else None,
        below_minimum = available < stored.get('min_stock', 0)
    )


def expiry_order(lot: Dict[str, Any]) -> tuple:
    '''
        Sort key for FEFO: soonest expiry first, and a batch with no expiry
        last — not first, because an unknown date must never jump ahead of a
        box that is about to expire.

        Args:
            lot (Dict[str, Any]): The lot item.

        Returns:
            tuple: (has no expiry, expiry date, reception time).
    '''
    expiry = lot.get('expiry_date')
    return (expiry is None, expiry or '', lot.get('received_at', ''))
