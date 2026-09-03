'''
    Mining Analysis: routes handler
'''
from datetime import date as date_type
from typing import Any, Dict, List, Optional
from fastapi import (
    APIRouter,
    Depends,
    Request,
    UploadFile,
    File,
    status,
    Query
)
from sqlalchemy.orm import Session
from services.logger_config import custom_logger as logger
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from controllers.mining_analysis import (
    bulk_upload_mining_controller,
    get_mineral_prices_controller,
    get_royalties_summary_controller,
    get_transactions_summary_controller,
    upload_royalties_controller,
    get_daily_report_controller,
    get_biweekly_report_controller,
    get_price_forecast_controller,
)
from schemas.mining_analysis import (
    MiningPriceResponseSchema,
    BulkUploadMiningResponseSchema,
    RoyaltySummaryResponse,
    TransactionSummaryResponse,
    DailyReportResponse,
    BiweeklyReportResponse,
    ForecastMethod,
    PriceForecastResponse,
)

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

@router.post(
    '/etl/upload',
    response_model = BulkUploadMiningResponseSchema,
    status_code = status.HTTP_201_CREATED
)
async def upload_mining_data_endpoint(
    request: Request,
    file: UploadFile = File(...),
    delimiter: str = Query(',', description = 'Separador de campos del CSV'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> BulkUploadMiningResponseSchema:
    '''
        Endpoint to trigger the mining data ETL process from a CSV file.
    '''
    message = f'User: {current_user}. Uploaded file: {file.filename} with delimiter "{
        delimiter}".'

    logger.info(message)

    content = await file.read()
    return await bulk_upload_mining_controller(
        db = db,
        file_content = content,
        file_name = file.filename,
        request = request,
        current_user = current_user,
        delimiter = delimiter
    )

@router.get(
    '/prices',
    response_model = List[MiningPriceResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Get all mineral prices',
    description = 'Retrieves a normalized list of all mineral prices with their metadata.'
)
async def get_mining_prices_endpoint(
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> List[MiningPriceResponseSchema]:
    ''' Endpoint to retrieve processed prices. '''
    message = f'User: {current_user}. Requested all mineral prices.'

    logger.info(message)

    return await get_mineral_prices_controller(
        db = db,
        request = request,
        current_user = current_user
    )

@router.post('/royalties/upload', status_code=status.HTTP_201_CREATED)
async def upload_royalties_excel(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    ''' Endpoint to trigger the Excel ETL process directly in memory. '''
    message = f'User: {current_user}. Uploading file: {file.filename}'
    logger.info(message)

    # Extraemos los bytes físicos en la capa de rutas
    content = await file.read()

    return await upload_royalties_controller(
        db = db,
        request = request,
        current_user = current_user,
        file_name = file.filename,
        file_content = content # Pasamos los bytes
    )

@router.get('/royalties/summary', response_model = RoyaltySummaryResponse)
async def get_royalties_summary(
    request: Request,
    year: Optional[int] = Query(None, description='Gestión fiscal a consultar'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> RoyaltySummaryResponse:
    ''' Retrieves aggregated royalties data. '''
    message = f'User: {current_user}. Requested royalties summary.'
    logger.info(message)

    return await get_royalties_summary_controller(
        db = db,
        request = request,
        current_user = current_user,
        year = year
    )

@router.get(
    '/royalties/transactions',
    response_model = TransactionSummaryResponse
)
async def get_royalties_transactions(
    request: Request,
    year: Optional[int] = Query(None, description='Gestión fiscal a consultar'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> TransactionSummaryResponse:
    ''' Retrieves aggregated transactions data by company. '''
    message = f'User: {current_user}. Requested transactions summary.'
    logger.info(message)

    return await get_transactions_summary_controller(
        db = db,
        request = request,
        current_user = current_user,
        year = year
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
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> DailyReportResponse:
    ''' Endpoint for the daily mineral report. '''
    message = f'User: {current_user}. Requested daily report for {ref_date}.'
    logger.info(message)

    return await get_daily_report_controller(
        db = db,
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
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> BiweeklyReportResponse:
    ''' Endpoint for the biweekly official mineral report. '''
    message = (f'User: {current_user}. Requested biweekly report for '
               f'{period.year}-{period.month:02d} half {period.half}.')
    logger.info(message)

    return await get_biweekly_report_controller(
        db = db,
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
    days_ahead: int = Query(30, ge = 1, le = 180,
                            description = 'Days to project ahead.'),
    method: ForecastMethod = Query(ForecastMethod.LINEAR,
                                   description = 'Projection method.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> PriceForecastResponse:
    ''' Endpoint for the mineral price projection. '''
    message = f'User: {current_user}. Requested a {days_ahead}-day price forecast.'
    logger.info(message)

    return await get_price_forecast_controller(
        db = db,
        request = request,
        current_user = current_user,
        days_ahead = days_ahead,
        method = method,
    )
