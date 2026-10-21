'''
    Mining Analysis: routes handler
'''
from datetime import date as date_type
from fastapi import (
    APIRouter,
    Depends,
    Request,
    status,
    Query
)
from boto3.resources.base import ServiceResource
from services.logger_config import custom_logger as logger
from services.db_connection import GET_DB_DEPENDENCY
from services.environment import load_and_validate_env_vars
from services.security import require_roles
from routes.market import MINERALS_ROLES
from controllers.mining_analysis import (
    get_mineral_prices_controller,
    get_daily_report_controller,
    get_biweekly_report_controller,
    get_price_forecast_controller,
)
from schemas.mining_analysis import (
    MiningPriceResponseSchema,
    DailyReportResponse,
    BiweeklyReportResponse,
    ForecastMethod,
    PriceForecastResponse,
)

# Days a price projection covers when the caller does not ask for a horizon.
_SETTINGS = load_and_validate_env_vars({'FORECAST_DEFAULT_DAYS_AHEAD': int})
DEFAULT_DAYS_AHEAD = _SETTINGS['FORECAST_DEFAULT_DAYS_AHEAD']

router = APIRouter(prefix = '/v1/mining-analysis', tags = ['Mining Analysis'])


class BiweeklyPeriod: # pylint: disable=too-few-public-methods
    '''
        The half of the month a biweekly report covers.

        Grouped as a dependency rather than three loose query parameters
        because they are one concept: they travel together, they are validated
        together, and the endpoint stays within the argument budget.
    '''

    def __init__(
        self,
        year: int = Query(..., ge = 2000, le = 2100, description = 'Year.'),
        month: int = Query(..., ge = 1, le = 12, description = 'Month (1-12).'),
        half: int = Query(..., ge = 1, le = 2,
                          description = '1 for days 1-15, 2 for 16-end.')
    ):
        self.year = year
        self.month = month
        self.half = half

@router.get(
    '/prices',
    response_model = list[MiningPriceResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Get all mineral prices',
    description = 'Retrieves a normalized list of all mineral prices with their metadata.'
)
async def get_mining_prices_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MINERALS_ROLES))
) -> list[MiningPriceResponseSchema]:
    ''' Endpoint to retrieve processed prices. '''
    message = f'User: {current_user}. Requested all mineral prices.'

    logger.info(message)

    return await get_mineral_prices_controller(
        dynamodb_resource = dynamodb_resource,
        request = request,
        current_user = current_user
    )

@router.get(
    '/reports/daily',
    response_model = DailyReportResponse,
    summary = 'Daily mineral report (Minerales_01 template).',
    description = 'Returns the latest cotización per official mineral up to '
                  'the reference date, with fallback to the most recent prior '
                  'record when no entry exists on the date itself.'
)
async def get_daily_report_endpoint(
    request: Request,
    ref_date: date_type = Query(..., alias = 'date',
                                description = 'Reference date (YYYY-MM-DD).'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MINERALS_ROLES))
) -> DailyReportResponse:
    ''' Endpoint for the daily mineral report. '''
    message = f'User: {current_user}. Requested daily report for {ref_date}.'
    logger.info(message)

    return await get_daily_report_controller(
        dynamodb_resource = dynamodb_resource,
        request = request,
        current_user = current_user,
        ref_date = ref_date,
    )

@router.get(
    '/reports/biweekly',
    response_model = BiweeklyReportResponse,
    summary = 'Biweekly official mineral report (Minerales_02 template).',
    description = 'Returns the simple mean of price_low across the requested '
                  'half of the month. Falls back to the most recent prior '
                  'biweekly period that has data when none exists.'
)
async def get_biweekly_report_endpoint(
    request: Request,
    period: BiweeklyPeriod = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MINERALS_ROLES))
) -> BiweeklyReportResponse:
    ''' Endpoint for the biweekly official mineral report. '''
    message = (f'User: {current_user}. Requested biweekly report for '
               f'{period.year}-{period.month:02d} half {period.half}.')
    logger.info(message)

    return await get_biweekly_report_controller(
        dynamodb_resource = dynamodb_resource,
        request = request,
        current_user = current_user,
        year = period.year,
        month = period.month,
        half = period.half,
    )

@router.get(
    '/forecast/prices',
    response_model = PriceForecastResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Mineral price projection.',
    description = 'Projects each official mineral forward from its observed '
                  'quotations. Every projection reports the method that '
                  'produced it and how much history backs it; a mineral with '
                  'too little history is listed with an empty projection '
                  'instead of an invented number.'
)
async def get_price_forecast_endpoint(
    request: Request,
    days_ahead: int = Query(DEFAULT_DAYS_AHEAD, ge = 1, le = 180,
                            description = 'Days to project ahead.'),
    method: ForecastMethod = Query(ForecastMethod.DAMPED_TREND,
                                   description = 'Projection method.'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MINERALS_ROLES))
) -> PriceForecastResponse:
    ''' Endpoint for the mineral price projection. '''
    message = f'User: {current_user}. Requested a {days_ahead}-day price forecast.'
    logger.info(message)

    return await get_price_forecast_controller(
        dynamodb_resource = dynamodb_resource,
        request = request,
        current_user = current_user,
        days_ahead = days_ahead,
        method = method,
    )
