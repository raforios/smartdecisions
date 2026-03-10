'''
    Mining Analysis Controllers
'''
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
    current_user: str
) -> RoyaltySummaryResponse:
    '''
        Controller to orchestrate the retrieval of royalty summaries.
        Strictly handles telemetry and response formatting, delegating DB
        logic to the service layer.
    '''

    message = f'User: {current_user}. Executing get_royalties_summary_controller.'
    logger.info(message)

    # --- DELEGACIÓN ESTRICTA A LA CAPA DE SERVICIOS ---
    data = await get_royalties_summary_service(db)

    return RoyaltySummaryResponse(status = 'success', data = data)


@handle_service_errors('MINING_ANALYSIS')
async def upload_royalties_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    file_name: str,
    file_content: bytes
) -> Dict[str, Any]:
    '''
        Controller to handle in-memory bulk upload of Royalties.
    '''
    message = f'Starting in-memory ETL for file: {file_name}'
    logger.info(message)

    # 1. Procesamiento directo en la capa de servicios
    result = await process_royalties_excel_service(db, file_content)

    # 2. Auditoría Manual Segura (Evita el Error 500 del decorador tratando de leer bytes)
    _trigger_bulk_audit(
        microservice = 'MINING_ANALYSIS',
        entity = 'RoyaltyPayment',
        user = current_user,
        result = result
    )

    return result
