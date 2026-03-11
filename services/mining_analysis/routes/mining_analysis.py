'''
    Mining Analysis: routes handler
'''
from typing import List, Optional
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
from services.db_connection import get_db_dependency
from services.security import get_current_user
from controllers.mining_analysis import (
    bulk_upload_mining_controller,
    get_mineral_prices_controller,
    get_royalties_summary_controller,
    upload_royalties_controller
)
from schemas.mining_analysis import (
    MiningPriceResponseSchema,
    BulkUploadMiningResponseSchema,
    RoyaltySummaryResponse
)

router = APIRouter(prefix = '/v1/mining-analysis', tags = ['Mining Analysis'])

@router.post(
    '/etl/upload',
    response_model = BulkUploadMiningResponseSchema,
    status_code = status.HTTP_201_CREATED
)
async def upload_mining_data_endpoint(
    request: Request,
    file: UploadFile = File(...),
    delimiter: str = Query(',', description = 'Separador de campos del CSV'),
    db: Session = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user)
):
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
    db: Session = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user)
):
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
    db: Session = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user)
):
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
    db: Session = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user)
):
    ''' Retrieves aggregated royalties data. '''
    message = f'User: {current_user}. Requested royalties summary.'
    logger.info(message)

    return await get_royalties_summary_controller(
        db = db,
        request = request,
        current_user = current_user,
        year = year
    )
