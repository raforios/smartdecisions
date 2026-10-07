'''
    Daily stock — the company's units per SKU at the start of the day, drawn
    down by the sales sellers register on their visits.

    The draw-down is a single DynamoDB transaction over every SKU of the sale
    with a condition on each ("available >= this"), so a sale either fits
    entirely or is refused entirely, and two sellers selling the last units
    at the same moment cannot both succeed.
'''

from boto3.resources.base import ServiceResource
from botocore.exceptions import ClientError

from models.daily_stock import DailyStockItem
from schemas.daily_stock import (
    DailyStockFromIngestSchema,
    DailyStockLoadSchema,
    DailyStockResponseSchema,
    SaleItemSchema,
    StockError,
    StockItemLoadSchema,
    StockItemResponseSchema
)
from services.common import from_dynamo, now_iso, to_dynamo
from services.crud import query_by_partition
from services.environment import load_and_validate_env_vars
from services.exceptions import (
    InvalidInputError,
    ResourceNotFoundError,
    ServiceUnavailableError
)
from services.ingest_directory import ingest_get
from services.logger_config import custom_logger as logger

_SETTINGS = load_and_validate_env_vars({'DYNAMODB_TABLE_NAME_OPTIMIZATION_DAILY_STOCK': str})
DAILY_STOCK_TABLE = _SETTINGS['DYNAMODB_TABLE_NAME_OPTIMIZATION_DAILY_STOCK']


def build_stock_key(
    day: str,
    sku: str
) -> str:
    '''
        Sort key of a stock row.

        Args:
            day (str): YYYY-MM-DD.
            sku (str): Product code.

        Returns:
            str: "{day}#{sku}".
    '''
    return f'{day}#{sku}'


def to_stock_item_response(item: DailyStockItem) -> StockItemResponseSchema:
    '''
        Stock item -> DTO.

        Args:
            item (DailyStockItem): Stored row.

        Returns:
            StockItemResponseSchema: The row as the API returns it.
    '''
    return StockItemResponseSchema(
        date = item['date'],
        sku = item['sku'],
        product_name = item.get('product_name'),
        opening_quantity = item['opening_quantity'],
        sold_quantity = item['sold_quantity'],
        available_quantity = item['available_quantity'],
        updated_at = item['updated_at']
    )


def to_daily_stock_response(
    day: str,
    items: list[DailyStockItem]
) -> DailyStockResponseSchema:
    '''
        The day's rows -> DTO with the two counts the screen shows first.

        Args:
            day (str): YYYY-MM-DD.
            items (list[DailyStockItem]): Stored rows of that day.

        Returns:
            DailyStockResponseSchema: The day's stock.
    '''
    rows = [to_stock_item_response(item) for item in sorted(items, key = lambda row: row['sku'])]
    return DailyStockResponseSchema(
        date = day,
        items = rows,
        skus_loaded = len(rows),
        skus_out_of_stock = sum(1 for row in rows if row.available_quantity <= 0)
    )


def get_daily_stock(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    day: str
) -> list[DailyStockItem]:
    '''
        Every SKU loaded for the owner on `day`.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            day (str): YYYY-MM-DD.

        Returns:
            list[DailyStockItem]: Rows with native numbers.
    '''
    items = query_by_partition(
        dynamodb_resource = dynamodb_resource,
        table_name = DAILY_STOCK_TABLE,
        partition_key = 'owner_email',
        partition_value = owner_email,
        sort_key = 'stock_key',
        sort_between = {'from': f'{day}#', 'to': f'{day}#~'}
    )
    return from_dynamo(items)


def load_daily_stock(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    load: DailyStockLoadSchema
) -> list[DailyStockItem]:
    '''
        Loads the day's opening stock, replacing whatever the day had: the
        previous rows go first, so a SKU dropped from the new load disappears.
        Sales already registered that day are kept for the SKUs still present.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            load (DailyStockLoadSchema): Date and items.

        Returns:
            list[DailyStockItem]: The rows as stored.

        Raises:
            InvalidInputError: DUPLICATE_SKU when a SKU repeats in the load.
    '''
    skus = [item.sku for item in load.items]
    if len(set(skus)) != len(skus):
        error_msg = f'Stock load for {load.date} repeats a SKU.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = StockError.DUPLICATE_SKU.value)

    previous = {row['sku']: row
                for row in get_daily_stock(dynamodb_resource, owner_email, load.date)}
    stamp = now_iso()
    rows: list[DailyStockItem] = []
    for item in load.items:
        sold = previous.get(item.sku, {}).get('sold_quantity', 0)
        rows.append({
            'owner_email': owner_email,
            'stock_key': build_stock_key(load.date, item.sku),
            'date': load.date,
            'sku': item.sku,
            'product_name': item.product_name,
            'opening_quantity': item.quantity,
            'sold_quantity': sold,
            'available_quantity': item.quantity - sold,
            'updated_at': stamp
        })
    table = dynamodb_resource.Table(DAILY_STOCK_TABLE)
    with table.batch_writer() as batch:
        for sku, row in previous.items():
            if sku not in set(skus):
                batch.delete_item(Key = {'owner_email': owner_email, 'stock_key': row['stock_key']})
        for row in rows:
            batch.put_item(Item = to_dynamo(row))
    message = f'Daily stock for {load.date} loaded: {len(rows)} SKU(s), {len(previous)} replaced.'
    logger.info(message)
    return rows


def _merge_sale_lines(items: list[SaleItemSchema]) -> dict[str, float]:
    '''
        Units per SKU, adding repeated lines together.
    '''
    merged: dict[str, float] = {}
    for line in items:
        merged[line.sku] = merged.get(line.sku, 0.0) + line.quantity
    return merged


def draw_down_stock(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    day: str,
    items: list[SaleItemSchema]
) -> None:
    '''
        Registers a sale against the day's stock, all SKUs or none.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            day (str): YYYY-MM-DD of the sale.
            items (list[SaleItemSchema]): Lines sold.

        Raises:
            InvalidInputError: STOCK_NOT_LOADED when a SKU has no row that day,
                INSUFFICIENT_STOCK when the units are not there.
    '''
    if not items:
        return
    merged = _merge_sale_lines(items)
    stamp = now_iso()
    actions = [
        {
            'Update': {
                'TableName': DAILY_STOCK_TABLE,
                'Key': to_dynamo({'owner_email': owner_email,
                                  'stock_key': build_stock_key(day, sku)}),
                'UpdateExpression': 'SET sold_quantity = sold_quantity + :units, '
                                    'available_quantity = available_quantity - :units, '
                                    'updated_at = :stamp',
                'ConditionExpression': 'attribute_exists(stock_key) '
                                       'AND available_quantity >= :units',
                'ExpressionAttributeValues': to_dynamo({':units': units, ':stamp': stamp})
            }
        }
        for sku, units in merged.items()
    ]
    try:
        dynamodb_resource.meta.client.transact_write_items(TransactItems = actions)
    except ClientError as error:
        if error.response['Error']['Code'] != 'TransactionCanceledException':
            raise
        loaded = {row['sku'] for row in get_daily_stock(dynamodb_resource, owner_email, day)}
        missing = sorted(sku for sku in merged if sku not in loaded)
        error_msg = (
            f'Sale refused on {day}: missing SKUs {missing}; requested {merged}.'
            if missing else f'Sale refused on {day}: not enough units for {merged}.'
        )
        logger.warning(error_msg)
        code = StockError.STOCK_NOT_LOADED if missing else StockError.INSUFFICIENT_STOCK
        raise InvalidInputError(detail = code.value) from error
    message = f'Sale drawn from stock of {day}: {merged}.'
    logger.info(message)


def fetch_stock_from_ingest(
    source: DailyStockFromIngestSchema,
    auth_token: str
) -> DailyStockLoadSchema:
    '''
        The day's opening stock, asked of INGEST, which owns the stock file.

        The company fills one stock template and both modules read it: the
        analysis for coverage, the route for what a seller can still sell. What
        opens the day is `available` —on hand minus what the ERP already
        committed— because a box promised to someone else is not on the truck.

        The caller's token is forwarded so INGEST answers for the real user and
        applies its own ownership rule.

        Args:
            source (DailyStockFromIngestSchema): Dataset and day to open.
            auth_token (str): The caller's Authorization header.

        Returns:
            DailyStockLoadSchema: The day, ready for `load_daily_stock`.

        Raises:
            ResourceNotFoundError: NO_STOCK_FOR_DAY when INGEST holds nothing
                for that dataset and day.
            ServiceUnavailableError: STOCK_SOURCE_UNAVAILABLE when INGEST
                cannot be reached or refuses.
    '''
    response = ingest_get(
        f'/v1/ingest/{source.dataset_id}/stock', auth_token, {'date': source.date},
        StockError.STOCK_SOURCE_UNAVAILABLE.value
    )
    if response.status_code == 404:
        error_msg = (f'INGEST holds no stock for dataset {source.dataset_id} '
                     f'on {source.date}: {response.text[:200]}')
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = StockError.NO_STOCK_FOR_DAY.value)
    if not response.ok:
        error_msg = (f'INGEST refused the stock of {source.date}: '
                     f'status={response.status_code} body={response.text[:200]}')
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = StockError.STOCK_SOURCE_UNAVAILABLE.value)

    items = (response.json() or {}).get('items') or []
    return DailyStockLoadSchema(
        date = source.date,
        items = [
            StockItemLoadSchema(
                sku = item['product_id'],
                product_name = item.get('product_name'),
                quantity = item['available']
            )
            for item in items
        ]
    )
