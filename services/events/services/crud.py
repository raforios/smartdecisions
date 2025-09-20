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
            Item=item_data,
            ConditionExpression='attribute_not_exists(id)'
        )
        message = f'Item added successfully to {table_name}.'
        logger.info(message)
        return item_data
    except AWSClientError as e:
        if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
            error_msg = f'Item with id {item_data["id"]} already exists.'
            logger.warning(error_msg, exc_info=True)
            raise RegisterAlreadyExistsError(detail=error_msg) from e
        error_msg = f'Error adding item to {table_name}: {e}'
        logger.error(error_msg, exc_info=True)
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
        raise RegisterNotFoundError(detail=error_msg)

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
        limit = query_params.get('limit', 100)
        last_evaluated_key_str = query_params.get('last_evaluated_key', None)

        scan_kwargs = {'Limit': limit}

        # Construir la expresión de filtro dinámicamente
        filters = {k: v for k, v in query_params.items() if v is not None}
        filters.pop('limit', None)
        filters.pop('last_evaluated_key', None)

        if filters:
            expressions = []
            for key, value in filters.items():
                expressions.append(Attr(key).eq(value))

            filter_expression = expressions[0]
            for expr in expressions[1:]:
                filter_expression &= expr

            scan_kwargs['FilterExpression'] = filter_expression

        # Manejar la clave de paginación si está presente
        if last_evaluated_key_str:
            last_evaluated_key = json.loads(last_evaluated_key_str)
            scan_kwargs['ExclusiveStartKey'] = last_evaluated_key

        response = table.scan(**scan_kwargs)

        items = response.get('Items', [])
        response_last_key = response.get('LastEvaluatedKey')

        # Serializar la clave de paginación para la respuesta
        if response_last_key:
            response_last_key = json.dumps(response_last_key, separators=(',', ':'))

        message = f'Retrieved {len(items)} records from {table_name}.'
        logger.info(message)

        return {
            'items': items,
            'last_evaluated_key': response_last_key
        }

    except AWSClientError as e:
        error_msg = f'Error retrieving all items from {table_name}: {e}'
        logger.error(error_msg, exc_info=True)
        raise e
    except json.JSONDecodeError as e:
        error_msg = 'Invalid JSON format for last_evaluated_key.'
        logger.error(error_msg, exc_info=True)
        raise e
