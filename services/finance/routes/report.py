'''
    The report and the parameters — HTTP layer.

    The report, the client's own parameters and its business model are for the
    people who run the business (MANAGER); the suggestions every client sees
    are BearSoft's, and only its ADMIN changes them.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Header, Path as PathParam, Query, Request, status

from controllers.report import (
    get_business_model_controller,
    finance_projection_controller,
    finance_report_controller,
    list_client_parameters_controller,
    list_suggested_parameters_controller,
    set_business_model_controller,
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
from schemas.business_model import BusinessModelResponseSchema, BusinessModelSchema
from schemas.projection import ProjectionSchema, ScenarioInputSchema
from services.db_connection import GET_DB_DEPENDENCY
from services.projection import ProjectionRequest
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
    authorization: str | None = Header(None),
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
        auth_token = authorization,
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


def _change(
    sales: float | None,
    outflow: float | None
) -> ScenarioInputSchema | None:
    '''
        A scenario the manager typed, or None to keep the default.

        Args:
            sales (float | None): % change of the sales.
            outflow (float | None): % change of the outflow.

        Returns:
            ScenarioInputSchema | None: The scenario.
    '''
    if sales is None and outflow is None:
        return None
    return ScenarioInputSchema(sales_change = sales or 0.0, outflow_change = outflow or 0.0)


@router.get(
    '/projection',
    response_model = ProjectionSchema,
    status_code = status.HTTP_200_OK,
    summary = 'How the next months may go, in three scenarios',
    description = (
        'The realistic scenario is a damped trend over the loaded months; the '
        'worst and the best move it by the percentages given here, or by the '
        'defaults of the service. Each scenario says when its cash runs out.'
    )
)
async def finance_projection_endpoint(
    request: Request,
    horizon: int | None = Query(None, description = 'Months ahead; the default when empty.'),
    worst_sales: float | None = Query(None, description = 'Worst: % change of the sales.'),
    worst_outflow: float | None = Query(None, description = 'Worst: % change of the outflow.'),
    best_sales: float | None = Query(None, description = 'Best: % change of the sales.'),
    best_outflow: float | None = Query(None, description = 'Best: % change of the outflow.'),
    authorization: str | None = Header(None),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> ProjectionSchema:
    '''
        Endpoint returning the projection.
    '''
    message = f'User: {current_user} ({client}). Projecting {horizon} month(s).'
    logger.info(message)
    return await finance_projection_controller(
        dynamodb_resource = dynamodb_resource,
        client = client,
        asked = (authorization, ProjectionRequest(
            horizon = horizon, worst = _change(worst_sales, worst_outflow),
            best = _change(best_sales, best_outflow))),
        current_user = current_user,
        request = request
    )


@router.get(
    '/business-model',
    response_model = BusinessModelResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The business model the client described'
)
async def get_business_model_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> BusinessModelResponseSchema:
    '''
        Endpoint reading the business model.
    '''
    message = f'User: {current_user} ({client}). Reading the business model.'
    logger.info(message)
    return await get_business_model_controller(
        dynamodb_resource = dynamodb_resource,
        client = client,
        current_user = current_user,
        request = request
    )


@router.put(
    '/business-model',
    response_model = BusinessModelResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Save the business model the client described',
    description = ('Replaces the whole form. The AI compares it with the figures; '
                   'FINANCE only keeps it.')
)
async def set_business_model_endpoint(
    request: Request,
    business_model: BusinessModelSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    client: str = Depends(require_roles(*FINANCE_ROLES)),
    current_user: str = Depends(get_current_user)
) -> BusinessModelResponseSchema:
    '''
        Endpoint saving the business model.
    '''
    message = f'User: {current_user} ({client}). Saving the business model.'
    logger.info(message)
    return await set_business_model_controller(
        dynamodb_resource = dynamodb_resource,
        business_model = business_model,
        client = client,
        current_user = current_user,
        request = request
    )
