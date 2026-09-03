'''
    QUOTES: routes handler
'''
from datetime import date as date_type
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status

from controllers.quotes import (
    get_history_controller,
    sale_scenario_controller,
    sync_rates_controller
)
from models.quotes import USD
from schemas.quotes import (
    ExchangeRateHistory,
    SaleScenario,
    SaleScenarioRequest,
    SyncResult
)
from services.logger_config import custom_logger as logger
from services.security import get_current_user


router = APIRouter(prefix = '/v1/quotes', tags = ['Quotes'])


@router.get(
    '/exchange-rates',
    response_model = ExchangeRateHistory,
    status_code = status.HTTP_200_OK,
    summary = 'Official exchange-rate history.',
    description = 'Returns the stored series of the official rate published by '
                  'the Banco Central de Bolivia. Without a lower bound the '
                  'series starts on 27/06/2026, when the rate stopped being '
                  'fixed: the years before that belong to a different regime '
                  'and are not comparable with what came after.'
)
async def get_exchange_rates_endpoint(
    request: Request,
    date_from: Optional[date_type] = Query(
        None, description = 'Inclusive start (YYYY-MM-DD).'
    ),
    date_to: Optional[date_type] = Query(
        None, description = 'Inclusive end (YYYY-MM-DD).'
    ),
    currency: str = Query(USD, min_length = 3, max_length = 3,
                          description = 'ISO 4217 code.'),
    current_user: str = Depends(get_current_user)
) -> ExchangeRateHistory:
    ''' Endpoint returning the stored exchange-rate series. '''
    message = f'User: {current_user}. Requested the {currency} rate history.'
    logger.info(message)

    return await get_history_controller(
        date_from = date_from,
        date_to = date_to,
        currency = currency,
        current_user = current_user,
        request = request
    )


@router.post(
    '/exchange-rates/sync',
    response_model = SyncResult,
    status_code = status.HTTP_201_CREATED,
    summary = 'Pull recently published rates into our history.',
    description = 'Reads the Banco Central de Bolivia one date at a time and '
                  'stores what it publishes. Dates already held are skipped, so '
                  'running it twice costs nothing.'
)
async def sync_exchange_rates_endpoint(
    request: Request,
    days_back: int = Query(30, ge = 1, le = 400,
                           description = 'Days back from today to cover.'),
    currency: str = Query(USD, min_length = 3, max_length = 3,
                          description = 'ISO 4217 code.'),
    current_user: str = Depends(get_current_user)
) -> SyncResult:
    ''' Endpoint that refreshes the stored exchange-rate history. '''
    message = (f'User: {current_user}. Requested a {days_back}-day '
               f'{currency} rate sync.')
    logger.info(message)

    return await sync_rates_controller(
        days_back = days_back,
        currency = currency,
        current_user = current_user,
        request = request
    )


@router.post(
    '/sale-scenario',
    response_model = SaleScenario,
    status_code = status.HTTP_200_OK,
    summary = 'Selling today against waiting.',
    description = 'Prices the same sale under today\'s official rate and under '
                  'the projected one, and returns the difference in bolivianos. '
                  'Supply the mineral\'s expected change (from the '
                  'MINING_ANALYSIS projection) to weigh both movements together; '
                  'omit it to price the currency move alone.'
)
async def sale_scenario_endpoint(
    request: Request,
    scenario: SaleScenarioRequest,
    current_user: str = Depends(get_current_user)
) -> SaleScenario:
    ''' Endpoint comparing a sale settled today against one settled later. '''
    message = (f'User: {current_user}. Requested a sale scenario over '
               f'{scenario.days_ahead} day(s).')
    logger.info(message)

    return await sale_scenario_controller(
        scenario = scenario,
        current_user = current_user,
        request = request
    )
