'''
    The parameters the calculation reads: the rates set by law (global, ADMIN
    only), the values BearSoft suggests (global, ADMIN only) and the values
    each client chose (its MANAGER).

    A suggestion is never applied on its own: until the client sets its own
    value, the figure that depends on it is not calculated and the report says
    so (Rafael, 16-oct: the IUE provision is a suggestion the user defines).
'''
from datetime import date as date_type
from typing import Any

from boto3.dynamodb.conditions import Key
from boto3.resources.base import ServiceResource

from models.finance import ClientParameterItem, SuggestedParameterItem
from schemas.report import (
    ClientParameterListResponseSchema,
    ClientParameterResponseSchema,
    ClientParameterSchema,
    ReportError,
    SuggestedParameterListResponseSchema,
    SuggestedParameterSchema
)
from services.environment import load_and_validate_env_vars
from services.exceptions import ResourceNotFoundError
from services.finance import LAW_PARAMETERS_TABLE
from services.finance_utils import scan_all, to_dynamo
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_FINANCE_SUGGESTED_PARAMETERS': str,
    'DYNAMODB_TABLE_NAME_FINANCE_CLIENT_PARAMETERS': str,
})
SUGGESTED_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_FINANCE_SUGGESTED_PARAMETERS']
CLIENT_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_FINANCE_CLIENT_PARAMETERS']


def law_rates(dynamodb_resource: ServiceResource) -> dict[str, list[tuple[str, float]]]:
    '''
        Every value of every law parameter, by code, oldest first.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            dict[str, list[tuple[str, float]]]: {code: [(valid_from, rate)]}.
    '''
    rates: dict[str, list[tuple[str, float]]] = {}
    for item in scan_all(dynamodb_resource, LAW_PARAMETERS_TABLE):
        rates.setdefault(item['parameter_code'], []).append(
            (item['valid_from'], float(item['rate']))
        )
    return {code: sorted(values) for code, values in rates.items()}


def rate_on(
    rates: dict[str, list[tuple[str, float]]],
    code: str,
    day: date_type
) -> float:
    '''
        The rate of a law parameter in force on a day: the last one that
        started on or before it. A month is computed with its own rate.

        Args:
            rates (dict[str, list[tuple[str, float]]]): From `law_rates`.
            code (str): The parameter, e.g. IVA.
            day (date): The day it applies to.

        Returns:
            float: The rate, as a fraction (13 % is 0.13).

        Raises:
            ResourceNotFoundError: PARAMETER_NOT_FOUND or NO_RATE_FOR_DATE.
    '''
    if code not in rates:
        error_msg = f'Law parameter {code} does not exist.'
        logger.error(error_msg)
        raise ResourceNotFoundError(detail = ReportError.PARAMETER_NOT_FOUND.value)
    in_force = [rate for valid_from, rate in rates[code] if valid_from <= day.isoformat()]
    if not in_force:
        error_msg = f'No {code} rate in force on {day}.'
        logger.error(error_msg)
        raise ResourceNotFoundError(detail = ReportError.NO_RATE_FOR_DATE.value)
    return in_force[-1] / 100


def set_suggested_parameter(
    dynamodb_resource: ServiceResource,
    parameter: SuggestedParameterSchema
) -> SuggestedParameterSchema:
    '''
        Stores a value BearSoft suggests to every client.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            parameter (SuggestedParameterSchema): The suggestion.

        Returns:
            SuggestedParameterSchema: The stored suggestion.
    '''
    item: SuggestedParameterItem = {
        **parameter.model_dump(), 'updated_at': get_current_time_gmt().isoformat()
    }
    dynamodb_resource.Table(SUGGESTED_TABLE).put_item(Item = to_dynamo(dict(item)))
    message = f'Suggested parameter {parameter.parameter_code} set to {parameter.value}.'
    logger.info(message)
    return parameter


def list_suggested_parameters(
    dynamodb_resource: ServiceResource
) -> SuggestedParameterListResponseSchema:
    '''
        Every suggestion BearSoft keeps.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            SuggestedParameterListResponseSchema: The suggestions.
    '''
    parameters = [
        SuggestedParameterSchema(parameter_code = item['parameter_code'], name = item['name'],
                                 value = float(item['value']))
        for item in sorted(scan_all(dynamodb_resource, SUGGESTED_TABLE),
                           key = lambda item: item['parameter_code'])
    ]
    return SuggestedParameterListResponseSchema(parameters = parameters, total = len(parameters))


def _client_values(
    dynamodb_resource: ServiceResource,
    client: str
) -> dict[str, dict[str, Any]]:
    '''
        What the client set, by parameter code.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.

        Returns:
            dict[str, dict[str, Any]]: The stored items.
    '''
    response = dynamodb_resource.Table(CLIENT_TABLE).query(
        KeyConditionExpression = Key('client').eq(client)
    )
    return {item['parameter_code']: item for item in response.get('Items', [])}


def list_client_parameters(
    dynamodb_resource: ServiceResource,
    client: str
) -> ClientParameterListResponseSchema:
    '''
        Every parameter the client can set, with its own value next to the
        suggestion.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.

        Returns:
            ClientParameterListResponseSchema: The parameters.
    '''
    own = _client_values(dynamodb_resource, client)
    parameters = []
    for suggestion in list_suggested_parameters(dynamodb_resource).parameters:
        mine = own.get(suggestion.parameter_code)
        parameters.append(ClientParameterResponseSchema(
            parameter_code = suggestion.parameter_code, name = suggestion.name,
            suggested = suggestion.value,
            value = float(mine['value']) if mine else None,
            updated_at = mine['updated_at'] if mine else None
        ))
    return ClientParameterListResponseSchema(parameters = parameters, total = len(parameters))


def client_value(
    dynamodb_resource: ServiceResource,
    client: str,
    parameter_code: str
) -> float | None:
    '''
        The value the client chose, or None while it has not chosen one.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            parameter_code (str): The parameter.

        Returns:
            float | None: The percentage the client set.
    '''
    item = _client_values(dynamodb_resource, client).get(parameter_code)
    return float(item['value']) if item else None


def set_client_parameter(
    dynamodb_resource: ServiceResource,
    owner: tuple[str, str],
    parameter_code: str,
    parameter: ClientParameterSchema
) -> ClientParameterResponseSchema:
    '''
        Stores the value a client chose. Only a parameter BearSoft defined
        can be set: the suggestion is what declares it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (tuple[str, str]): The client and the user setting it.
            parameter_code (str): The parameter.
            parameter (ClientParameterSchema): The value.

        Returns:
            ClientParameterResponseSchema: The parameter after the change.

        Raises:
            ResourceNotFoundError: PARAMETER_NOT_FOUND.
    '''
    client, user = owner
    suggestion = dynamodb_resource.Table(SUGGESTED_TABLE).get_item(
        Key = {'parameter_code': parameter_code}
    ).get('Item')
    if not suggestion:
        error_msg = f'{client} tried to set the unknown parameter {parameter_code}.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = ReportError.PARAMETER_NOT_FOUND.value)
    now = get_current_time_gmt().isoformat()
    item: ClientParameterItem = {
        'client': client, 'parameter_code': parameter_code, 'value': parameter.value,
        'user': user, 'updated_at': now
    }
    dynamodb_resource.Table(CLIENT_TABLE).put_item(Item = to_dynamo(dict(item)))
    message = f'{client} set {parameter_code} to {parameter.value} ({user}).'
    logger.info(message)
    return ClientParameterResponseSchema(
        parameter_code = parameter_code, name = suggestion['name'],
        suggested = float(suggestion['value']), value = parameter.value, updated_at = now
    )
