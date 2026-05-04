'''
    CRUD Service
'''
import json
import decimal
from typing import Any, Dict, List, Optional
from boto3.resources.base import ServiceResource
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError as AWSClientError
from services.logger_config import custom_logger as logger
from services.exceptions import RegisterAlreadyExistsError, RegisterNotFoundError

TABLE_SCHEMA = {
    'audit_records': {'pk': 'id', 'sk': 'sk', 'index': 'sk-pk-index'},
    'usage_logs': {'pk': 'id', 'sk': 'sk', 'index': 'sk-pk-index'},
}

def _convert_floats_to_decimals(data: Any) -> Any:
    '''
        Recursively converts all float values in a dictionary or list
        to Decimal objects for DynamoDB compatibility.
    '''
    if isinstance(data, float):
        return decimal.Decimal(str(data))
    if isinstance(data, dict):
        return {k: _convert_floats_to_decimals(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_convert_floats_to_decimals(v) for v in data]
    return data

def create_item(
    dynamodb_resource: ServiceResource,
    table_name: str,
    item_data: Dict[str, Any],
    unique_key_attribute: str
) -> Dict[str, Any]:
    '''
        Adds a new item to a DynamoDB table, enforcing uniqueness on the
        partition-key attribute supplied by the caller.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Target DynamoDB table.
            item_data (Dict[str, Any]): Item to insert.
            unique_key_attribute (str): Attribute used to enforce uniqueness via
                an 'attribute_not_exists' condition (typically the partition key).

        Returns:
            Dict[str, Any]: The persisted item.

        Raises:
            RegisterAlreadyExistsError: If an item with the same key already exists.
    '''
    try:
        table = dynamodb_resource.Table(table_name)

        item_data_processed = _convert_floats_to_decimals(item_data)

        table.put_item(
            Item = item_data_processed,
            ConditionExpression = f'attribute_not_exists({unique_key_attribute})'
        )
        message = f'Item added successfully to {table_name}.'
        logger.info(message)
        return item_data_processed
    except AWSClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            error_msg = (
                f'Item with {unique_key_attribute}='
                f'{item_data.get(unique_key_attribute)} already exists.'
            )
            logger.warning(error_msg, exc_info = True)
            raise RegisterAlreadyExistsError(detail = error_msg) from e
        error_msg = f'Error adding item to {table_name}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def get_item_by_id(
    dynamodb_resource: ServiceResource,
    table_name: str,
    item_id: str
) -> Dict[str, Any]:
    '''
        Retrieves an item from a DynamoDB table by its ID.
    '''
    table = dynamodb_resource.Table(table_name)
    response = table.get_item(
        Key={
            'id': item_id
        }
    )
    item = response.get('Item')
    if not item:
        error_msg = f'Item with id {item_id} not found in {table_name}.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = error_msg)

    message = f'Item with id {item_id} retrieved successfully.'
    logger.info(message)
    return item

def get_all_records_paginated(
    dynamodb_resource: ServiceResource,
    table_name: str,
    query_params: Dict[str, Any],
) -> Dict[str, Any]:
    '''
        Retrieves all items from a DynamoDB table with optional pagination and filters.
    '''
    try:
        table = dynamodb_resource.Table(table_name)
        scan_kwargs = {'Limit': query_params.get('limit', 100)}

        filters = {k: v for k, v in query_params.items() if v is not None and k \
            not in ['limit', 'last_evaluated_key']}

        if filters:
            filter_expressions = [Attr(key).eq(value) for key, value in filters.items()]
            combined_expression = filter_expressions[0]
            for expr in filter_expressions[1:]:
                combined_expression &= expr
            scan_kwargs['FilterExpression'] = combined_expression

        if 'last_evaluated_key' in query_params and query_params['last_evaluated_key']:
            scan_kwargs['ExclusiveStartKey'] = json.loads(query_params['last_evaluated_key'])

        response = table.scan(**scan_kwargs)

        last_evaluated_key_json = json.dumps(response.get('LastEvaluatedKey'),
                    separators=(',', ':')) if response.get('LastEvaluatedKey') else None

        message = f'Retrieved {len(response.get("Items", []))} records from {table_name}.'
        logger.info(message)

        return {
            'items': response.get('Items', []),
            'last_evaluated_key': last_evaluated_key_json
        }

    except AWSClientError as e:
        error_msg = f'Error retrieving all items from {table_name}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except json.JSONDecodeError as e:
        logger.error('Invalid JSON format for last_evaluated_key.', exc_info = True)
        raise e


# ----------------------------------------------------------------------------
# Boilerplate extensions (added 2026-05-04 for the Mining Summit service).
#
# The functions below complement the original CRUD primitives with helpers
# required by services that do not key items by 'id':
#
#   * get_item_by_key             - generic version of get_item_by_id that
#                                   accepts an arbitrary primary key dict
#                                   (single or composite).
#   * find_item_by_key            - same as above but returns None instead of
#                                   raising RegisterNotFoundError, useful for
#                                   "exists?" checks.
#   * put_unique_composite_item   - inserts an item enforcing uniqueness on a
#                                   (partition_key, sort_key) tuple.
#   * query_by_partition          - efficient Query (no Scan) by partition
#                                   value, with optional sort-key range.
#
# These helpers are generic and reusable; any other DynamoDB-backed service
# can adopt them without modifying the original CRUD primitives above.
# ----------------------------------------------------------------------------


def get_item_by_key(
    dynamodb_resource: ServiceResource,
    table_name: str,
    key: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Retrieves an item from a DynamoDB table by its primary key (single or
        composite). Raises RegisterNotFoundError if the item does not exist.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Target DynamoDB table.
            key (Dict[str, Any]): Primary key mapping (e.g., {'ci': '123'} or
                {'ci': '123', 'attendance_date': '2026-05-04'}).

        Returns:
            Dict[str, Any]: The retrieved item.
    '''
    table = dynamodb_resource.Table(table_name)
    response = table.get_item(Key = key)
    item = response.get('Item')
    if not item:
        error_msg = f'Item with key {key} not found in {table_name}.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = error_msg)
    message = f'Item with key {key} retrieved successfully from {table_name}.'
    logger.info(message)
    return item


def find_item_by_key(
    dynamodb_resource: ServiceResource,
    table_name: str,
    key: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    '''
        Retrieves an item from a DynamoDB table by its primary key, returning
        None if the item does not exist (no exception is raised).

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Target DynamoDB table.
            key (Dict[str, Any]): Primary key mapping.

        Returns:
            Optional[Dict[str, Any]]: The retrieved item or None.
    '''
    table = dynamodb_resource.Table(table_name)
    response = table.get_item(Key = key)
    return response.get('Item')


def put_unique_composite_item(
    dynamodb_resource: ServiceResource,
    table_name: str,
    item_data: Dict[str, Any],
    partition_key: str,
    sort_key: str
) -> Dict[str, Any]:
    '''
        Inserts an item into a composite-key DynamoDB table enforcing
        uniqueness on the (partition_key, sort_key) tuple.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Target DynamoDB table.
            item_data (Dict[str, Any]): Item to insert.
            partition_key (str): Partition key attribute name.
            sort_key (str): Sort key attribute name.

        Returns:
            Dict[str, Any]: The persisted item.

        Raises:
            RegisterAlreadyExistsError: If a record with the same composite
                key already exists.
    '''
    try:
        table = dynamodb_resource.Table(table_name)
        item_data_processed = _convert_floats_to_decimals(item_data)

        table.put_item(
            Item = item_data_processed,
            ConditionExpression = (
                f'attribute_not_exists({partition_key}) '
                f'AND attribute_not_exists({sort_key})'
            )
        )
        message = f'Composite item added successfully to {table_name}.'
        logger.info(message)
        return item_data_processed
    except AWSClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            error_msg = (
                f'Item with {partition_key}={item_data.get(partition_key)} '
                f'and {sort_key}={item_data.get(sort_key)} already exists '
                f'in {table_name}.'
            )
            logger.warning(error_msg, exc_info = True)
            raise RegisterAlreadyExistsError(detail = error_msg) from e
        error_msg = f'Error adding composite item to {table_name}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e


def query_by_partition(
    dynamodb_resource: ServiceResource,
    table_name: str,
    partition_key: str,
    partition_value: str,
    sort_key: Optional[str] = None,
    sort_between: Optional[Dict[str, str]] = None
) -> List[Dict[str, Any]]:
    '''
        Performs an efficient Query (not Scan) on a composite-key table by
        partition value, optionally bounding the sort key.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Target DynamoDB table.
            partition_key (str): Partition key attribute name.
            partition_value (str): Partition key value to match.
            sort_key (Optional[str]): Sort key attribute name (when bounding).
            sort_between (Optional[Dict[str, str]]): Bounds for the sort key,
                accepting 'from' and/or 'to' (inclusive).

        Returns:
            List[Dict[str, Any]]: Matched items.
    '''
    table = dynamodb_resource.Table(table_name)
    key_condition = Key(partition_key).eq(partition_value)

    if sort_key and sort_between:
        date_from = sort_between.get('from')
        date_to = sort_between.get('to')
        if date_from and date_to:
            key_condition = key_condition & Key(sort_key).between(date_from, date_to)
        elif date_from:
            key_condition = key_condition & Key(sort_key).gte(date_from)
        elif date_to:
            key_condition = key_condition & Key(sort_key).lte(date_to)

    response = table.query(KeyConditionExpression = key_condition)
    items = response.get('Items', [])
    message = f'Query on {table_name} returned {len(items)} item(s).'
    logger.info(message)
    return items
