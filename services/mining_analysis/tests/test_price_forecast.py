'''
    Tests for the price projection.

    The projection reaches a mining association, so the cases that matter are
    not the happy ones: a thin series must say it is thin, and a fitted line
    that collapses must never be published as a finding.
'''
from datetime import date, timedelta

import pytest

from schemas.mining_analysis import ForecastConfidence, ForecastMethod
from services.price_forecast import (
    HIGH_CONFIDENCE_DAYS,
    MEDIUM_CONFIDENCE_DAYS,
    MIN_DAYS,
    confidence_for,
    project
)
from services.prices_store import PriceRecord


def _series(values: list) -> list:
    '''
        Builds consecutive daily quotations from a list of prices.

        Args:
            values (list): Prices in chronological order.

        Returns:
            list: PriceRecord instances, one per day.
    '''
    start = date(2026, 1, 1)
    return [
        PriceRecord('1', start + timedelta(days = index), price_low = value)
        for index, value in enumerate(values)
    ]


def test_rising_series_is_projected_upwards():
    '''A quotation that has been climbing is projected to keep climbing.'''
    result = project(_series([10 + index * 0.1 for index in range(100)]), days_ahead = 30)

    assert result.method is ForecastMethod.LINEAR
    assert result.confidence is ForecastConfidence.HIGH
    assert len(result.points) == 30
    assert result.points[-1][1] > result.points[0][1]
    assert result.change_percent > 0


def test_projection_dates_follow_the_last_observation():
    '''The forecast starts the day after the last quotation, without gaps.'''
    prices = _series([10.0] * 40)
    result = project(prices, days_ahead = 5)

    expected = [prices[-1].date + timedelta(days = offset) for offset in range(1, 6)]
    assert [point[0] for point in result.points] == expected


def test_short_history_is_reported_as_insufficient():
    '''
        Below the minimum the engine refuses to project: an invented line over
        four days would look identical to one backed by four months.
    '''
    result = project(_series([10.0] * (MIN_DAYS - 1)), days_ahead = 30)

    assert result.confidence is ForecastConfidence.INSUFFICIENT
    assert not result.points
    assert result.change_percent is None


def test_collapsing_line_falls_back_to_the_moving_average():
    '''
        A steep decline over a short window sends the fitted line to zero inside
        the horizon. Publishing that would read as "this mineral will be worth
        nothing"; the engine falls back and says which method it used.

        This is the Wolfram case: 22 days of falling quotations projected 30
        days ahead returned 0.00 and a -100% change.
    '''
    steep_decline = [61000 - index * 2000 for index in range(22)]

    result = project(_series(steep_decline), days_ahead = 30)

    assert result.method is ForecastMethod.MOVING_AVERAGE
    assert all(price > 0 for _, price in result.points)
    assert result.change_percent > -50


def test_moving_average_carries_no_trend():
    '''The moving average projects a level, never a direction.'''
    result = project(
        _series([10 + index * 0.5 for index in range(40)]),
        days_ahead = 10,
        method = ForecastMethod.MOVING_AVERAGE
    )

    projected = [price for _, price in result.points]
    assert len(set(projected)) == 1


@pytest.mark.parametrize('sample_size, expected', [
    (MIN_DAYS - 1, ForecastConfidence.INSUFFICIENT),
    (MIN_DAYS, ForecastConfidence.LOW),
    (MEDIUM_CONFIDENCE_DAYS, ForecastConfidence.MEDIUM),
    (HIGH_CONFIDENCE_DAYS, ForecastConfidence.HIGH),
])
def test_confidence_follows_the_amount_of_history(sample_size, expected):
    '''The same arithmetic over three weeks and four months is not equal.'''
    assert confidence_for(sample_size) is expected


def test_quotations_without_a_price_are_ignored():
    '''Days with no quotation must not count towards the sample size.'''
    prices = _series([10.0] * 40)
    prices += [PriceRecord('1', date(2026, 3, 1), price_low = None)]

    result = project(prices, days_ahead = 5)

    assert result.points
    # 40 quotations from 2026-01-01 end on 2026-02-09, so the projection starts
    # the next day. The price-less 2026-03-01 row must not move that boundary.
    assert result.points[0][0] == date(2026, 2, 10)
