'''
    Daily stock — orchestration between the HTTP layer and `services.daily_stock`.
    The sale side has no controller of its own: sales arrive on the visit
    (`register_executed_point_controller`) and draw the stock down from there.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.daily_stock import (
    DailyStockFromIngestSchema,
    DailyStockLoadSchema,
    DailyStockResponseSchema
)
from services.daily_stock import (
    fetch_stock_from_ingest,
    get_daily_stock,
    load_daily_stock,
    to_daily_stock_response
)
from services.utils import audit_event, handle_service_errors


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'DailyStock', 'LOAD')
async def load_daily_stock_controller(
    dynamodb_resource: ServiceResource,
    load: DailyStockLoadSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> DailyStockResponseSchema:
    '''
        Loads (or replaces) the day's opening stock and returns the day.
    '''
    rows = load_daily_stock(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        load = load
    )
    return to_daily_stock_response(load.date, rows)


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'DailyStock', 'LOAD')
async def load_daily_stock_from_ingest_controller(
    dynamodb_resource: ServiceResource,
    source: DailyStockFromIngestSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> DailyStockResponseSchema:
    '''
        Opens the day from the stock file loaded in INGEST, then loads it
        exactly like the typed stock: same replacement rule, same audit.
    '''
    load = fetch_stock_from_ingest(source = source, auth_token = auth_token)
    rows = load_daily_stock(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        load = load
    )
    return to_daily_stock_response(load.date, rows)


@handle_service_errors('OPTIMIZATION')
async def get_daily_stock_controller(
    dynamodb_resource: ServiceResource,
    day: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> DailyStockResponseSchema:
    '''
        The day's stock with what is left per SKU.
    '''
    rows = get_daily_stock(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        day = day
    )
    return to_daily_stock_response(day, rows)
