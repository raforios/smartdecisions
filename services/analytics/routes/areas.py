'''
    Analytics: the views that gather an area — the main dashboard, the
    inventory over time and the purchases. Same prefix and same window as the
    rest of the analyses.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path, Request, status

from controllers.analytics import stock_history_controller
from controllers.client_card import client_card_controller, client_list_controller
from controllers.dashboard import dashboard_controller
from controllers.purchases import purchases_controller
from routes.analytics import DateWindow
from schemas.client import ClientCardResponse, ClientListResponse
from schemas.dashboard import DashboardResponse
from schemas.purchases import PurchasesResponse
from schemas.stock import StockHistoryResponse
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner

router = APIRouter(prefix = '/v1/analytics', tags = ['Analytics'])


@router.get(
    '/dashboard/{dataset_id}',
    response_model = DashboardResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Main dashboard: the salient figure of each area',
    description = (
        'Sales of the last month against the previous one and the same month a '
        'year earlier (each at its close), attainment and gross margin; clients '
        'who bought, at risk, new and lost; the stock photo; the credit book; and '
        'today\'s official dollar and USDT with the gap between them. Read-only.'
    )
)
async def dashboard_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> DashboardResponse:
    '''
        Endpoint returning the main dashboard for a dataset_id.
    '''
    message = f'Dashboard for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await dashboard_controller(dynamodb_resource, dataset_id, window.as_params(),
                                      current_user, request)

@router.get(
    '/stock-history/{dataset_id}',
    response_model = StockHistoryResponse,
    status_code = status.HTTP_200_OK,
    summary = 'The inventory over time',
    description = (
        'One row per stored stock photo, oldest first: products, units, value at '
        'cost and at sale price in the dollars of its own day, and the same at '
        'today\'s rate. Read-only.'
    )
)
async def stock_history_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> StockHistoryResponse:
    '''
        Endpoint returning the stock history of a dataset_id.
    '''
    message = f'Stock history for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await stock_history_controller(dynamodb_resource, dataset_id, window.as_params(),
                                          current_user, request)

@router.get(
    '/purchases/{dataset_id}',
    response_model = PurchasesResponse,
    status_code = status.HTTP_200_OK,
    summary = 'What the merchandise costs',
    description = (
        'For each product, its last purchase at the rate of its own day against '
        'the previous ones, the same purchase at today\'s rate and the difference, '
        'and the margin at the latest sale price. The last month of purchases, at '
        'its close. Read-only.'
    )
)
async def purchases_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> PurchasesResponse:
    '''
        Endpoint returning the purchases view of a dataset_id.
    '''
    message = f'Purchases for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await purchases_controller(dynamodb_resource, dataset_id, window.as_params(),
                                      current_user, request)


@router.get(
    '/clients/{dataset_id}',
    response_model = ClientListResponse,
    status_code = status.HTTP_200_OK,
    summary = 'The clients of a dataset, the largest first',
    description = 'To find a client and open its card. Read-only.'
)
async def client_list_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ClientListResponse:
    '''
        Endpoint returning the clients of a dataset_id.
    '''
    message = f'Client list of dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await client_list_controller(dynamodb_resource, dataset_id, window.as_params(),
                                        current_user, request)


@router.get(
    '/client/{dataset_id}/{client_id}',
    response_model = ClientCardResponse,
    status_code = status.HTTP_200_OK,
    summary = 'The card of one client',
    description = (
        'Who the client is, what and how much it buys month by month (each month '
        'at its close), what it owes and the timeline of its invoices and payments. '
        'A client not in the dataset answers CLIENT_NOT_FOUND. Read-only.'
    )
)
async def client_card_endpoint(
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    client_id: str = Path(..., min_length = 1, max_length = 64),
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ClientCardResponse:
    '''
        Endpoint returning the card of one client.
    '''
    message = f'Card of client {client_id} in dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await client_card_controller(dynamodb_resource, dataset_id, client_id,
                                        window.as_params(), current_user)
