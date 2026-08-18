'''
    CRUD Service
'''
import json
import decimal
import time
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

# Query parameters that describe a date RANGE instead of an exact value, and
# the item attribute they are matched against.
DATE_RANGE_PARAMS = ('start_date', 'end_date')
DEFAULT_DATE_ATTRIBUTE = 'timestamp'
# A filtered Scan reads before it filters, so filling one page can take several
# reads. The budget is in seconds, not pages: the service runs in a Lambda with
# a 30 s timeout and a read page can be slow on a large, low-capacity table.
# Returning a partial page with a cursor beats dying on timeout.
SCAN_TIME_BUDGET_SECONDS = 18


def _build_filter_expression(filters: Dict[str, Any], date_attribute: str):
    '''
        Turns the query parameters into a DynamoDB FilterExpression.

        Ordinary parameters match by equality. `start_date` / `end_date` are
        NOT item attributes: they describe a range over `date_attribute`, and
        matching them by equality is what made every dated query come back
        empty.

        Args:
            filters (Dict[str, Any]): Query parameters, without paging keys.
            date_attribute (str): Item attribute holding the ISO timestamp.

        Returns:
            The combined condition, or None when there is nothing to filter.
    '''
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    conditions = [
        Attr(key).eq(value)
        for key, value in filters.items()
        if key not in DATE_RANGE_PARAMS
    ]

    if start_date and end_date:
        conditions.append(Attr(date_attribute).between(start_date, end_date))
    elif start_date:
        conditions.append(Attr(date_attribute).gte(start_date))
    elif end_date:
        conditions.append(Attr(date_attribute).lte(end_date))

    if not conditions:
        return None
    combined = conditions[0]
    for condition in conditions[1:]:
        combined &= condition
    return combined


def _find_usable_index(
    table, filters: Dict[str, Any], partition_attribute: Optional[str]
) -> Optional[Dict[str, str]]:
    '''
        Looks for a secondary index that can answer this query as a Query
        instead of a Scan.

        Usable means the caller both declared which attribute its index is
        partitioned by AND filtered by it; the date range then rides on the
        index sort key. Which attribute that is belongs to the service, not
        here, so it travels as an argument.

        Args:
            table: boto3 Table resource.
            filters (Dict[str, Any]): Query parameters, without paging keys.
            partition_attribute (Optional[str]): Attribute the service's index
                is partitioned by. None means "always Scan".

        Returns:
            Optional[Dict[str, str]]: {'name', 'partition', 'sort'} or None to
                fall back to Scan.
    '''
    if not partition_attribute or not filters.get(partition_attribute):
        return None
    try:
        indexes = table.global_secondary_indexes or []
    except AWSClientError:
        return None

    for index in indexes:
        keys = {k['KeyType']: k['AttributeName'] for k in index['KeySchema']}
        if keys.get('HASH') == partition_attribute:
            return {
                'name': index['IndexName'],
                'partition': keys['HASH'],
                'sort': keys.get('RANGE'),
            }
    return None


def _index_key_condition(index: Dict[str, str], filters: Dict[str, Any]):
    '''
        Builds the KeyConditionExpression for an index-backed listing: the
        partition value plus, when the index is sorted by date, the requested
        range.
    '''
    condition = Key(index['partition']).eq(filters[index['partition']])
    sort_key = index.get('sort')
    if not sort_key:
        return condition

    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    if start_date and end_date:
        condition &= Key(sort_key).between(start_date, end_date)
    elif start_date:
        condition &= Key(sort_key).gte(start_date)
    elif end_date:
        condition &= Key(sort_key).lte(end_date)
    return condition


def _cursor_from_item(item: Dict[str, Any], key_schema: List[Dict[str, str]]) -> Dict[str, Any]:
    '''
        Builds the pagination cursor pointing at a specific item, so the next
        page resumes exactly where this one stopped.

        Args:
            item (Dict[str, Any]): Last item actually returned to the caller.
            key_schema (List[Dict[str, str]]): Table key schema from boto3.

        Returns:
            Dict[str, Any]: ExclusiveStartKey for the following request.
    '''
    return {key['AttributeName']: item[key['AttributeName']] for key in key_schema}


def _build_read_plan(table, filters: Dict[str, Any], limit: int, options: Dict[str, Any]):
    '''
        Decides how the listing will be read and with which arguments.

        Uses a Query against a secondary index when one can answer the filter,
        because that reads only matching items; otherwise falls back to a Scan,
        which reads the table and discards what does not match.

        Args:
            table: boto3 Table resource.
            filters (Dict[str, Any]): Query parameters, without paging keys.
            limit (int): Page size requested by the caller.
            options (Dict[str, Any]): 'date_attribute' and, optionally,
                'index_partition_attribute'.

        Returns:
            tuple: (callable that reads one page, kwargs for it).
    '''
    date_attribute = options['date_attribute']
    read_kwargs: Dict[str, Any] = {'Limit': limit}
    index = _find_usable_index(table, filters, options.get('index_partition_attribute'))

    if not index:
        filter_expression = _build_filter_expression(filters, date_attribute)
        if filter_expression is not None:
            read_kwargs['FilterExpression'] = filter_expression
        return table.scan, read_kwargs

    read_kwargs['IndexName'] = index['name']
    read_kwargs['KeyConditionExpression'] = _index_key_condition(index, filters)
    # Whatever the key condition already covers must not be filtered again.
    consumed = {index['partition'], *(DATE_RANGE_PARAMS if index.get('sort') else ())}
    leftover = {k: v for k, v in filters.items() if k not in consumed}
    residual = _build_filter_expression(leftover, date_attribute)
    if residual is not None:
        read_kwargs['FilterExpression'] = residual
    return table.query, read_kwargs


def _read_until_full(read_page, read_kwargs: Dict[str, Any], limit: int):
    '''
        Reads pages until `limit` items are gathered, the data runs out or the
        time budget expires.

        A filtered read returns only what matched the page it read, so one call
        can legitimately come back empty while matches remain further along.
        Looping here is what turns an empty response into a truthful "no more
        matches" instead of "nothing on this page".

        Args:
            read_page: Bound table.query or table.scan.
            read_kwargs (Dict[str, Any]): Arguments for it; mutated per page.
            limit (int): Items the caller asked for.

        Returns:
            tuple: (items gathered, cursor to continue or None).
    '''
    items: List[Dict[str, Any]] = []
    cursor = None
    deadline = time.monotonic() + SCAN_TIME_BUDGET_SECONDS
    while True:
        response = read_page(**read_kwargs)
        items.extend(response.get('Items', []))
        cursor = response.get('LastEvaluatedKey')
        if len(items) >= limit or not cursor or time.monotonic() > deadline:
            return items, cursor
        read_kwargs['ExclusiveStartKey'] = cursor


def get_all_records_paginated(
    dynamodb_resource: ServiceResource,
    table_name: str,
    query_params: Dict[str, Any],
    date_attribute: str = DEFAULT_DATE_ATTRIBUTE,
    index_partition_attribute: Optional[str] = None,
) -> Dict[str, Any]:
    '''
        Retrieves items from a DynamoDB table with optional pagination and
        filters.

        DynamoDB applies `Limit` to the items it READS, before the filter runs,
        so a single scan can return an empty page while the table still holds
        matches further along. This keeps reading until the page is full, the
        table is exhausted or the read budget runs out, so an empty `records`
        list now really means "no more matches".

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            table_name (str): Table to read.
            query_params (Dict[str, Any]): Filters plus `limit` and
                `last_evaluated_key`.
            date_attribute (str): Item attribute the date range applies to.
            index_partition_attribute (Optional[str]): Attribute the service's
                secondary index is partitioned by. When given and present in
                the filters, the listing is served by a Query instead of a
                Scan. Omit it and the behaviour is the previous Scan.

        Returns:
            Dict[str, Any]: 'items' and the 'last_evaluated_key' to continue.
    '''
    try:
        table = dynamodb_resource.Table(table_name)
        limit = query_params.get('limit', 100)

        filters = {k: v for k, v in query_params.items() if v is not None and k \
            not in ['limit', 'last_evaluated_key']}

        read_page, read_kwargs = _build_read_plan(table, filters, limit, {
            'date_attribute': date_attribute,
            'index_partition_attribute': index_partition_attribute,
        })

        if 'last_evaluated_key' in query_params and query_params['last_evaluated_key']:
            read_kwargs['ExclusiveStartKey'] = json.loads(query_params['last_evaluated_key'])

        items, cursor = _read_until_full(read_page, read_kwargs, limit)

        # More matches than the caller asked for: hand back exactly `limit` and
        # point the cursor at the last one returned, so nothing is skipped.
        if len(items) > limit:
            items = items[:limit]
            cursor = _cursor_from_item(items[-1], table.key_schema)

        message = f'Retrieved {len(items)} records from {table_name}.'
        logger.info(message)

        return {
            'items': items,
            'last_evaluated_key': json.dumps(
                cursor, separators = (',', ':'), default = str) if cursor else None
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


# pylint: disable=too-many-arguments, too-many-positional-arguments
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
