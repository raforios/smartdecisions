'''
    DynamoDB access for the quotations: the mineral catalogue, the official
    daily prices, the market prices read from the public sources and the
    Art. 227 royalty scales.

    Every function receives the boto3 resource the route resolved through
    `GET_DB_DEPENDENCY`, like every other service of the product: the module
    owns no connection of its own, which is what makes it testable and what
    the boilerplate asks for.

    Key design, driven by how the data is read:
      minerals / mining_royalty_rules   PK: mineral_id (S)
          A handful of rows read whole; a scan is cheaper than an index.
      mining_prices / mining_market_prices
          PK: mineral_id (S)  SK: date (S, ISO 'YYYY-MM-DD')
          Every read is "this mineral over this window": a Query on the
          partition bounded by the sort key. The market series lives in its
          own table so the official history is never mixed with a proxy.
'''
from datetime import date as date_type
from typing import Any, Dict, List, Optional

from boto3.resources.base import ServiceResource

from models.market_prices import (
    MARKET_PARTITION_KEY,
    MARKET_SORT_KEY,
    RULES_TABLE_KEY,
    MarketPriceItem,
    RoyaltyRuleItem
)
from models.mining_analysis_dyb import (
    MINERALS_TABLE_KEY,
    PRICES_PARTITION_KEY,
    PRICES_SORT_KEY,
    MineralItem,
    MiningPriceItem
)
from services.crud import _convert_floats_to_decimals, find_item_by_key, query_by_partition
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_MINERALS': str,
    'DYNAMODB_TABLE_NAME_MINING_PRICES': str,
    'DYNAMODB_TABLE_NAME_MINING_MARKET_PRICES': str,
    'DYNAMODB_TABLE_NAME_MINING_ROYALTY_RULES': str
})
MINERALS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_MINERALS']
PRICES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_MINING_PRICES']
MARKET_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_MINING_MARKET_PRICES']
RULES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_MINING_ROYALTY_RULES']


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------
def _scan(
    dynamodb_resource: ServiceResource,
    table_name: str
) -> List[Dict[str, Any]]:
    '''
        Every item of a small table. Deliberate on the catalogue and on the
        royalty scales: a handful of rows, where an index would cost more to
        maintain than the scan costs to run. The shared CRUD has no scan
        because no other service needs one.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Table to read whole.

        Returns:
            List[Dict[str, Any]]: Every item.
    '''
    table = dynamodb_resource.Table(table_name)
    items: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {}
    while True:
        response = table.scan(**kwargs)
        items.extend(response.get('Items', []))
        if not response.get('LastEvaluatedKey'):
            break
        kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
    return items


def _write(
    dynamodb_resource: ServiceResource,
    table_name: str,
    items: List[Dict[str, Any]]
) -> int:
    '''
        Writes items in one batch, replacing any row with the same key.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Target table.
            items (List[Dict[str, Any]]): Items to write.

        Returns:
            int: How many were written.
    '''
    if not items:
        return 0
    table = dynamodb_resource.Table(table_name)
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item = _convert_floats_to_decimals(item))
    return len(items)


def list_minerals(dynamodb_resource: ServiceResource) -> List[MineralItem]:
    '''
        The whole mineral catalogue.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            List[MineralItem]: Every mineral on record.
    '''
    return [MineralItem.from_item(item)
            for item in _scan(dynamodb_resource, MINERALS_TABLE)]


def put_mineral(
    dynamodb_resource: ServiceResource,
    mineral: MineralItem
) -> None:
    '''
        Writes one mineral of the catalogue.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            mineral (MineralItem): Record to store.
    '''
    item = {
        MINERALS_TABLE_KEY: mineral.mineral_id,
        'name': mineral.name,
        'unit': mineral.unit,
        'chemical_symbol': mineral.chemical_symbol,
        'quoted_in': mineral.quoted_in,
        'method': mineral.method,
        'created_at': mineral.created_at
    }
    _write(dynamodb_resource, MINERALS_TABLE, [item])


# ---------------------------------------------------------------------------
# Official daily prices
# ---------------------------------------------------------------------------
def get_price(
    dynamodb_resource: ServiceResource,
    mineral_id: str,
    day: date_type
) -> Optional[MiningPriceItem]:
    '''
        The official quotation of one mineral on one date.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            mineral_id (str): Mineral identifier.
            day (date): Date of the quotation.

        Returns:
            MiningPriceItem | None: The quotation, or None when absent.
    '''
    item = find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = PRICES_TABLE,
        key = {PRICES_PARTITION_KEY: mineral_id, PRICES_SORT_KEY: day.isoformat()}
    )
    return MiningPriceItem.from_item(item) if item else None


def query_prices(
    dynamodb_resource: ServiceResource,
    mineral_id: str,
    window: Optional[Dict[str, date_type]] = None,
    descending: bool = False
) -> List[MiningPriceItem]:
    '''
        The official quotations of one mineral, optionally within a window.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            mineral_id (str): Mineral identifier.
            window (Dict[str, date] | None): 'from' and/or 'to', inclusive.
            descending (bool): Walk the partition newest first, so a caller
                that only wants the last quotations stops early.

        Returns:
            List[MiningPriceItem]: Quotations by date, newest first when
                `descending` is set.
    '''
    items = query_by_partition(
        dynamodb_resource = dynamodb_resource,
        table_name = PRICES_TABLE,
        partition_key = PRICES_PARTITION_KEY,
        partition_value = mineral_id,
        sort_key = PRICES_SORT_KEY,
        sort_between = _bounds(window)
    )
    quotations = [MiningPriceItem.from_item(item) for item in items]
    # The shared Query returns the partition ascending. A mineral holds a few
    # hundred daily rows, so reversing here costs nothing and keeps the CRUD
    # contract untouched.
    return list(reversed(quotations)) if descending else quotations


def scan_prices(dynamodb_resource: ServiceResource) -> List[MiningPriceItem]:
    '''
        Every official quotation on record. Only the full export needs this;
        the day-to-day reads go through `query_prices`.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            List[MiningPriceItem]: Every quotation.
    '''
    return [MiningPriceItem.from_item(item)
            for item in _scan(dynamodb_resource, PRICES_TABLE)]


def put_prices_batch(
    dynamodb_resource: ServiceResource,
    prices: List[MiningPriceItem]
) -> int:
    '''
        Writes many official quotations at once.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            prices (List[MiningPriceItem]): Quotations to store.

        Returns:
            int: How many were written.
    '''
    return _write(dynamodb_resource, PRICES_TABLE, [price.to_item() for price in prices])


def put_price(
    dynamodb_resource: ServiceResource,
    price: MiningPriceItem
) -> None:
    '''
        Writes one official quotation.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            price (MiningPriceItem): Record to store.
    '''
    put_prices_batch(dynamodb_resource, [price])


# ---------------------------------------------------------------------------
# Market prices and royalty scales
# ---------------------------------------------------------------------------
def query_market_prices(
    dynamodb_resource: ServiceResource,
    mineral_id: str,
    window: Optional[Dict[str, date_type]] = None
) -> List[MarketPriceItem]:
    '''
        The market prices of one mineral, oldest first, optionally in a window.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            mineral_id (str): Catalogue id.
            window (Dict[str, date] | None): 'from' and/or 'to', inclusive.

        Returns:
            List[MarketPriceItem]: Prices ordered by date.
    '''
    items = query_by_partition(
        dynamodb_resource = dynamodb_resource,
        table_name = MARKET_TABLE,
        partition_key = MARKET_PARTITION_KEY,
        partition_value = mineral_id,
        sort_key = MARKET_SORT_KEY,
        sort_between = _bounds(window)
    )
    return [MarketPriceItem.from_item(item) for item in items]


def put_market_prices(
    dynamodb_resource: ServiceResource,
    prices: List[MarketPriceItem]
) -> int:
    '''
        Writes market prices, replacing any row of the same day.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            prices (List[MarketPriceItem]): Rows to write.

        Returns:
            int: Rows written.
    '''
    written = _write(dynamodb_resource, MARKET_TABLE, [price.to_item() for price in prices])
    if written:
        message = f'Wrote {written} market price(s) to {MARKET_TABLE}.'
        logger.info(message)
    return written


def list_royalty_rules(dynamodb_resource: ServiceResource) -> List[RoyaltyRuleItem]:
    '''
        Every Art. 227 scale stored, by mineral id.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            List[RoyaltyRuleItem]: The scales.
    '''
    rules = [RoyaltyRuleItem.from_item(item)
             for item in _scan(dynamodb_resource, RULES_TABLE)]
    return sorted(rules, key = lambda rule: (int(rule.mineral_id) if rule.mineral_id.isdigit()
                                             else 0))


def get_royalty_rule(
    dynamodb_resource: ServiceResource,
    mineral_id: str
) -> Optional[RoyaltyRuleItem]:
    '''
        One scale, or None.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            mineral_id (str): Catalogue id.

        Returns:
            Optional[RoyaltyRuleItem]: The rule when stored.
    '''
    item = find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = RULES_TABLE,
        key = {RULES_TABLE_KEY: mineral_id}
    )
    return RoyaltyRuleItem.from_item(item) if item else None


def put_royalty_rule(
    dynamodb_resource: ServiceResource,
    rule: RoyaltyRuleItem
) -> None:
    '''
        Creates or replaces one scale.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            rule (RoyaltyRuleItem): The scale.
    '''
    _write(dynamodb_resource, RULES_TABLE, [rule.to_item()])
    message = f'Royalty rule for mineral {rule.mineral_id} stored ({RULES_TABLE}).'
    logger.info(message)


def _bounds(window: Optional[Dict[str, date_type]]) -> Optional[Dict[str, str]]:
    '''
        A date window as the ISO strings the sort key is compared against.

        Args:
            window (Dict[str, date] | None): 'from' and/or 'to'.

        Returns:
            Dict[str, str] | None: The same bounds as text, or None.
    '''
    if not window:
        return None
    bounds: Dict[str, Any] = {}
    for edge in ('from', 'to'):
        if window.get(edge):
            bounds[edge] = window[edge].isoformat()
    return bounds or None
