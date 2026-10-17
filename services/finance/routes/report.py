'''
    The report and the parameters — HTTP layer.

    The report and the client's own parameters are for the people who run the
    business (MANAGER); the suggestions every client sees are BearSoft's, and
    only its ADMIN changes them.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path as PathParam, Request, status

from controllers.report import (
    finance_report_controller,
    list_client_parameters_controller,
    list_suggested_parameters_controller,
    set_client_parameter_controller,
    set_suggested_parameter_controller
)
from routes.entries import FINANCE_ROLES
from routes.finance import GLOBAL_EDITORS
from schemas.report import (
    ClientParameterListResponseSchema,
    ClientParameterResponseSchema,
    ClientParameterSchema,
    FinanceReportSchema,
    SuggestedParameterListResponseSchema,
    SuggestedParameterSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner, get_current_user, require_roles

router = APIRouter(prefix = '/v1/finance', tags = ['Financial analysis — report'])

# A FastAPI endpoint declares its dependencies as parameters —resource, caller,
# body— so the five-argument budget does not describe it.
# pylint: disable=too-many-arguments, too-many-positional-arguments


@router.get(
    '/report',
    response_model = FinanceReportSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The financial report of the client',
    description = (
        'Income statement, taxes of the period, balance sheet and indicators, '
        'per month and per year. Computed when asked for, never stored; each '
        'line says whether it was loaded or calculated.'
    )
)
async def finance_report_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> FinanceReportSchema:
    '''
        Endpoint returning the report.
    '''
    message = f'User: {current_user} ({client}). Reading the financial report.'
    logger.info(message)
    return await finance_report_controller(
        dynamodb_resource = dynamodb_resource,
        client = client,
        current_user = current_user,
        request = request
    )


@router.get(
    '/parameters',
    response_model = ClientParameterListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The parameters the client can set, with their suggestion'
)
async def list_client_parameters_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> ClientParameterListResponseSchema:
    '''
        Endpoint listing the client's parameters.
    '''
    message = f'User: {current_user} ({client}). Reading the parameters.'
    logger.info(message)
    return await list_client_parameters_controller(
        dynamodb_resource = dynamodb_resource,
        client = client,
        current_user = current_user,
        request = request
    )


@router.put(
    '/parameters/{parameter_code}',
    response_model = ClientParameterResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Set the value the client chose for a parameter'
)
async def set_client_parameter_endpoint(
    request: Request,
    parameter: ClientParameterSchema,
    parameter_code: str = PathParam(..., min_length = 1, max_length = 40),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> ClientParameterResponseSchema:
    '''
        Endpoint setting a client parameter.
    '''
    message = f'User: {current_user} ({client}). Setting {parameter_code} to {parameter.value}.'
    logger.info(message)
    return await set_client_parameter_controller(
        dynamodb_resource = dynamodb_resource,
        parameter_code = parameter_code,
        parameter = parameter,
        client = client,
        current_user = current_user,
        request = request
    )


@router.get(
    '/suggested-parameters',
    response_model = SuggestedParameterListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The values BearSoft suggests to every client'
)
async def list_suggested_parameters_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> SuggestedParameterListResponseSchema:
    '''
        Endpoint listing the suggestions.
    '''
    message = f'User: {current_user}. Reading the suggested parameters.'
    logger.info(message)
    return await list_suggested_parameters_controller(
        dynamodb_resource = dynamodb_resource,
        current_user = current_user,
        request = request
    )


@router.put(
    '/suggested-parameters',
    response_model = SuggestedParameterSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Set a value BearSoft suggests to every client (ADMIN)'
)
async def set_suggested_parameter_endpoint(
    request: Request,
    parameter: SuggestedParameterSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*GLOBAL_EDITORS))
) -> SuggestedParameterSchema:
    '''
        Endpoint setting a suggestion.
    '''
    message = f'User: {current_user}. Suggesting {parameter.parameter_code} = {parameter.value}.'
    logger.info(message)
    return await set_suggested_parameter_controller(
        dynamodb_resource = dynamodb_resource,
        parameter = parameter,
        current_user = current_user,
        request = request
    )
