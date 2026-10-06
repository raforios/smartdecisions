'''
    Controller-level tests: every QUOTES endpoint must return its response model
    fully built.

    These exist because the domain tests alone did not catch a real production
    failure in the sibling services: the services were changed to return DTOs
    while the controllers still spread them with `**`, which raises TypeError
    only when the endpoint runs. The domain stayed green; the API returned 500.
'''
import asyncio
from datetime import date
from unittest.mock import patch

import pytest

from models.quotes import USD, ExchangeRateItem
from schemas.factors import (
    FactorDefinitionSchema,
    FactorListResponseSchema,
    FactorResponseSchema,
    FactorSeriesResponseSchema,
    FactorStateSchema,
    FactorStatus,
    FactorValueSchema,
    FactorValuesLoadSchema,
    TransportCostSchema
)
from schemas.quotes import (
    ExchangeRateHistory,
    ModelBench,
    RateForecast,
    RateOnDate,
    SaleScenario,
    SaleScenarioRequest,
    SyncResult
)
from controllers import quotes as controllers
from routes import factors as factor_routes
from services import factors, quotes


def _run(coroutine):
    '''
        Runs a coroutine without extra plugins, as the domain tests do.

        Args:
            coroutine: The coroutine to execute.

        Returns:
            Any: Whatever the coroutine returns.
    '''
    return asyncio.run(coroutine)


def test_history_controller_returns_its_model(
    seeded_store # pylint: disable=unused-argument
):
    '''The history endpoint answers a fully built ExchangeRateHistory.'''
    response = _run(controllers.get_history_controller(
        date_from = None, date_to = None,
        current_user = 'tester', request = None
    ))

    assert isinstance(response, ExchangeRateHistory)
    assert response.days == 60
    assert response.rates[0].date < response.rates[-1].date


@pytest.mark.usefixtures('midweek')
def test_sync_controller_returns_its_model(
    seeded_store # pylint: disable=unused-argument
):
    '''The sync endpoint answers a fully built SyncResult.'''
    with patch.object(quotes, 'fetch_official_rate', lambda day: 12.32):
        response = _run(controllers.sync_rates_controller(
            days_back = 2, currency = USD,
            current_user = 'tester', request = None
        ))

    assert isinstance(response, SyncResult)
    assert response.stored + response.already_present + \
        response.without_publication == response.requested_days


def test_scenario_controller_returns_its_model(
    seeded_store # pylint: disable=unused-argument
):
    '''
        The scenario endpoint answers a fully built SaleScenario, nested
        outcomes included: the failure this guards against is exactly a nested
        payload that never gets coerced into its model.
    '''
    response = _run(controllers.preview_sale_scenario_controller(
        scenario = SaleScenarioRequest(
            quantity = 10, unit_price_usd = 100,
            days_ahead = 30, mineral_change_percent = -5.0
        ),
        current_user = 'tester',
        request = None
    ))

    assert isinstance(response, SaleScenario)
    assert response.today.amount_bob > 0
    assert response.projected is not None
    assert response.projected.mineral_price == 95.0
    assert response.difference_bob is not None


def test_declaring_a_factor_answers_its_model(factor_store):
    '''
        The ROUTE, not just the controller, must survive a declaration.

        This is where a removed field hid: the endpoint logged
        `definition.weight` after `weight` was taken out of the schema, so
        every declaration raised AttributeError while the domain suite stayed
        green. Controller tests could not see it — the line was in the route.
    '''
    response = _run(factor_routes.declare_factor_endpoint(
        request = None,
        definition = FactorDefinitionSchema(
            code = 'DIESEL', name = 'Precio del diesel', unit = 'Bs/litro'
        ),
        dynamodb_resource = factor_store,
        current_user = 'tester'
    ))

    assert isinstance(response, FactorResponseSchema)
    assert (response.code, response.status) == ('DIESEL', FactorStatus.ACTIVE)


def test_every_read_only_factor_route_answers_its_model(factor_store):
    '''
        Listing, series, state and transport cost, called as the API calls
        them. One reading of each factor is enough: what is under test is the
        wiring of the route, not the arithmetic, which `test_factors` owns.
    '''
    for code, name, unit, value in (
        ('DIESEL', 'Precio del diesel', 'Bs/litro', 20.0),
        (factors.FUEL_EFFICIENCY_CODE, 'Rendimiento', 'Km/litro', 10.0)
    ):
        _run(factor_routes.declare_factor_endpoint(
            request = None,
            definition = FactorDefinitionSchema(
                code = code, name = name, unit = unit,
                effective_from = date(2026, 1, 1)
            ),
            dynamodb_resource = factor_store, current_user = 'tester'
        ))
        _run(factor_routes.load_factor_values_endpoint(
            request = None, code = code,
            load = FactorValuesLoadSchema(
                values = [FactorValueSchema(factor_date = date(2026, 9, 1), value = value)]
            ),
            dynamodb_resource = factor_store, current_user = 'tester'
        ))

    listed = _run(factor_routes.list_factors_endpoint(
        request = None, only_active = True,
        dynamodb_resource = factor_store, current_user = 'tester'
    ))
    series = _run(factor_routes.read_factor_series_endpoint(
        request = None, code = 'DIESEL', start = None, end = None,
        dynamodb_resource = factor_store, current_user = 'tester'
    ))
    state = _run(factor_routes.read_factor_state_endpoint(
        request = None, code = 'DIESEL', day = date(2026, 9, 15),
        dynamodb_resource = factor_store, current_user = 'tester'
    ))
    cost = _run(factor_routes.transport_cost_endpoint(
        request = None, km = 100.0, day = date(2026, 9, 15), units = 1000.0,
        dynamodb_resource = factor_store, current_user = 'tester'
    ))

    assert isinstance(listed, FactorListResponseSchema) and listed.total == 2
    assert isinstance(series, FactorSeriesResponseSchema) and series.values[0].value == 20.0
    assert isinstance(state, FactorStateSchema) and state.active and state.value == 20.0
    assert isinstance(cost, TransportCostSchema)
    assert (cost.round_trip_km, cost.cost, cost.cost_per_unit) == (200.0, 400.0, 0.4)


def test_rate_on_a_day_controller_returns_its_model(
    seeded_store # pylint: disable=unused-argument
):
    '''The rate in force on one day, which every dated report reads.'''
    response = _run(controllers.get_rate_on_controller(
        day = date(2026, 7, 15), currency = USD,
        current_user = 'tester', request = None
    ))

    assert isinstance(response, RateOnDate)
    assert response.rate > 0


def test_forecast_and_bench_controllers_return_their_models(
    seeded_store # pylint: disable=unused-argument
):
    '''The projection and the model comparison behind it.'''
    forecast = _run(controllers.get_forecast_controller(
        days_ahead = 30, currency = USD, current_user = 'tester', request = None
    ))
    bench = _run(controllers.get_bench_controller(
        days_ahead = 30, currency = USD, models = None,
        current_user = 'tester', request = None
    ))

    assert isinstance(forecast, RateForecast)
    assert isinstance(bench, ModelBench)


def test_the_history_endpoint_accepts_the_usdt_series(store):
    '''
        ANALYTICS asks for the USDT series by its code; a three-letter limit
        answered it with a 422 before the service was ever reached.
    '''
    # pylint: disable=import-outside-toplevel
    from fastapi.testclient import TestClient

    from main import app
    from services.security import get_current_owner

    store[(quotes.PARALLEL_CURRENCY, date(2026, 10, 5))] = ExchangeRateItem(
        currency = quotes.PARALLEL_CURRENCY, date = date(2026, 10, 5),
        official_rate = 11.99, source = 'BINANCE_P2P', retrieved_at = '2026-10-05T09:00:00'
    )
    app.dependency_overrides[get_current_owner] = lambda: 'tester'
    try:
        response = TestClient(app).get('/v1/quotes/exchange-rates', params = {
            'currency': 'USDT', 'start': '2026-10-01', 'end': '2026-10-06'})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert [point['rate'] for point in response.json()['rates']] == [11.99]
