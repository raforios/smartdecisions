'''
    DynamoDB data access for the quotations tables.

    Sibling of crud.py, which stays as the relational access layer: this module
    is used when the service is configured to run on DynamoDB. It deliberately
    covers only minerals and prices — the quotations data SmartDecisions
    consumes. Royalties and the rest keep working on the relational side.

    Follows the same shape as the CRUD of the ANALYTICS and EVENTS services:
    thin functions over boto3, float-to-Decimal conversion on write, and errors
    surfaced as ServiceUnavailableError.
'''
import decimal
from datetime import date as date_type
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from models.mining_analysis_dyb import (
    MINERALS_TABLE_KEY,
    PRICES_PARTITION_KEY,
    PRICES_SORT_KEY,
    MineralItem,
    MiningPriceItem
)
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger


ENV_VARS = load_and_validate_env_vars({}, optional_env_vars = {
    'DYNAMODB_TABLE_NAME_MINERALS': str,
    'DYNAMODB_TABLE_NAME_MINING_PRICES': str,
})
# Defaults without the 't_' prefix: that prefix names the MySQL tables, and
# every DynamoDB table in the account goes without it.
MINERALS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_MINERALS'] or 'minerals'
PRICES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_MINING_PRICES'] or 'mining_prices'

# Region and credentials come from the default chain (Lambda role in AWS).
_resource = boto3.resource('dynamodb')


def _floats_to_decimal(value: Any) -> Any:
    '''
        Converts floats to Decimal, which is the only numeric type DynamoDB
        accepts.

        Args:
            value (Any): Value, possibly nested, to convert.

        Returns:
            Any: The same structure with every float turned into Decimal.
    '''
    if isinstance(value, float):
        return decimal.Decimal(str(value))
    if isinstance(value, dict):
        return {key: _floats_to_decimal(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_floats_to_decimal(item) for item in value]
    return value


def _table(name: str):
    '''
        Returns a table reference.

        Args:
            name (str): Table name.

        Returns:
            Any: The boto3 table resource.

        Raises:
            ServiceUnavailableError: If the table cannot be reached.
    '''
    try:
        return _resource.Table(name)
    except ClientError as error:
        error_msg = f'DynamoDB table "{name}" is not reachable: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error


def list_minerals() -> List[MineralItem]:
    '''
        Returns the whole mineral catalogue.

        A scan is deliberate: the catalogue holds a handful of rows, so an index
        would cost more to maintain than the scan costs to run.

        Returns:
            List[MineralItem]: Every mineral on record.
    '''
    try:
        response = _table(MINERALS_TABLE).scan()
    except ClientError as error:
        error_msg = f'Failed to scan {MINERALS_TABLE}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error
    return [MineralItem.from_item(item) for item in response.get('Items', [])]


def put_mineral(mineral: MineralItem) -> None:
    '''
        Writes one mineral of the catalogue.

        Args:
            mineral (MineralItem): Record to store.

        Raises:
            ServiceUnavailableError: If DynamoDB rejects the write.
    '''
    item = {
        MINERALS_TABLE_KEY: mineral.mineral_id,
        'name': mineral.name,
        'unit': mineral.unit,
        'chemical_symbol': mineral.chemical_symbol,
        'quoted_in': mineral.quoted_in,
        'method': mineral.method,
        'created_at': mineral.created_at,
    }
    try:
        _table(MINERALS_TABLE).put_item(Item = _floats_to_decimal(item))
    except ClientError as error:
        error_msg = f'Failed to write mineral {mineral.mineral_id}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error


def get_price(mineral_id: str, day: date_type) -> Optional[MiningPriceItem]:
    '''
        Returns the quotation of one mineral on one date.

        Args:
            mineral_id (str): Mineral identifier.
            day (date): Date of the quotation.

        Returns:
            MiningPriceItem | None: The quotation, or None when absent.
    '''
    try:
        response = _table(PRICES_TABLE).get_item(Key = {
            PRICES_PARTITION_KEY: mineral_id,
            PRICES_SORT_KEY: day.isoformat(),
        })
    except ClientError as error:
        error_msg = f'Failed to read price {mineral_id} {day}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error
    item = response.get('Item')
    return MiningPriceItem.from_item(item) if item else None


def put_price(price: MiningPriceItem) -> None:
    '''
        Writes one quotation.

        Args:
            price (MiningPriceItem): Record to store.

        Raises:
            ServiceUnavailableError: If DynamoDB rejects the write.
    '''
    try:
        _table(PRICES_TABLE).put_item(Item = _floats_to_decimal(price.to_item()))
    except ClientError as error:
        error_msg = f'Failed to write price {price.mineral_id} {price.date}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error


def query_prices(
    mineral_id: str,
    start: Optional[date_type] = None,
    end: Optional[date_type] = None,
    descending: bool = False
) -> List[MiningPriceItem]:
    '''
        Returns the quotations of one mineral, optionally within a window.

        This is the access pattern the table was keyed for: a Query on the
        partition with a range condition on the sort key.

        Args:
            mineral_id (str): Mineral identifier.
            start (date | None): First date to include.
            end (date | None): Last date to include.
            descending (bool): Walk the partition newest first. The daily report
                only wants the last two quotations, so reading backwards lets
                the caller stop early instead of pulling the whole history.

        Returns:
            List[MiningPriceItem]: Quotations ordered by date, newest first when
                `descending` is set.
    '''
    condition = Key(PRICES_PARTITION_KEY).eq(mineral_id)
    if start and end:
        condition = condition & Key(PRICES_SORT_KEY).between(
            start.isoformat(), end.isoformat()
        )
    elif start:
        condition = condition & Key(PRICES_SORT_KEY).gte(start.isoformat())
    elif end:
        condition = condition & Key(PRICES_SORT_KEY).lte(end.isoformat())

    items: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {'KeyConditionExpression': condition}
    if descending:
        kwargs['ScanIndexForward'] = False
    try:
        while True:
            response = _table(PRICES_TABLE).query(**kwargs)
            items.extend(response.get('Items', []))
            last_key = response.get('LastEvaluatedKey')
            if not last_key:
                break
            kwargs['ExclusiveStartKey'] = last_key
    except ClientError as error:
        error_msg = f'Failed to query prices of {mineral_id}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error
    return [MiningPriceItem.from_item(item) for item in items]


def scan_prices() -> List[MiningPriceItem]:
    '''
        Returns every quotation on record.

        Only used by the full export; the day-to-day reads go through
        query_prices, which never scans.

        Returns:
            List[MiningPriceItem]: Every quotation.
    '''
    items: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {}
    try:
        while True:
            response = _table(PRICES_TABLE).scan(**kwargs)
            items.extend(response.get('Items', []))
            last_key = response.get('LastEvaluatedKey')
            if not last_key:
                break
            kwargs['ExclusiveStartKey'] = last_key
    except ClientError as error:
        error_msg = f'Failed to scan {PRICES_TABLE}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error
    return [MiningPriceItem.from_item(item) for item in items]


def put_prices_batch(prices: List[MiningPriceItem]) -> int:
    '''
        Writes many quotations in batches.

        One put_item per quotation costs a round trip each, which turns a
        migration of a few hundred rows into minutes of waiting. DynamoDB's
        batch writer groups them and retries what the service throttles.

        Args:
            prices (List[MiningPriceItem]): Quotations to store.

        Returns:
            int: How many quotations were written.

        Raises:
            ServiceUnavailableError: If the table cannot be written to.
    '''
    if not prices:
        # Nothing to write: opening a batch writer for an empty list would only
        # reach for the table resource to do nothing with it.
        return 0

    try:
        with _table(PRICES_TABLE).batch_writer() as batch:
            for price in prices:
                batch.put_item(Item = _floats_to_decimal(price.to_item()))
    except ClientError as error:
        error_msg = f'Failed to batch-write into {PRICES_TABLE}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error
    return len(prices)
