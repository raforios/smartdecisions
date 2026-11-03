'''
    Controller-level tests: every MINING_ANALYSIS endpoint must return its
    response model fully built.

    These exist because the domain tests alone did not catch a real production
    failure in the sibling services: the services were changed to return DTOs
    while the controllers still spread them with `**`, which raises TypeError
    only when the endpoint runs. The domain stayed green; the API returned 500.

    They run on a simulated DynamoDB (moto) with `request = None`, so no usage
    log leaves for EVENTS; the external sources (Westmetall, LBMA, QUOTES,
    ML_FUNCTIONS) are replaced at their boundary.
'''
import asyncio
from datetime import date
from unittest.mock import patch

import pytest
from moto import mock_aws

from controllers import market as market_controllers
from controllers import mining_analysis as controllers
from models.mining_analysis import MiningPriceItem
from schemas.market import (
    EstimateResponse,
    MarketPricesResponse,
    MarketSyncResult,
    MarketWindow,
    RoyaltyRulesResponse,
    SaleScenario,
    SaleScenarioRequest
)
from schemas.mining_analysis import (
    BiweeklyHistoryResponse,
    BiweeklyReportResponse,
    DailyReportResponse,
    ForecastMethod,
    MiningPriceResponseSchema,
    PriceForecastResponse
)
from services import market_sources, prices_dyb
from services.mining_analysis import normalize_name
from tests.dynamo_helpers import (
    build_market_tables,
    build_quotation_tables,
    seed_official_catalog
)

# Two days of tin, enough for every report to have a row with data.
TIN_PRICES = ((date(2026, 4, 10), 21.0), (date(2026, 4, 11), 22.0))
RATE_FORECAST = {'last_rate': 10.0, 'final_rate': 11.0, 'confidence': 'MEDIUM',
                 'change_percent': 10.0}


def _run(coroutine):
    '''
        Runs a coroutine without extra plugins, as the domain tests do.

        Args:
            coroutine: The coroutine to execute.

        Returns:
            Any: Whatever the coroutine returns.
    '''
    return asyncio.run(coroutine)


@pytest.fixture(name = 'store')
def _store():
    '''
        The four tables of the service, mocked, with the official catalogue and
        two tin quotations.
    '''
    with mock_aws():
        resource = build_market_tables(build_quotation_tables())
        tin_id = seed_official_catalog(resource)[normalize_name('Estaño')]
        prices_dyb.put_prices_batch(resource, [
            MiningPriceItem(mineral_id = tin_id, date = day, price_low = price,
                            price_high = price)
            for day, price in TIN_PRICES
        ])
        yield resource


def test_prices_controller_returns_its_model(store):
    '''The full export answers one built schema per stored quotation.'''
    response = _run(controllers.get_mineral_prices_controller(
        dynamodb_resource = store, request = None, current_user = 'tester'
    ))
    assert len(response) == len(TIN_PRICES)
    assert all(isinstance(row, MiningPriceResponseSchema) for row in response)


def test_daily_report_controller_returns_its_model(store):
    '''The daily report answers a fully built DailyReportResponse.'''
    response = _run(controllers.get_daily_report_controller(
        dynamodb_resource = store, request = None, current_user = 'tester',
        ref_date = date(2026, 4, 11)
    ))
    assert isinstance(response, DailyReportResponse)


def test_biweekly_report_controller_returns_its_model(store):
    '''The fortnightly report answers a fully built BiweeklyReportResponse.'''
    response = _run(controllers.get_biweekly_report_controller(
        dynamodb_resource = store, request = None, current_user = 'tester',
        year = 2026, month = 4, half = 1
    ))
    assert isinstance(response, BiweeklyReportResponse)


def test_biweekly_history_controller_returns_its_model(store):
    '''The fortnightly history answers a fully built BiweeklyHistoryResponse.'''
    response = _run(controllers.get_biweekly_history_controller(
        dynamodb_resource = store, request = None, current_user = 'tester'
    ))
    assert isinstance(response, BiweeklyHistoryResponse)


def test_price_forecast_controller_returns_its_model(store):
    '''
        The projection answers a fully built PriceForecastResponse. Two days of
        history are too few to project, so ML_FUNCTIONS is never asked.
    '''
    response = _run(controllers.get_price_forecast_controller(
        dynamodb_resource = store, request = None, current_user = 'tester',
        days_ahead = 30, method = ForecastMethod.DAMPED_TREND
    ))
    assert isinstance(response, PriceForecastResponse)


def test_sync_market_controller_returns_its_model(store):
    '''With no source for any mineral, the sync still answers its result.'''
    with patch.object(market_sources, 'source_for', lambda name: None):
        response = _run(market_controllers.sync_market_controller(
            dynamodb_resource = store, days_back = 3, request = None,
            current_user = 'tester'
        ))
    assert isinstance(response, MarketSyncResult)
    assert response.stored == 0


def test_estimate_controller_returns_its_model(store):
    '''The anticipated quotation answers a fully built EstimateResponse.'''
    response = _run(market_controllers.estimate_controller(
        dynamodb_resource = store, as_of = date(2026, 4, 20), request = None,
        current_user = 'tester'
    ))
    assert isinstance(response, EstimateResponse)


def test_market_series_controller_returns_its_model(store):
    '''A mineral with a market source answers its (here empty) series.'''
    copper_id = seed_official_catalog(store)[normalize_name('Cobre')]
    response = _run(market_controllers.market_series_controller(
        dynamodb_resource = store, mineral_id = copper_id, window = MarketWindow(),
        request = None, current_user = 'tester'
    ))
    assert isinstance(response, MarketPricesResponse)


def test_list_rules_controller_returns_its_model(store):
    '''The Art. 227 scales are seeded on first read and returned built.'''
    response = _run(market_controllers.list_rules_controller(
        dynamodb_resource = store, request = None, current_user = 'tester'
    ))
    assert isinstance(response, RoyaltyRulesResponse)
    assert response.rules


def test_sale_scenario_controller_returns_its_model():
    '''«Vender hoy o esperar» answers a fully built SaleScenario.'''
    with patch.object(market_controllers, 'rate_forecast', lambda days, token: RATE_FORECAST):
        response = _run(market_controllers.preview_sale_scenario_controller(
            scenario = SaleScenarioRequest(quantity = 10, unit_price_usd = 100),
            current_user = 'tester', request = None
        ))
    assert isinstance(response, SaleScenario)
