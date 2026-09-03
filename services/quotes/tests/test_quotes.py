'''
    Tests for the QUOTES domain.

    The exchange rate is the figure a sale is settled at, so the cases that
    matter are the ones where a wrong answer would be believed: a source that
    changed shape, a weekend with no publication, and the regime change of June
    2026 that makes the older history unusable for projection.
'''
import asyncio
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from fastapi import HTTPException

from models.quotes import USD, ExchangeRateItem
from schemas.quotes import QuotesError, RateConfidence
from services import bcb_source, quotes
from services.exceptions import ServiceUnavailableError

from tests.conftest import build_history


def _run(coroutine):
    '''
        Runs a coroutine, the way the TRADE tests do, without extra plugins.

        Args:
            coroutine: The coroutine to execute.

        Returns:
            Any: Whatever the coroutine returns.
    '''
    return asyncio.run(coroutine)


def test_sync_stores_what_the_source_publishes(store):
    '''Every published date is written once, with its source recorded.'''
    with patch.object(quotes, 'fetch_official_rate', lambda day: 12.26):
        result = _run(quotes.sync_rates_service(days_back = 3))

    assert result['stored'] == 3
    assert result['already_present'] == 0
    assert len(store) == 3
    assert all(item.source == bcb_source.SOURCE_NAME for item in store.values())


def test_sync_does_not_refetch_what_is_already_stored(store): # pylint: disable=unused-argument
    '''
        A published rate is never revised, so re-reading it would only spend
        requests against a source that answers one date at a time.
    '''
    with patch.object(quotes, 'fetch_official_rate', lambda day: 12.26):
        _run(quotes.sync_rates_service(days_back = 3))

    calls = []

    def _counted(day):
        calls.append(day)
        return 12.26

    with patch.object(quotes, 'fetch_official_rate', _counted):
        result = _run(quotes.sync_rates_service(days_back = 3))

    assert not calls
    assert result['already_present'] == 3
    assert result['stored'] == 0


def test_dates_without_publication_are_counted_not_failed(store):
    '''A weekend with no table is an absence, never an error.'''
    with patch.object(quotes, 'fetch_official_rate', lambda day: None):
        result = _run(quotes.sync_rates_service(days_back = 4))

    assert result['without_publication'] == 4
    assert result['stored'] == 0
    assert not store


def test_sync_rejects_an_out_of_bounds_window(store): # pylint: disable=unused-argument
    '''
        One call cannot walk the source for an unbounded number of days.

        The service raises InvalidInputError and the boilerplate decorator turns
        it into a 400 carrying the code, which is what the client sees.
    '''
    with pytest.raises(HTTPException) as excinfo:
        _run(quotes.sync_rates_service(days_back = quotes.SYNC_MAX_DAYS + 1))

    assert excinfo.value.status_code == 400
    assert QuotesError.INVALID_DATE_RANGE.value in str(excinfo.value.detail)


def test_history_starts_at_the_float_regime_by_default(store):
    '''
        Before 27/06/2026 the rate was fixed at 6.86 for years. Serving both
        regimes as one series would read as a cliff, and fitting a projection
        over it would conclude the rate stays at 6.86.
    '''
    fixed_day = quotes.FLOAT_REGIME_START - timedelta(days = 10)
    float_day = quotes.FLOAT_REGIME_START + timedelta(days = 1)
    for day, rate in ((fixed_day, 6.86), (quotes.FLOAT_REGIME_START, 9.73), (float_day, 9.80)):
        store[(USD, day)] = ExchangeRateItem(USD, day, rate)

    result = _run(quotes.get_history_service())

    assert result['days'] == 2
    assert result['date_from'] == quotes.FLOAT_REGIME_START
    assert all(point['rate'] > 6.86 for point in result['rates'])


def test_history_can_be_asked_for_the_fixed_regime_explicitly(store):
    '''An explicit lower bound overrides the default, for historical reads.'''
    fixed_day = quotes.FLOAT_REGIME_START - timedelta(days = 10)
    store[(USD, fixed_day)] = ExchangeRateItem(USD, fixed_day, 6.86)

    result = _run(quotes.get_history_service(date_from = fixed_day))

    assert result['days'] == 1
    assert result['rates'][0]['rate'] == 6.86


def test_history_rejects_an_inverted_window(store): # pylint: disable=unused-argument
    '''An end before the start is a caller mistake, not an empty series.'''
    with pytest.raises(HTTPException) as excinfo:
        _run(quotes.get_history_service(
            date_from = date(2026, 8, 1), date_to = date(2026, 7, 1)
        ))

    assert excinfo.value.status_code == 400
    assert QuotesError.INVALID_DATE_RANGE.value in str(excinfo.value.detail)


def test_source_reports_an_absent_table_as_no_publication():
    '''A date the BCB does not publish returns nothing, and does not raise.'''
    class _Response: # pylint: disable=too-few-public-methods
        text = '<html><body>Sin informacion</body></html>'

        @staticmethod
        def raise_for_status():
            '''No HTTP error to report.'''

    with patch.object(bcb_source.requests, 'get', lambda *a, **k: _Response()):
        assert bcb_source.fetch_official_rate(date(2026, 9, 2)) is None


def test_source_refuses_to_guess_when_the_page_changes_shape():
    '''
        A redesigned page must stop the sync, not store a number read from the
        wrong cell: a wrong rate poisons every scenario built on it.
    '''
    class _Response: # pylint: disable=too-few-public-methods
        text = ('<html><body>TABLA DE COTIZACIONES '
                '<table><tr><td>otra cosa</td></tr></table></body></html>')

        @staticmethod
        def raise_for_status():
            '''No HTTP error to report.'''

    with patch.object(bcb_source.requests, 'get', lambda *a, **k: _Response()):
        with pytest.raises(ServiceUnavailableError) as excinfo:
            bcb_source.fetch_official_rate(date(2026, 9, 2))

    assert excinfo.value.detail == QuotesError.SOURCE_UNREADABLE.value


def test_scenario_prices_both_paths_when_the_history_supports_it(store):
    '''
        With a rising rate and a flat mineral, waiting is worth more bolivianos
        even though the sale is the same amount of dollars.
    '''
    for item in build_history(60):
        store[(item.currency, item.date)] = item

    result = _run(quotes.sale_scenario_service(
        quantity = 10, unit_price_usd = 100, days_ahead = 30
    ))

    assert result['today']['amount_usd'] == 1000
    assert result['projected']['amount_usd'] == 1000
    assert result['projected']['exchange_rate'] > result['today']['exchange_rate']
    assert result['difference_bob'] > 0
    assert result['rate_change_percent'] > 0


def test_scenario_weighs_a_falling_mineral_against_a_rising_rate(store):
    '''
        The decision is the net of both moves: a mineral falling harder than the
        currency climbs turns waiting into a loss, and that is what the seller
        must see.
    '''
    for item in build_history(60):
        store[(item.currency, item.date)] = item

    result = _run(quotes.sale_scenario_service(
        quantity = 10,
        unit_price_usd = 100,
        days_ahead = 30,
        mineral_change_percent = -25.0
    ))

    assert result['mineral_change_percent'] == -25.0
    assert result['projected']['mineral_price'] == 75.0
    assert result['difference_bob'] < 0
    assert result['difference_percent'] < 0


def test_scenario_answers_today_only_when_history_is_too_thin(store):
    '''
        Below the minimum sample the projection is refused rather than guessed,
        and the caller still gets today's figure plus the reason.
    '''
    for item in build_history(5):
        store[(item.currency, item.date)] = item

    result = _run(quotes.sale_scenario_service(
        quantity = 10, unit_price_usd = 100, days_ahead = 30
    ))

    assert result['projected'] is None
    assert result['difference_bob'] is None
    assert result['difference_percent'] is None
    assert result['rate_confidence'] is RateConfidence.INSUFFICIENT
    assert result['today']['amount_bob'] > 0


def test_scenario_refuses_a_horizon_beyond_the_bound(store):
    '''
        Past a quarter the projection describes the fitted line, not the market.
    '''
    for item in build_history(60):
        store[(item.currency, item.date)] = item

    with pytest.raises(HTTPException) as failure:
        _run(quotes.sale_scenario_service(
            quantity = 10, unit_price_usd = 100,
            days_ahead = quotes.SCENARIO_MAX_DAYS + 1
        ))

    assert QuotesError.INVALID_DATE_RANGE.value in str(failure.value.detail)


def test_scenario_reports_no_rate_when_nothing_is_stored(store): # pylint: disable=unused-argument
    '''
        Without a published rate there is no figure to settle at, and saying so
        is the only honest answer.
    '''
    with pytest.raises(HTTPException) as failure:
        _run(quotes.sale_scenario_service(quantity = 10, unit_price_usd = 100))

    assert QuotesError.NO_RATE_PUBLISHED.value in str(failure.value.detail)


def test_forecast_projects_the_rate_on_its_own(store):
    '''The dollar is a question by itself, not only an input to a sale.'''
    for item in build_history(60):
        store[(item.currency, item.date)] = item

    result = _run(quotes.get_forecast_service(days_ahead = 30))

    assert result['confidence'] is RateConfidence.MEDIUM
    assert len(result['projected']) == 30
    assert result['final_rate'] > result['last_rate']
    assert result['change_percent'] > 0
    # The observed series must travel too, or the chart has nothing to anchor on.
    assert len(result['history']) == 60
    assert result['history'][-1]['date'] < result['projected'][0]['date']


def test_forecast_refuses_to_guess_on_a_thin_history(store):
    '''
        Below the minimum sample the projection is withheld, and the caller is
        told why instead of receiving a line drawn through noise.
    '''
    for item in build_history(5):
        store[(item.currency, item.date)] = item

    result = _run(quotes.get_forecast_service(days_ahead = 30))

    assert result['projected'] == []
    assert result['final_rate'] is None
    assert result['confidence'] is RateConfidence.INSUFFICIENT
    assert len(result['history']) == 5


def test_forecast_refuses_a_horizon_beyond_the_bound(store):
    '''Past a quarter the projection describes the fitted line, not the market.'''
    for item in build_history(60):
        store[(item.currency, item.date)] = item

    with pytest.raises(HTTPException) as failure:
        _run(quotes.get_forecast_service(days_ahead = quotes.SCENARIO_MAX_DAYS + 1))

    assert QuotesError.INVALID_DATE_RANGE.value in str(failure.value.detail)
