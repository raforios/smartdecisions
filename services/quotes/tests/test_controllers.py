'''
    Controller-level tests: every QUOTES endpoint must return its response model
    fully built.

    These exist because the domain tests alone did not catch a real production
    failure in the sibling services: the services were changed to return DTOs
    while the controllers still spread them with `**`, which raises TypeError
    only when the endpoint runs. The domain stayed green; the API returned 500.
'''
import asyncio
from unittest.mock import patch

from models.quotes import USD
from schemas.quotes import (
    ExchangeRateHistory,
    SaleScenario,
    SaleScenarioRequest,
    SyncResult
)
from controllers import quotes as controllers
from services import quotes


def _run(coroutine):
    '''
        Runs a coroutine without extra plugins, as the domain tests do.

        Args:
            coroutine: The coroutine to execute.

        Returns:
            Any: Whatever the coroutine returns.
    '''
    return asyncio.run(coroutine)


def test_history_controller_returns_its_model(seeded_store): # pylint: disable=unused-argument
    '''The history endpoint answers a fully built ExchangeRateHistory.'''
    response = _run(controllers.get_history_controller(
        date_from = None, date_to = None,
        current_user = 'tester', request = None
    ))

    assert isinstance(response, ExchangeRateHistory)
    assert response.days == 60
    assert response.rates[0].date < response.rates[-1].date


def test_sync_controller_returns_its_model(seeded_store): # pylint: disable=unused-argument
    '''The sync endpoint answers a fully built SyncResult.'''
    with patch.object(quotes, 'fetch_official_rate', lambda day: 12.32):
        response = _run(controllers.sync_rates_controller(
            days_back = 2, currency = USD,
            current_user = 'tester', request = None
        ))

    assert isinstance(response, SyncResult)
    assert response.stored + response.already_present + \
        response.without_publication == response.requested_days


def test_scenario_controller_returns_its_model(seeded_store): # pylint: disable=unused-argument
    '''
        The scenario endpoint answers a fully built SaleScenario, nested
        outcomes included: the failure this guards against is exactly a nested
        payload that never gets coerced into its model.
    '''
    response = _run(controllers.sale_scenario_controller(
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
