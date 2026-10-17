'''
    The report and the parameters — orchestration.

    Setting a parameter is a change, so it is audited: a provision rate that
    moved every month of a client's taxes is a number somebody typed.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.projection import ProjectionSchema
from schemas.report import (
    ClientParameterListResponseSchema,
    ClientParameterResponseSchema,
    ClientParameterSchema,
    FinanceReportSchema,
    SuggestedParameterListResponseSchema,
    SuggestedParameterSchema
)
from services.projection import ProjectionRequest, finance_projection
from services.parameters import (
    list_client_parameters,
    list_suggested_parameters,
    set_client_parameter,
    set_suggested_parameter
)
from services.report import finance_report
from services.utils import audit_event, handle_service_errors

# Besides its own input, a controller receives what the decorators read
# —current_user for the audit, request for the usage log— so two of them pass
# the five-argument budget without carrying more than they need.
# pylint: disable=too-many-arguments, too-many-positional-arguments


@handle_service_errors('FINANCE')
async def finance_report_controller(
    dynamodb_resource: ServiceResource,
    client: str,
    auth_token: str | None,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> FinanceReportSchema:
    '''
        The report of the client.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            client (str): The owner of the data, from the token.
            auth_token (str | None): The caller's Authorization header, for PARAMETERS.
            current_user (str): The user, read by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            FinanceReportSchema: Every month and every year.
    '''
    return finance_report(dynamodb_resource, client, auth_token)


@handle_service_errors('FINANCE')
async def list_client_parameters_controller(
    dynamodb_resource: ServiceResource,
    client: str,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> ClientParameterListResponseSchema:
    '''
        The parameters the client can set, with the suggestion of each.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            client (str): The owner of the data, from the token.
            current_user (str): The user, read by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ClientParameterListResponseSchema: The parameters.
    '''
    return list_client_parameters(dynamodb_resource, client)


@handle_service_errors('FINANCE')
@audit_event('FINANCE', 'ClientParameter', 'UPDATE')
async def set_client_parameter_controller(
    dynamodb_resource: ServiceResource,
    parameter_code: str,
    parameter: ClientParameterSchema,
    client: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ClientParameterResponseSchema:
    '''
        Stores the value the client chose for a parameter.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            parameter_code (str): The parameter.
            parameter (ClientParameterSchema): The value.
            client (str): The owner of the data, from the token.
            current_user (str): The user setting it, recorded and audited.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ClientParameterResponseSchema: The parameter after the change.
    '''
    return set_client_parameter(dynamodb_resource, (client, current_user),
                                parameter_code, parameter)


@handle_service_errors('FINANCE')
async def list_suggested_parameters_controller(
    dynamodb_resource: ServiceResource,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> SuggestedParameterListResponseSchema:
    '''
        Every suggestion BearSoft keeps.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            current_user (str): The user, read by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            SuggestedParameterListResponseSchema: The suggestions.
    '''
    return list_suggested_parameters(dynamodb_resource)


@handle_service_errors('FINANCE')
@audit_event('FINANCE', 'SuggestedParameter', 'UPDATE')
async def set_suggested_parameter_controller(
    dynamodb_resource: ServiceResource,
    parameter: SuggestedParameterSchema,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> SuggestedParameterSchema:
    '''
        Stores a value BearSoft suggests to every client.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            parameter (SuggestedParameterSchema): The suggestion.
            current_user (str): The ADMIN making the change, read by the decorators for the audit.
            request (Request): Incoming request, used by the decorators.

        Returns:
            SuggestedParameterSchema: The stored suggestion.
    '''
    return set_suggested_parameter(dynamodb_resource, parameter)


@handle_service_errors('FINANCE')
async def finance_projection_controller(
    dynamodb_resource: ServiceResource,
    client: str,
    asked: tuple[str | None, ProjectionRequest],
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> ProjectionSchema:
    '''
        The projection of the client, with what the manager typed.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            client (str): The owner of the data, from the token.
            asked (tuple[str | None, ProjectionRequest]): The caller's
                Authorization header and what the screen sent.
            current_user (str): The user, read by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ProjectionSchema: The three scenarios.
    '''
    auth_token, wanted = asked
    return finance_projection(dynamodb_resource, client, auth_token, wanted)
