'''
    Fluctuating factors — HTTP layer.

    The exchange rate has its own endpoints because it has a publisher and a
    calendar. Everything else that moves on its own and changes what a report
    means goes through here: declared once, loaded by hand or by API, and
    carrying the day it was true.

    A factor is never an environment variable. The `.env` belongs to the
    deployment, and a number the client reads off an invoice every week cannot
    need a release to change.
'''
from datetime import date as date_type
from typing import Optional

from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path as PathParam, Query, Request, status

from controllers.factors import (
    declare_factor_controller,
    list_factors_controller,
    load_factor_values_controller,
    read_factor_series_controller,
    read_factor_state_controller,
    transport_cost_controller
)
from schemas.factors import (
    FactorDefinitionSchema,
    FactorListResponseSchema,
    FactorResponseSchema,
    FactorSeriesResponseSchema,
    FactorStateSchema,
    FactorValuesLoadSchema,
    TransportCostSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner

router = APIRouter(prefix = '/v1/quotes/factors', tags = ['Fluctuating factors'])

# A FastAPI endpoint declares its dependencies as parameters —resource, caller,
# body— so the five-argument budget does not describe it.
# pylint: disable=too-many-arguments, too-many-positional-arguments

_CODE = PathParam(..., min_length = 1, max_length = 40)


@router.post(
    '',
    response_model = FactorResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Declare a fluctuating factor',
    description = (
        'A figure that moves on its own and changes what a report means — the '
        'price of fuel, a tariff, an index. It is born ACTIVE; turning it '
        'off is what stops it counting. Declaring it again corrects the '
        'definition and keeps every reading already loaded.'
    )
)
async def declare_factor_endpoint(
    request: Request,
    definition: FactorDefinitionSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> FactorResponseSchema:
    '''
        Endpoint to declare a fluctuating factor.
    '''
    message = (f'User: {current_user}. Declaring factor {definition.code} '
               f'as {definition.status.value}.')
    logger.info(message)
    return await declare_factor_controller(
        dynamodb_resource = dynamodb_resource,
        definition = definition,
        current_user = current_user,
        request = request
    )


@router.get(
    '',
    response_model = FactorListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The factors of the account, with their latest reading',
    description = (
        'Every factor by default, so a screen can show the ones turned off '
        'and offer to turn them back on. `only_active` returns just the ones '
        'a calculation is allowed to take into account.'
    )
)
async def list_factors_endpoint(
    request: Request,
    only_active: bool = Query(False, description = 'Leave out the ones turned off.'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> FactorListResponseSchema:
    '''
        Endpoint listing the account's factors.
    '''
    message = f'User: {current_user}. Reading the factors (only_active={only_active}).'
    logger.info(message)
    return await list_factors_controller(
        dynamodb_resource = dynamodb_resource,
        only_active = only_active,
        current_user = current_user,
        request = request
    )


@router.post(
    '/{code}/values',
    response_model = FactorResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Load readings of a factor',
    description = (
        'Typed on a screen or pushed by an ERP; both doors, like every other '
        'load in the product. Idempotent by day: sending a day again corrects '
        'it instead of leaving two truths for it.'
    )
)
async def load_factor_values_endpoint(
    request: Request,
    load: FactorValuesLoadSchema,
    code: str = _CODE,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> FactorResponseSchema:
    '''
        Endpoint to load readings of a factor.
    '''
    message = (f'User: {current_user}. Loading {len(load.values)} reading(s) '
               f'of factor {code}.')
    logger.info(message)
    return await load_factor_values_controller(
        dynamodb_resource = dynamodb_resource,
        code = code,
        load = load,
        current_user = current_user,
        request = request
    )


@router.get(
    '/transport-cost',
    response_model = TransportCostSchema,
    status_code = status.HTTP_200_OK,
    summary = 'What a local delivery over a distance costs',
    description = (
        'Kilometres divided by what a litre gives, times what a litre cost, '
        'over the ROUND TRIP — the vehicle ends at the last client and returns '
        'empty. Local distribution only; import freight is another matter. '
        'Both figures are read as of the day asked about, so a route run in '
        'March is costed with March\'s fuel. The whole chain comes back and '
        'not just the total: a number a manager cannot take apart is one they '
        'cannot argue with.'
    )
)
async def transport_cost_endpoint(
    request: Request,
    km: float = Query(..., gt = 0, description = 'Kilometres of the route, one way.'),
    day: date_type = Query(..., alias = 'date', description = 'YYYY-MM-DD.'),
    units: Optional[float] = Query(
        None, gt = 0, description = 'Units carried, to get the cost per unit.'
    ),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> TransportCostSchema:
    '''
        Endpoint costing a local delivery.
    '''
    message = f'User: {current_user}. Costing {km} km of delivery on {day}.'
    logger.info(message)
    return await transport_cost_controller(
        dynamodb_resource = dynamodb_resource,
        trip = (km, units),
        day = day,
        current_user = current_user,
        request = request
    )


@router.get(
    '/{code}/state',
    response_model = FactorStateSchema,
    status_code = status.HTTP_200_OK,
    summary = 'What this factor WAS on a day',
    description = (
        'Its reading and whether it counted, both as they stood that day. A '
        'report of March is computed with March\'s pair, so turning a factor '
        'off in September cannot rewrite a figure produced before it. A '
        'factor answers inactive for any day before it existed: something '
        'that did not exist did not count.'
    )
)
async def read_factor_state_endpoint(
    request: Request,
    code: str = _CODE,
    day: date_type = Query(..., alias = 'date', description = 'YYYY-MM-DD.'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> FactorStateSchema:
    '''
        Endpoint reading the state of a factor on a day.
    '''
    message = f'User: {current_user}. Reading factor {code} as of {day}.'
    logger.info(message)
    return await read_factor_state_controller(
        dynamodb_resource = dynamodb_resource,
        code = code,
        day = day,
        current_user = current_user,
        request = request
    )


@router.get(
    '/{code}/values',
    response_model = FactorSeriesResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The series of one factor'
)
async def read_factor_series_endpoint(
    request: Request,
    code: str = _CODE,
    start: Optional[date_type] = Query(None, description = 'First day to include.'),
    end: Optional[date_type] = Query(None, description = 'Last day to include.'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> FactorSeriesResponseSchema:
    '''
        Endpoint reading the series of a factor.
    '''
    message = f'User: {current_user}. Reading the series of factor {code}.'
    logger.info(message)
    return await read_factor_series_controller(
        dynamodb_resource = dynamodb_resource,
        code = code,
        window = (start, end),
        current_user = current_user,
        request = request
    )
