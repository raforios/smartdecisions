'''
    Unit tests for the official daily and biweekly mineral report services.
'''
import asyncio
from datetime import date

import pytest

from models.mining_analysis import Mineral, MiningPrice
from services.reports_renderer import _format_price
from services.mining_analysis import (
    OFFICIAL_MINERALS,
    ensure_official_minerals,
    get_biweekly_history_service,
    get_biweekly_report_service,
    get_daily_report_service,
    _biweekly_period_bounds,
    _normalize_name,
    _prev_biweekly_period,
)


def _run(coro):
    '''Synchronous wrapper around async services for terser test code.'''
    return asyncio.run(coro)


def _seed_catalog(session) -> dict:
    '''Inserts the official catalog and returns {normalized_name: mineral_id}.'''
    ensure_official_minerals(session)
    return {_normalize_name(m.name): m.id for m in session.query(Mineral).all()}


def _add_price(session, mineral_id: int, day: date, low: float, high: float = None):
    session.add(MiningPrice(
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
def test_biweekly_period_bounds(year, month, half, expected):
    '''Halves are fixed: 1 covers days 1-15 and 2 covers 16 to month end.'''
    assert _biweekly_period_bounds(year, month, half) == expected


@pytest.mark.parametrize('cur, expected', [
    ((2026, 4, 2), (2026, 4, 1)),
    ((2026, 4, 1), (2026, 3, 2)),
    ((2026, 1, 1), (2025, 12, 2)),
])
def test_prev_biweekly_period(cur, expected):
    '''Walking back one period crosses month and year boundaries.'''
    assert _prev_biweekly_period(*cur) == expected


# --- biweekly average -------------------------------------------------------

def test_biweekly_average_partial_days(db_session):
    '''
    Bismuto has prices on days 1, 8 and 15. The average must divide by 3.
    '''
    ids = _seed_catalog(db_session)
    bismuto_id = ids[_normalize_name('Bismuto')]
    _add_price(db_session, bismuto_id, date(2026, 4, 1), 13.2)
    _add_price(db_session, bismuto_id, date(2026, 4, 8), 13.3)
    _add_price(db_session, bismuto_id, date(2026, 4, 15), 13.3)
    db_session.commit()

    result = _run(get_biweekly_report_service(db_session, 2026, 4, 1))
    row = next(r for r in result['rows'] if r['mineral'] == 'Bismuto')

    assert row['sample_size'] == 3
    assert row['avg_price_low'] == pytest.approx((13.2 + 13.3 + 13.3) / 3)
    assert row['period_start'] == date(2026, 4, 1)
    assert row['period_end'] == date(2026, 4, 15)
    assert row['is_fallback'] is False


def test_biweekly_average_falls_back_to_prior_period(db_session):
    '''
    Estaño has data only in the first half of April; the second-half request
    must reuse that average and flag is_fallback = True.
    '''
    ids = _seed_catalog(db_session)
    estano_id = ids[_normalize_name('Estaño')]
    _add_price(db_session, estano_id, date(2026, 4, 5), 21.0)
    _add_price(db_session, estano_id, date(2026, 4, 10), 22.0)
    db_session.commit()

    result = _run(get_biweekly_report_service(db_session, 2026, 4, 2))
    row = next(r for r in result['rows'] if r['mineral'] == 'Estaño')

    assert row['is_fallback'] is True
    assert row['avg_price_low'] == pytest.approx(21.5)
    assert row['period_start'] == date(2026, 4, 1)
    assert row['period_end'] == date(2026, 4, 15)


def test_biweekly_average_no_data_anywhere(db_session):
    '''
    With an empty price table, every row must be zero-valued and flagged.
    '''
    _seed_catalog(db_session)

    result = _run(get_biweekly_report_service(db_session, 2026, 4, 1))

    assert len(result['rows']) == len(OFFICIAL_MINERALS)
    assert all(r['avg_price_low'] == 0.0 for r in result['rows'])
    assert all(r['sample_size'] == 0 for r in result['rows'])
    assert all(r['is_fallback'] is True for r in result['rows'])


def test_biweekly_invalid_half_raises(db_session):
    '''
    half must be 1 or 2; anything else is an InvalidInputError surfaced as
    HTTPException by the @handle_service_errors decorator.
    '''
    _seed_catalog(db_session)
    with pytest.raises(Exception):
        _run(get_biweekly_report_service(db_session, 2026, 4, 3))


# --- daily report ----------------------------------------------------------

def test_daily_report_returns_latest_on_date(db_session):
    '''
    When a price exists exactly on ref_date, is_fallback must be False.
    '''
    ids = _seed_catalog(db_session)
    plata_id = ids[_normalize_name('Plata')]
    _add_price(db_session, plata_id, date(2026, 5, 10), 73.5, 74.5)
    _add_price(db_session, plata_id, date(2026, 5, 11), 75.0, 76.0)
    db_session.commit()

    result = _run(get_daily_report_service(db_session, date(2026, 5, 11)))
    row = next(r for r in result['rows'] if r['mineral'] == 'Plata')

    assert row['price_date'] == date(2026, 5, 11)
    assert row['price_low'] == pytest.approx(75.0)
    assert row['price_high'] == pytest.approx(76.0)
    assert row['is_fallback'] is False


def test_daily_report_falls_back_to_prior_date(db_session):
    '''
    When ref_date has no record, the most recent prior row is returned with
    is_fallback = True.
    '''
    ids = _seed_catalog(db_session)
    oro_id = ids[_normalize_name('Oro')]
    _add_price(db_session, oro_id, date(2026, 5, 8), 4700)
    db_session.commit()

    result = _run(get_daily_report_service(db_session, date(2026, 5, 11)))
    row = next(r for r in result['rows'] if r['mineral'] == 'Oro')

    assert row['price_date'] == date(2026, 5, 8)
    assert row['is_fallback'] is True


def test_daily_report_no_data_marks_all_fallback(db_session):
    '''
    Without any t_mining_prices row, every mineral must still appear and be
    flagged is_fallback = True.
    '''
    _seed_catalog(db_session)

    result = _run(get_daily_report_service(db_session, date(2026, 5, 11)))

    assert len(result['rows']) == len(OFFICIAL_MINERALS)
    assert all(r['is_fallback'] for r in result['rows'])
    assert all(r['price_low'] == 0.0 for r in result['rows'])


# --- catalog seed ----------------------------------------------------------

def test_ensure_official_minerals_is_idempotent(db_session):
    '''
    First invocation seeds all 9; the second adds none.
    '''
    first = ensure_official_minerals(db_session)
    second = ensure_official_minerals(db_session)
    assert first == len(OFFICIAL_MINERALS)
    assert second == 0
    names = {m.name for m in db_session.query(Mineral).all()}
    assert names == {m['name'] for m in OFFICIAL_MINERALS}


# --- change_pct on the daily report ---------------------------------------

def test_daily_report_includes_previous_price_and_change_pct(db_session):
    '''
    The daily report must report the immediately preceding row's price and
    the variation %, computed against the most recent prior day with data.
    '''
    ids = _seed_catalog(db_session)
    estano_id = ids[_normalize_name('Estaño')]
    _add_price(db_session, estano_id, date(2026, 5, 10), 20.0)
    _add_price(db_session, estano_id, date(2026, 5, 11), 22.0)
    db_session.commit()

    result = _run(get_daily_report_service(db_session, date(2026, 5, 11)))
    row = next(r for r in result['rows'] if r['mineral'] == 'Estaño')

    assert row['previous_price_low'] == pytest.approx(20.0)
    assert row['previous_price_date'] == date(2026, 5, 10)
    assert row['change_pct'] == pytest.approx(10.0)


def test_daily_report_change_pct_zero_when_no_history(db_session):
    '''
    With a single price in storage, change_pct collapses to 0.0 instead of
    raising or returning a misleading negative value.
    '''
    ids = _seed_catalog(db_session)
    plata_id = ids[_normalize_name('Plata')]
    _add_price(db_session, plata_id, date(2026, 5, 11), 75.0)
    db_session.commit()

    result = _run(get_daily_report_service(db_session, date(2026, 5, 11)))
    row = next(r for r in result['rows'] if r['mineral'] == 'Plata')

    assert row['previous_price_low'] == 0.0
    assert row['previous_price_date'] is None
    assert row['change_pct'] == 0.0


# --- biweekly history -----------------------------------------------------

def test_biweekly_history_lists_only_periods_with_data(db_session):
    '''
    Only biweekly periods that actually have data should appear in the list.
    Fully-fallback rows are excluded.
    '''
    ids = _seed_catalog(db_session)
    estano_id = ids[_normalize_name('Estaño')]
    _add_price(db_session, estano_id, date(2026, 4, 3), 21.0)
    _add_price(db_session, estano_id, date(2026, 4, 20), 22.0)
    db_session.commit()

    result = _run(get_biweekly_history_service(db_session))
    keys = [(p['year'], p['month'], p['half']) for p in result['periods']]
    assert keys == [(2026, 4, 1), (2026, 4, 2)]
    assert result['period_from'] == date(2026, 4, 3)
    assert result['period_to'] == date(2026, 4, 20)


def test_biweekly_history_empty_when_no_data(db_session):
    '''
    With no price rows at all, the history endpoint returns an empty list
    instead of raising.
    '''
    _seed_catalog(db_session)
    result = _run(get_biweekly_history_service(db_session))
    assert result['periods'] == []


# --- price rendering --------------------------------------------------------

def test_price_rounds_half_up_not_toward_the_even_float():
    '''
        A bulletin cannot round a half down. 12.825 is the real Bismuto average
        for the first half of September; plain float formatting renders 12.82
        because the binary float behind it is 12.8249999….
    '''
    assert _format_price(12.825) == '12.83'
    assert _format_price(0.735) == '0.74'
    assert _format_price(12.8249) == '12.82'


def test_integer_like_quotes_keep_no_decimals():
    '''Antimonio and Wolfram are published without decimals.'''
    assert _format_price(27000.0) == '27,000'
    assert _format_price(116355.0) == '116,355'


def test_missing_price_renders_a_dash():
    '''A mineral with no quote shows an em dash, never a zero.'''
    assert _format_price(None) == '—'
