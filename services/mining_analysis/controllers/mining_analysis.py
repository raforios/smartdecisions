'''
    Mining Analysis Controllers
'''
from datetime import date
from fastapi import Request
from boto3.resources.base import ServiceResource
from services.utils import handle_service_errors
from services.logger_config import custom_logger as logger
from services.price_forecast import get_price_forecast_service
from services.mining_analysis import (
    get_all_prices_service,
)
from services.official_reports import (
    get_daily_report_service,
    get_biweekly_report_service,
    get_biweekly_history_service,
)
from schemas.mining_analysis import (
    ForecastMethod,
    PriceForecastResponse,
    MiningPriceResponseSchema,
    DailyReportResponse,
    BiweeklyReportResponse,
    BiweeklyHistoryResponse,
)

@handle_service_errors('MINING_ANALYSIS')
async def get_mineral_prices_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> list[MiningPriceResponseSchema]:
    ''' 
        Controller to fetch all processed prices.
    '''
    message = f'User {current_user} requested all mineral prices.'
    logger.info(message)
    prices = await get_all_prices_service(dynamodb_resource)
    return [MiningPriceResponseSchema.model_validate(p) for p in prices]

@handle_service_errors('MINING_ANALYSIS')
async def get_daily_report_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    ref_date: date,
) -> DailyReportResponse:
    '''
    Orchestrates the daily mineral report (template Minerales_01).
    '''
    message = f'User: {current_user} requesting daily report for {ref_date}.'
    logger.info(message)
    result = await get_daily_report_service(dynamodb_resource, ref_date)
    return DailyReportResponse(**result)

# pylint: disable=too-many-arguments, too-many-positional-arguments
@handle_service_errors('MINING_ANALYSIS')
async def get_biweekly_report_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    year: int,
    month: int,
    half: int,
) -> BiweeklyReportResponse:
    '''
    Orchestrates the biweekly official report (template Minerales_02).
    '''
    message = (f'User: {current_user} requesting biweekly report for '
               f'{year}-{month:02d} half {half}.')
    logger.info(message)
    result = await get_biweekly_report_service(
        dynamodb_resource, (year, month, half)
    )
    return BiweeklyReportResponse(**result)

@handle_service_errors('MINING_ANALYSIS')
async def get_biweekly_history_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    period_from: date = None,
    period_to: date = None,
) -> BiweeklyHistoryResponse:
    '''
    Orchestrates the biweekly history endpoint.
    '''
    message = (f'User: {current_user} requesting biweekly history '
               f'{period_from} → {period_to}.')
    logger.info(message)
    result = await get_biweekly_history_service(
        dynamodb_resource, period_from = period_from, period_to = period_to,
    )
    return BiweeklyHistoryResponse(**result)

@handle_service_errors('MINING_ANALYSIS')
async def get_price_forecast_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    days_ahead: int,
    method: ForecastMethod
) -> PriceForecastResponse:
    '''
    Orchestrates the mineral price projection.
    '''
    message = (f'User: {current_user} requesting a {days_ahead}-day price '
               f'forecast with {method.value}.')
    logger.info(message)
    result = await get_price_forecast_service(
        dynamodb_resource, days_ahead = days_ahead, method = method
    )
    return PriceForecastResponse(**result)
