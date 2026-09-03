'''
    QUOTES support: DynamoDB access for the exchange-rate history.

    Keeps quotes.py free of plumbing. Nothing here decides anything about the
    business; it stores and reads what the domain asks for.
'''
import decimal
from datetime import date as date_type
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from models.quotes import (
    RATES_PARTITION_KEY,
    RATES_SORT_KEY,
    ExchangeRateItem
)
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger


ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_EXCHANGE_RATES': str,
})
RATES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_EXCHANGE_RATES']

# Region and credentials come from the default chain (Lambda role in AWS).
_resource = boto3.resource('dynamodb')


def _floats_to_decimal(value: Any) -> Any:
    '''
        Converts floats to Decimal, the only numeric type DynamoDB accepts.

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


def _table():
    '''
        Returns the exchange-rate table reference.

        Returns:
            Any: The boto3 table resource.

        Raises:
            ServiceUnavailableError: If the table cannot be reached.
    '''
    try:
        return _resource.Table(RATES_TABLE)
    except ClientError as error:
        error_msg = f'DynamoDB table "{RATES_TABLE}" is not reachable: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error


def get_rate(currency: str, day: date_type) -> Optional[ExchangeRateItem]:
    '''
        Returns the stored rate of one currency on one date.

        Args:
            currency (str): ISO 4217 code.
            day (date): Date of the rate.

        Returns:
            ExchangeRateItem | None: The rate, or None when it is not stored.
    '''
    try:
        response = _table().get_item(Key = {
            RATES_PARTITION_KEY: currency,
            RATES_SORT_KEY: day.isoformat(),
        })
    except ClientError as error:
        error_msg = f'Failed to read the rate of {currency} on {day}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error
    item = response.get('Item')
    return ExchangeRateItem.from_item(item) if item else None


def put_rate(rate: ExchangeRateItem) -> None:
    '''
        Stores one published rate.

        Args:
            rate (ExchangeRateItem): Record to store.

        Raises:
            ServiceUnavailableError: If DynamoDB rejects the write.
    '''
    try:
        _table().put_item(Item = _floats_to_decimal(rate.to_item()))
    except ClientError as error:
        error_msg = f'Failed to store the rate of {rate.currency} on {rate.date}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error


def query_rates(
    currency: str,
    start: Optional[date_type] = None,
    end: Optional[date_type] = None
) -> List[ExchangeRateItem]:
    '''
        Returns the stored rates of one currency, optionally within a window.

        This is the access pattern the table was keyed for: a Query on the
        partition with a range condition on the sort key.

        Args:
            currency (str): ISO 4217 code.
            start (date | None): First date to include.
            end (date | None): Last date to include.

        Returns:
            List[ExchangeRateItem]: Rates ordered by date.
    '''
    condition = Key(RATES_PARTITION_KEY).eq(currency)
    if start and end:
        condition = condition & Key(RATES_SORT_KEY).between(
            start.isoformat(), end.isoformat()
        )
    elif start:
        condition = condition & Key(RATES_SORT_KEY).gte(start.isoformat())
    elif end:
        condition = condition & Key(RATES_SORT_KEY).lte(end.isoformat())

    items: List[Dict[str, Any]] = []
    kwargs: Dict[str, Any] = {'KeyConditionExpression': condition}
    try:
        while True:
            response = _table().query(**kwargs)
            items.extend(response.get('Items', []))
            last_key = response.get('LastEvaluatedKey')
            if not last_key:
                break
            kwargs['ExclusiveStartKey'] = last_key
    except ClientError as error:
        error_msg = f'Failed to query the rates of {currency}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = error_msg) from error
    return [ExchangeRateItem.from_item(item) for item in items]
