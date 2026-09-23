'''
    Market side of the quotations — orchestration between the HTTP layer and
    `services.market_sources`, `services.official_estimate` and
    `services.royalty_rules`.

    The market tables live on DynamoDB whatever the persistence backend of the
    official series, so no relational session is needed here; `request` and
    `current_user` are consumed by @handle_service_errors for the usage log.
'''
from datetime import date as date_type
from typing import Optional

from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.market import (
    EstimateResponse,
    MarketPricesResponse,
    MarketSyncResult,
    MarketWindow,
    RoyaltyRuleSchema,
    RoyaltyRulesResponse
)
from services.market_sources import sync_market_prices
from services.official_estimate import estimate_all, market_series
from services.royalty_rules import ensure_rules, save_rule, to_rule_schema
from services.utils import audit_event, handle_service_errors


@handle_service_errors('MINING_ANALYSIS')
@audit_event('MINING_ANALYSIS', 'MarketPrice', 'SYNC')
async def sync_market_controller(
    dynamodb_resource: ServiceResource,
    days_back: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> MarketSyncResult:
    '''
        Reads the public sources and stores the missing days of the window.
    '''
    return sync_market_prices(dynamodb_resource, days_back)


@handle_service_errors('MINING_ANALYSIS')
async def estimate_controller(
    dynamodb_resource: ServiceResource,
    as_of: Optional[date_type],
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> EstimateResponse:
    '''
        The official quotation every mineral is heading to.
    '''
    return estimate_all(dynamodb_resource, as_of)


@handle_service_errors('MINING_ANALYSIS')
async def market_series_controller(
    dynamodb_resource: ServiceResource,
    mineral_id: str,
    window: MarketWindow,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> MarketPricesResponse:
    '''
        The stored market series of one mineral.
    '''
    return market_series(dynamodb_resource, mineral_id,
                         window.date_from, window.date_to)


@handle_service_errors('MINING_ANALYSIS')
async def list_rules_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> RoyaltyRulesResponse:
    '''
        The Art. 227 scales in force (seeded on first read).
    '''
    return RoyaltyRulesResponse(
        rules = [to_rule_schema(rule) for rule in ensure_rules(dynamodb_resource)]
    )


@handle_service_errors('MINING_ANALYSIS')
@audit_event('MINING_ANALYSIS', 'RoyaltyRule', 'UPSERT')
async def save_rule_controller(
    dynamodb_resource: ServiceResource,
    rule: RoyaltyRuleSchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> RoyaltyRuleSchema:
    '''
        Creates or replaces one scale.
    '''
    return to_rule_schema(save_rule(dynamodb_resource, rule))
