'''
    Market side of the quotations — HTTP layer: daily market prices from the
    public sources, the anticipated official quotation, and the Art. 227 scales.
'''
from datetime import date as date_type
from typing import Optional

from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path, Query, Request, status

from controllers.market import (
    estimate_controller,
    list_rules_controller,
    market_series_controller,
    save_rule_controller,
    sync_market_controller
)
from schemas.market import (
    EstimateResponse,
    MarketPricesResponse,
    MarketSyncResult,
    MarketWindow,
    RoyaltyRuleSchema,
    RoyaltyRulesResponse
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.market_sources import MARKET_SYNC_DAYS
from services.security import get_current_owner, require_roles

router = APIRouter(prefix = '/v1/mining-analysis', tags = ['Market quotations'])

# Editing the legal scale is an administrator's act; reading is for everyone.
RULE_EDITORS = ('ADMIN', 'MANAGER')


def market_window(
    date_from: Optional[date_type] = Query(None, description = 'First day; open when absent.'),
    date_to: Optional[date_type] = Query(None, description = 'Last day; open when absent.')
) -> MarketWindow:
    '''
        The date range of the series as one argument.

        Grouped as a dependency rather than two loose query parameters because
        they are one concept: they travel together, they are validated
        together, and the endpoint stays within the argument budget.

        Args:
            date_from (date | None): First day of the window.
            date_to (date | None): Last day of the window.

        Returns:
            MarketWindow: The range the controller receives.
    '''
    return MarketWindow(date_from = date_from, date_to = date_to)


@router.post(
    '/market/sync',
    response_model = MarketSyncResult,
    status_code = status.HTTP_200_OK,
    summary = 'Read the public sources and store the missing days',
    description = 'LBMA fixes (gold AM, silver) and LME cash via Westmetall (Cu, Sn, Pb, Zn). '
                  'Idempotent: days already stored are skipped.'
)
async def sync_market_endpoint(
    request: Request,
    days_back: int = Query(MARKET_SYNC_DAYS, ge = 1, le = 400,
                           description = 'Window ending today.'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*RULE_EDITORS))
) -> MarketSyncResult:
    '''
        Endpoint to sync the market series.
    '''
    message = f'User: {current_user}. Market sync over {days_back} day(s).'
    logger.info(message)
    return await sync_market_controller(
        dynamodb_resource = dynamodb_resource, days_back = days_back,
        request = request, current_user = current_user
    )


@router.get(
    '/market/estimate',
    response_model = EstimateResponse,
    status_code = status.HTTP_200_OK,
    summary = 'The official quotation each mineral is heading to',
    description = 'Running mean of the fortnight in progress against the quotation in force, '
                  'with the Art. 227 royalty rate it implies.'
)
async def estimate_endpoint(
    request: Request,
    as_of: Optional[date_type] = Query(None,
                                       description = 'Day of the estimate; today by default.'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> EstimateResponse:
    '''
        Endpoint for the anticipated official quotation.
    '''
    message = f'User: {current_user}. Official estimate as of {as_of or "today"}.'
    logger.info(message)
    return await estimate_controller(
        dynamodb_resource = dynamodb_resource, as_of = as_of,
        request = request, current_user = current_user
    )


@router.get(
    '/market/prices/{mineral_id}',
    response_model = MarketPricesResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Daily market series of one mineral'
)
async def market_series_endpoint(
    request: Request,
    mineral_id: str = Path(..., min_length = 1, max_length = 16),
    window: MarketWindow = Depends(market_window),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> MarketPricesResponse:
    '''
        Endpoint for the market series.
    '''
    message = f'User: {current_user}. Market series of mineral {mineral_id}.'
    logger.info(message)
    return await market_series_controller(
        dynamodb_resource = dynamodb_resource, mineral_id = mineral_id,
        window = window, request = request, current_user = current_user
    )


@router.get(
    '/royalty-rules',
    response_model = RoyaltyRulesResponse,
    status_code = status.HTTP_200_OK,
    summary = 'The Art. 227 scales in force'
)
async def list_rules_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> RoyaltyRulesResponse:
    '''
        Endpoint to read the royalty scales.
    '''
    message = f'User: {current_user}. Reading royalty rules.'
    logger.info(message)
    return await list_rules_controller(
        dynamodb_resource = dynamodb_resource,
        request = request, current_user = current_user
    )


@router.put(
    '/royalty-rules',
    response_model = RoyaltyRuleSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Create or replace the scale of one mineral'
)
async def save_rule_endpoint(
    request: Request,
    rule: RoyaltyRuleSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*RULE_EDITORS))
) -> RoyaltyRuleSchema:
    '''
        Endpoint to edit a royalty scale.
    '''
    message = f'User: {current_user}. Saving royalty rule of mineral {rule.mineral_id}.'
    logger.info(message)
    return await save_rule_controller(
        dynamodb_resource = dynamodb_resource, rule = rule,
        request = request, current_user = current_user
    )
