'''
    Unit tests for the official daily and biweekly mineral report services,
    run against a simulated DynamoDB (moto).
'''
import asyncio
from datetime import date

import pytest
from moto import mock_aws

from models.mining_analysis import MiningPriceItem
from services import prices_dyb
from services.mining_analysis import OFFICIAL_MINERALS
from services.official_reports import (
    biweekly_period_bounds,
    get_biweekly_report_service,
    get_daily_report_service,
    normalize_name,
    prev_biweekly_period,
)
from tests.dynamo_helpers import build_quotation_tables, seed_official_catalog


def _run(coro):
    '''Synchronous wrapper around async services for terser test code.'''
    return asyncio.run(coro)


@pytest.fixture(name = 'store')
def _store():
    '''Yields a simulated DynamoDB with the two quotation tables.'''
    with mock_aws():
        yield build_quotation_tables()


def _seed_catalog(resource) -> dict:
    '''Writes the official catalog and returns {normalized_name: mineral_id}.'''
    return seed_official_catalog(resource)


def _add_price(
    resource,
    mineral_id: str,
    day: date,
    low: float,
    high: float = None
):
    prices_dyb.put_price(resource, MiningPriceItem(
        mineral_id = mineral_id,
        date = day,
        price_low = low,
        price_high = high if high is not None else low,
    ))


# --- biweekly bounds & navigation -------------------------------------------

@pytest.mark.parametrize('year, month, half, expected', [
    (2026, 4, 1, (date(2026, 4, 1), date(2026, 4, 15))),
    (2026, 4, 2, (date(2026, 4, 16), date(2026, 4, 30))),
    (2026, 2, 2, (date(2026, 2, 16), date(2026, 2, 28))),
    (2024, 2, 2, (date(2024, 2, 16), date(2024, 2, 29))),
    (2026, 1, 1, (date(2026, 1, 1), date(2026, 1, 15))),
    (2026, 12, 2, (date(2026, 12, 16), date(2026, 12, 31))),
])
def test_biweekly_period_bounds(
    year,
    month,
    half,
    expected
):
    '''Halves are fixed: 1 covers days 1-15 and 2 covers 16 to month end.'''
    assert biweekly_period_bounds(year, month, half) == expected


@pytest.mark.parametrize('cur, expected', [
    ((2026, 4, 2), (2026, 4, 1)),
    ((2026, 4, 1), (2026, 3, 2)),
    ((2026, 1, 1), (2025, 12, 2)),
])
def test_prev_biweekly_period(
    cur,
    expected
):
    '''Walking back one period crosses month and year boundaries.'''
    assert prev_biweekly_period(*cur) == expected


# --- biweekly average -------------------------------------------------------

def test_biweekly_average_partial_days(store):
    '''
    Bismuto has prices on days 1, 8 and 15. The average must divide by 3.
    '''
    ids = _seed_catalog(store)
    bismuto_id = ids[normalize_name('Bismuto')]
    _add_price(store, bismuto_id, date(2026, 4, 1), 13.2)
    _add_price(store, bismuto_id, date(2026, 4, 8), 13.3)
    _add_price(store, bismuto_id, date(2026, 4, 15), 13.3)

    result = _run(get_biweekly_report_service(store, (2026, 4, 1)))
    row = next(r for r in result['rows'] if r['mineral'] == 'Bismuto')

    assert row['sample_size'] == 3
    assert row['avg_price_low'] == pytest.approx((13.2 + 13.3 + 13.3) / 3)
    assert row['period_start'] == date(2026, 4, 1)
    assert row['period_end'] == date(2026, 4, 15)
    assert row['is_fallback'] is False


def test_biweekly_average_falls_back_to_prior_period(store):
    '''
    Estaño has data only in the first half of April; the second-half request
    must reuse that average and flag is_fallback = True.
    '''
    ids = _seed_catalog(store)
    estano_id = ids[normalize_name('Estaño')]
    _add_price(store, estano_id, date(2026, 4, 5), 21.0)
    _add_price(store, estano_id, date(2026, 4, 10), 22.0)

    result = _run(get_biweekly_report_service(store, (2026, 4, 2)))
    row = next(r for r in result['rows'] if r['mineral'] == 'Estaño')

    assert row['is_fallback'] is True
    assert row['avg_price_low'] == pytest.approx(21.5)
    assert row['period_start'] == date(2026, 4, 1)
    assert row['period_end'] == date(2026, 4, 15)


def test_biweekly_average_no_data_anywhere(store):
    '''
    With an empty price table, every row must be zero-valued and flagged.
    '''
    _seed_catalog(store)

    result = _run(get_biweekly_report_service(store, (2026, 4, 1)))

    assert len(result['rows']) == len(OFFICIAL_MINERALS)
    assert all(r['avg_price_low'] == 0.0 for r in result['rows'])
    assert all(r['sample_size'] == 0 for r in result['rows'])
    assert all(r['is_fallback'] is True for r in result['rows'])


def test_biweekly_invalid_half_raises(store):
    '''
    half must be 1 or 2; anything else is an InvalidInputError surfaced as
    HTTPException by the @handle_service_errors decorator.
    '''
    _seed_catalog(store)
    with pytest.raises(Exception):
        _run(get_biweekly_report_service(store, (2026, 4, 3)))


# --- daily report ----------------------------------------------------------

def test_daily_report_returns_latest_on_date(store):
    '''
    When a price exists exactly on ref_date, is_fallback must be False.
    '''
    ids = _seed_catalog(store)
    plata_id = ids[normalize_name('Plata')]
    _add_price(store, plata_id, date(2026, 5, 10), 73.5, 74.5)
    _add_price(store, plata_id, date(2026, 5, 11), 75.0, 76.0)

    result = _run(get_daily_report_service(store, date(2026, 5, 11)))
    row = next(r for r in result['rows'] if r['mineral'] == 'Plata')

    assert row['price_date'] == date(2026, 5, 11)
    assert row['price_low'] == pytest.approx(75.0)
    assert row['price_high'] == pytest.approx(76.0)
    assert row['is_fallback'] is False


def test_daily_report_falls_back_to_prior_date(store):
    '''
    When ref_date has no record, the most recent prior row is returned with
    is_fallback = True.
    '''
    ids = _seed_catalog(store)
    oro_id = ids[normalize_name('Oro')]
    _add_price(store, oro_id, date(2026, 5, 8), 4700)

    result = _run(get_daily_report_service(store, date(2026, 5, 11)))
    row = next(r for r in result['rows'] if r['mineral'] == 'Oro')

    assert row['price_date'] == date(2026, 5, 8)
    assert row['is_fallback'] is True


def test_daily_report_no_data_marks_all_fallback(store):
    '''
    Without any t_mining_prices row, every mineral must still appear and be
    flagged is_fallback = True.
    '''
    _seed_catalog(store)

    result = _run(get_daily_report_service(store, date(2026, 5, 11)))

    assert len(result['rows']) == len(OFFICIAL_MINERALS)
    assert all(r['is_fallback'] for r in result['rows'])
    assert all(r['price_low'] == 0.0 for r in result['rows'])


# --- change_pct on the daily report ---------------------------------------

def test_daily_report_includes_previous_price_and_change_pct(store):
    '''
    The daily report must report the immediately preceding row's price and
    the variation %, computed against the most recent prior day with data.
    '''
    ids = _seed_catalog(store)
    estano_id = ids[normalize_name('Estaño')]
    _add_price(store, estano_id, date(2026, 5, 10), 20.0)
    _add_price(store, estano_id, date(2026, 5, 11), 22.0)

    result = _run(get_daily_report_service(store, date(2026, 5, 11)))
    row = next(r for r in result['rows'] if r['mineral'] == 'Estaño')

    assert row['previous_price_low'] == pytest.approx(20.0)
    assert row['previous_price_date'] == date(2026, 5, 10)
    assert row['change_pct'] == pytest.approx(10.0)


def test_daily_report_change_pct_zero_when_no_history(store):
    '''
    With a single price in storage, change_pct collapses to 0.0 instead of
    raising or returning a misleading negative value.
    '''
    ids = _seed_catalog(store)
    plata_id = ids[normalize_name('Plata')]
    _add_price(store, plata_id, date(2026, 5, 11), 75.0)

    result = _run(get_daily_report_service(store, date(2026, 5, 11)))
    row = next(r for r in result['rows'] if r['mineral'] == 'Plata')

    assert row['previous_price_low'] == 0.0
    assert row['previous_price_date'] is None
    assert row['change_pct'] == 0.0
