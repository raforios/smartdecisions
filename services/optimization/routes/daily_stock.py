'''
    Daily stock — HTTP layer. Sales are not posted here: they travel on the
    visit (`POST /routes/executed/points`) and draw the stock down.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path, Request, status

from controllers.daily_stock import get_daily_stock_controller, load_daily_stock_controller
from schemas.daily_stock import DailyStockLoadSchema, DailyStockResponseSchema
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/optimization', tags = ['Daily stock'])

_DAY = Path(..., pattern = r'^\d{4}-\d{2}-\d{2}$', description = 'YYYY-MM-DD.')


@router.put(
    '/stock/day',
    response_model = DailyStockResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Load the opening stock of a day',
    description = 'One row per SKU with the units the company has when the day starts. '
                  'Loading the same day again replaces it; sales already registered '
                  'that day are kept for the SKUs still present.'
)
async def load_daily_stock_endpoint(
    request: Request,
    load: DailyStockLoadSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to load the day's stock.
    '''
    message = f'User: {current_user}. Loading stock of {load.date}: {len(load.items)} SKU(s).'
    logger.info(message)
    return await load_daily_stock_controller(
        dynamodb_resource = dynamodb_resource,
        load = load,
        current_user = current_user,
        request = request
    )


@router.get(
    '/stock/day/{day}',
    response_model = DailyStockResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'What is left of the day\'s stock, per SKU'
)
async def get_daily_stock_endpoint(
    request: Request,
    day: str = _DAY,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to read the day's stock.
    '''
    message = f'User: {current_user}. Reading stock of {day}.'
    logger.info(message)
    return await get_daily_stock_controller(
        dynamodb_resource = dynamodb_resource,
        day = day,
        current_user = current_user,
        request = request
    )
