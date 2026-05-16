'''
    Mining Analysis Controllers
'''
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List
from fastapi import Request
from sqlalchemy.orm import Session
from services.utils import (
    _trigger_bulk_audit,
    handle_service_errors,
)
from services.logger_config import custom_logger as logger
from services.royalties_etl import process_royalties_excel_service
from services.mining_analysis import (
    get_royalties_summary_service,
    get_transactions_summary_service,
    process_mining_etl_service,
    get_all_prices_service,
    get_daily_report_service,
    get_biweekly_report_service,
    get_biweekly_history_service,
)
from schemas.mining_analysis import (
    MiningPriceResponseSchema,
    BulkUploadMiningResponseSchema,
    RoyaltySummaryResponse,
    TransactionSummaryResponse,
    DailyReportResponse,
    BiweeklyReportResponse,
    BiweeklyHistoryResponse,
)

# pylint: disable=too-many-arguments, too-many-positional-arguments
@handle_service_errors('MINING_ANALYSIS')
async def bulk_upload_mining_controller(
    db: Session,
    file_content: bytes,
    file_name: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    delimiter: str = ','
) -> BulkUploadMiningResponseSchema:
    '''
        Controller to handle the bulk upload of mining prices via ETL.
        Orchestrates service logic, audit events, and usage logging.
    '''

    result = await process_mining_etl_service(
        db = db,
        file_content = file_content,
        file_name = file_name,
        delimiter = delimiter
    )

    return BulkUploadMiningResponseSchema(**result)

@handle_service_errors('MINING_ANALYSIS')
async def get_mineral_prices_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> List[MiningPriceResponseSchema]:
    ''' 
        Controller to fetch all processed prices.
    '''
    message = f'User {current_user} requested all mineral prices.'
    logger.info(message)
    prices = await get_all_prices_service(db = db)
    return [MiningPriceResponseSchema.model_validate(p) for p in prices]

@handle_service_errors('MINING_ANALYSIS')
async def get_royalties_summary_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    year: int = None,
    quarter: int = None
) -> RoyaltySummaryResponse:
    '''
        Orchestrates the retrieval of royalty summaries with analytics.
    '''
    message = f'User: {current_user} requesting analytics for Year: {year}'
    logger.info(message)

    result = await get_royalties_summary_service(
        db,
        year = year,
        quarter = quarter
    )

    return RoyaltySummaryResponse(**result)

@handle_service_errors('MINING_ANALYSIS')
async def upload_royalties_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    file_name: str,
    file_content: bytes,
    exchange_rate: Decimal = Decimal('6.96')
) -> Dict[str, Any]:
    '''
        Controller to handle in-memory bulk upload of Royalties with currency conversion.
    '''
    message = f'Starting in-memory ETL for file: {file_name} with rate: {exchange_rate}'
    logger.info(message)

    # Procesamiento con tipo de cambio
    result = await process_royalties_excel_service(db, file_content, exchange_rate)

    _trigger_bulk_audit(
        microservice = 'MINING_ANALYSIS',
        entity = 'RoyaltyPayment',
        user = current_user,
        result = result
    )

    return result

@handle_service_errors('MINING_ANALYSIS')
async def get_transactions_summary_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    year: int = None
) -> TransactionSummaryResponse:
    '''
    Orchestrates the retrieval of transactions summary.
    '''
    message = f'User: {current_user} requesting transactions for Year: {year}'
    logger.info(message)

    result = await get_transactions_summary_service(
        db,
        year = year
    )

    return TransactionSummaryResponse(**result)

@handle_service_errors('MINING_ANALYSIS')
async def get_daily_report_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    ref_date: date,
) -> DailyReportResponse:
    '''
    Orchestrates the daily mineral report (template Minerales_01).
    '''
    message = f'User: {current_user} requesting daily report for {ref_date}.'
    logger.info(message)
    result = await get_daily_report_service(db = db, ref_date = ref_date)
    return DailyReportResponse(**result)

@handle_service_errors('MINING_ANALYSIS')
async def get_biweekly_report_controller(
    db: Session,
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
        db = db, year = year, month = month, half = half
    )
    return BiweeklyReportResponse(**result)

@handle_service_errors('MINING_ANALYSIS')
async def get_biweekly_history_controller(
    db: Session,
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
        db = db, period_from = period_from, period_to = period_to,
    )
    return BiweeklyHistoryResponse(**result)
