'''
    CRUD Service
'''
import json
from typing import Any, Dict
from boto3.resources.base import ServiceResource
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError as AWSClientError
from services.logger_config import custom_logger as logger
from services.exceptions import RegisterAlreadyExistsError, RegisterNotFoundError

# Constantes para la gestión de las tablas y sus claves
TABLE_SCHEMA = {
    'audit_records': {'pk': 'id', 'sk': 'sk', 'index': 'sk-pk-index'},
    'usage_logs': {'pk': 'id', 'sk': 'sk', 'index': 'sk-pk-index'},
}

def create_item(
    dynamodb_resource: ServiceResource,
    table_name: str,
    item_data: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Adds a new item to a DynamoDB table.
    '''
    try:
        table = dynamodb_resource.Table(table_name)
        # Conditional put to prevent overwriting an existing item
        table.put_item(
            Item = item_data,
            ConditionExpression = 'attribute_not_exists(id)'
        )
        message = f'Item added successfully to {table_name}.'
        logger.info(message)
        return item_data
    except AWSClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            error_msg = f'Item with id {item_data["id"]} already exists.'
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
