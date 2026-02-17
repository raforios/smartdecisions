'''
    Mining Analysis: routes handler
'''
from typing import List
from fastapi import APIRouter, Depends, Request, UploadFile, File, status, Query
from sqlalchemy.orm import Session
from services.db_connection import get_db_dependency
from services.security import get_current_user
from controllers.mining_analysis import (
    bulk_upload_mining_controller,
    get_mineral_prices_controller
)
from schemas.mining_analysis import (
    MiningPriceResponseSchema,
    BulkUploadMiningResponseSchema
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
    delimiter: str = Query(',', description = "Separador de campos del CSV"),
    db: Session = Depends(get_db_dependency),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to trigger the mining data ETL process from a CSV file.
    '''

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
    return await get_mineral_prices_controller(
        db = db,
        request = request,
        current_user = current_user
    )
