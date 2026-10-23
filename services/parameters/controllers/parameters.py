'''
    Parameters — orchestration.

    Every change (PUT, POST, DELETE) is audited: a number of decimals or an
    account that moved a report is a value somebody typed, and it has to be
    possible to say who. A read is not logged (Rafael, 17-oct): every service
    reads its values here, and logging each read says nothing about the business.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.parameters import (
    ParameterListResponseSchema,
    ParameterResponseSchema,
    ParameterSchema
)
from services.parameters import (
    all_parameters,
    delete_parameter,
    scope_parameters,
    set_parameter
)
from services.utils import audit_event, handle_service_errors

# Besides its own input, a controller receives what the decorators read
# —current_user for the audit, request for the usage log— so one of them
# passes the five-argument budget without carrying more than it needs.
# pylint: disable=too-many-arguments, too-many-positional-arguments


async def scope_parameters_controller(
    dynamodb_resource: ServiceResource,
    scope: str,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> ParameterListResponseSchema:
    '''
        The parameters of one scope.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            scope (str): `global` or a service name.
            current_user (str): The caller, read by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ParameterListResponseSchema: The parameters.
    '''
    return scope_parameters(dynamodb_resource, scope)


async def all_parameters_controller(
    dynamodb_resource: ServiceResource,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> ParameterListResponseSchema:
    '''
        Every parameter, for the ADMIN.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            current_user (str): The ADMIN, read by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ParameterListResponseSchema: The parameters.
    '''
    return all_parameters(dynamodb_resource)


@handle_service_errors('PARAMETERS')
@audit_event('PARAMETERS', 'Parameter', 'UPDATE', id_field = 'code')
async def set_parameter_controller(
    dynamodb_resource: ServiceResource,
    key: tuple[str, str],
    parameter: ParameterSchema,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> ParameterResponseSchema:
    '''
        Creates or changes a parameter.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            key (tuple[str, str]): Scope and code.
            parameter (ParameterSchema): The value and what it governs.
            current_user (str): The ADMIN making the change, read by the decorators for the audit.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ParameterResponseSchema: The stored parameter.
    '''
    return set_parameter(dynamodb_resource, key, parameter)


@handle_service_errors('PARAMETERS')
@audit_event('PARAMETERS', 'Parameter', 'DELETE', id_field = 'code')
async def delete_parameter_controller(
    dynamodb_resource: ServiceResource,
    key: tuple[str, str],
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> ParameterResponseSchema:
    '''
        Removes a parameter.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            key (tuple[str, str]): Scope and code.
            current_user (str): The ADMIN making the change, read by the decorators for the audit.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ParameterResponseSchema: The parameter that was removed.
    '''
    return delete_parameter(dynamodb_resource, key)
