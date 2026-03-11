'''
    Mining Analysis Controllers
'''
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
    process_mining_etl_service,
    get_all_prices_service
)
from schemas.mining_analysis import (
    MiningPriceResponseSchema,
    BulkUploadMiningResponseSchema,
    RoyaltySummaryResponse
)

# pylint: disable=too-many-arguments, too-many-positional-arguments
@handle_service_errors('MINING_ANALYSIS')
async def bulk_upload_mining_controller(
    db: Session,
    file_content: bytes,
    file_name: str, # pylint: disable=unused-argument
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    delimiter: str = ','
) -> BulkUploadMiningResponseSchema:
    '''
        Controller to handle the bulk upload of mining prices via ETL.
        Orchestrates service logic, audit events, and usage logging.
    '''

    result = {}

    result = await process_mining_etl_service(
        db = db,
        file_content = file_content,
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
