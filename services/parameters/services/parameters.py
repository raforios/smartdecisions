'''
    The parameters every service reads: business values that change without a
    release.

    Global, like the catalog of FINANCE: one copy, and only an ADMIN of
    BearSoft changes it. Each service reads its own scope and `global` by
    HTTP, the way it asks QUOTES for the exchange rate, so no service reads
    this table.
'''
from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Key
from boto3.resources.base import ServiceResource

from models.parameters import ParameterItem
from schemas.parameters import (
    ParameterError,
    ParameterListResponseSchema,
    ParameterResponseSchema,
    ParameterSchema,
    ValueType
)
from services.environment import load_and_validate_env_vars
from services.exceptions import ResourceNotFoundError
from services.logger_config import custom_logger as logger
from services.parameters_utils import to_dynamo
from services.utils import get_current_time_gmt

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_PARAMETERS_VALUES': str,
})
VALUES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_PARAMETERS_VALUES']


def to_parameter_response(item: ParameterItem | dict[str, Any]) -> ParameterResponseSchema:
    '''
        Builds the response of one stored parameter. DynamoDB keeps numbers as
        Decimal; a NUMBER comes back as a float.

        Args:
            item (ParameterItem | dict[str, Any]): The stored item.

        Returns:
            ParameterResponseSchema: The parameter.
    '''
    value = item['value']
    if isinstance(value, Decimal):
        value = float(value)
    return ParameterResponseSchema(
        scope = item['scope'], code = item['code'], value_type = ValueType(item['value_type']),
        value = value, description = item['description'], updated_at = item['updated_at']
    )


def set_parameter(
    dynamodb_resource: ServiceResource,
    key: tuple[str, str],
    parameter: ParameterSchema
) -> ParameterResponseSchema:
    '''
        Creates or changes a parameter.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            key (tuple[str, str]): Its scope and its code.
            parameter (ParameterSchema): The value and what it governs.

        Returns:
            ParameterResponseSchema: The stored parameter.
    '''
    scope, code = key
    item: ParameterItem = {
        'scope': scope, 'code': code, **parameter.model_dump(mode = 'json'),
        'updated_at': get_current_time_gmt().isoformat()
    }
    dynamodb_resource.Table(VALUES_TABLE).put_item(Item = to_dynamo(dict(item)))
    message = f'Parameter {scope}.{code} set to {parameter.value}.'
    logger.info(message)
    return to_parameter_response(item)


def scope_parameters(
    dynamodb_resource: ServiceResource,
    scope: str
) -> ParameterListResponseSchema:
    '''
        Every parameter of one scope, ordered by code.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            scope (str): `global` or a service name.

        Returns:
            ParameterListResponseSchema: The parameters; empty for an unknown scope.
    '''
    response = dynamodb_resource.Table(VALUES_TABLE).query(
        KeyConditionExpression = Key('scope').eq(scope)
    )
    parameters = [to_parameter_response(item)
                  for item in sorted(response.get('Items', []), key = lambda item: item['code'])]
    return ParameterListResponseSchema(parameters = parameters, total = len(parameters))


def all_parameters(dynamodb_resource: ServiceResource) -> ParameterListResponseSchema:
    '''
        Every parameter of every scope, for the ADMIN.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            ParameterListResponseSchema: The parameters, by scope and code.
    '''
    # A few dozen rows, read whole only here; a service reads its scope by Query.
    table = dynamodb_resource.Table(VALUES_TABLE)
    response = table.scan()
    items = response.get('Items', [])
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey = response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    items.sort(key = lambda item: (item['scope'], item['code']))
    parameters = [to_parameter_response(item) for item in items]
    return ParameterListResponseSchema(parameters = parameters, total = len(parameters))


def delete_parameter(
    dynamodb_resource: ServiceResource,
    key: tuple[str, str]
) -> ParameterResponseSchema:
    '''
        Removes a parameter.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            key (tuple[str, str]): Its scope and its code.

        Returns:
            ParameterResponseSchema: The parameter that was removed.

        Raises:
            ResourceNotFoundError: PARAMETER_NOT_FOUND.
    '''
    scope, code = key
    table = dynamodb_resource.Table(VALUES_TABLE)
    item = table.get_item(Key = {'scope': scope, 'code': code}).get('Item')
    if not item:
        error_msg = f'Parameter {scope}.{code} not found to delete.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = ParameterError.PARAMETER_NOT_FOUND.value)
    table.delete_item(Key = {'scope': scope, 'code': code})
    message = f'Parameter {scope}.{code} removed.'
    logger.info(message)
    return to_parameter_response(item)
