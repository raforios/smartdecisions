'''
    Fluctuating factors — orchestration.

    Declaring a factor and loading its readings are changes, so they are
    audited: a fuel price that moved a report is a number somebody typed, and
    it has to be possible to say who.
'''
from datetime import date as date_type

from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.factors import (
    FactorDefinitionSchema,
    FactorListResponseSchema,
    FactorResponseSchema,
    FactorSeriesResponseSchema,
    FactorStateSchema,
    FactorValuesLoadSchema,
    TransportCostSchema
)
from services.factors import (
    SERIES_VALUE,
    declare_factor,
    get_factor,
    list_factors,
    load_values,
    read_series,
    state_on,
    to_factor_response,
    transport_cost
)
from services.utils import audit_event, handle_service_errors


@handle_service_errors('QUOTES')
@audit_event('QUOTES', 'Factor', 'CREATE')
async def declare_factor_controller(
    dynamodb_resource: ServiceResource,
    definition: FactorDefinitionSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> FactorResponseSchema:
    '''
        Declares a fluctuating factor, or corrects its definition.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            definition (FactorDefinitionSchema): The factor.
            current_user (str): Account that owns the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            FactorResponseSchema: The stored factor.
    '''
    return to_factor_response(declare_factor(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        definition = definition
    ))


@handle_service_errors('QUOTES')
async def list_factors_controller(
    dynamodb_resource: ServiceResource,
    only_active: bool,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> FactorListResponseSchema:
    '''
        The factors of the account, with their latest reading.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            only_active (bool): Whether to leave out the ones turned off.
            current_user (str): Account that owns the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            FactorListResponseSchema: The factors.
    '''
    return list_factors(dynamodb_resource, current_user, only_active)


@handle_service_errors('QUOTES')
@audit_event('QUOTES', 'Factor', 'UPDATE')
async def load_factor_values_controller(
    dynamodb_resource: ServiceResource,
    code: str,
    load: FactorValuesLoadSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> FactorResponseSchema:
    '''
        Loads readings of a factor, typed on a screen or pushed by an ERP.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            code (str): Factor identifier.
            load (FactorValuesLoadSchema): The readings.
            current_user (str): Account that owns the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            FactorResponseSchema: The factor with its latest reading.
    '''
    return to_factor_response(load_values(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        code = code,
        values = load.values
    ))


@handle_service_errors('QUOTES')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def read_factor_series_controller(
    dynamodb_resource: ServiceResource,
    code: str,
    window: tuple[date_type | None, date_type | None],
    current_user: str,
    request: Request, # pylint: disable=unused-argument
    series: str = SERIES_VALUE
) -> FactorSeriesResponseSchema:
    '''
        The readings of a factor over a window.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            code (str): Factor identifier.
            window (tuple): First and last day to include.
            series (str): Which series — the readings or the status history.
            current_user (str): Account that owns the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            FactorSeriesResponseSchema: The series, oldest first.
    '''
    start, end = window
    get_factor(dynamodb_resource, current_user, code)
    return read_series(dynamodb_resource, current_user, code, start, end, series)


@handle_service_errors('QUOTES')
async def read_factor_state_controller(
    dynamodb_resource: ServiceResource,
    code: str,
    day: date_type,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> FactorStateSchema:
    '''
        What a factor was on a day: its reading and whether it counted.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            code (str): Factor identifier.
            day (date): The day being asked about.
            current_user (str): Account that owns the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            FactorStateSchema: The factor as it stood that day.
    '''
    return state_on(dynamodb_resource, current_user, code, day)


@handle_service_errors('QUOTES')
async def transport_cost_controller(
    dynamodb_resource: ServiceResource,
    trip: tuple[float, float | None],
    day: date_type,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> TransportCostSchema:
    '''
        What a local delivery over a distance cost on a day.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            trip (tuple): Kilometres one way, and the units carried if known.
            day (date): The day the trip belongs to.
            current_user (str): Account that owns the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            TransportCostSchema: The chain and its total.
    '''
    return transport_cost(dynamodb_resource, current_user, trip, day)
