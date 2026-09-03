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
from services import price_forecast
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


def test_official_average_is_the_previous_fortnight_not_the_last_quote():
    '''
        The Bolivian official price is the mean of the closed fortnight.

        Reporting the last daily quotation instead is the mistake this exists to
        prevent: a miner settles on the average, and the two numbers differ.
    '''
    window = (date(2026, 8, 16), date(2026, 8, 31))
    observed = {
        date(2026, 8, 17): 10.0,
        date(2026, 8, 18): 20.0,
        date(2026, 8, 19): 30.0,
    }

    result = price_forecast._official_average(window, observed, {}) # pylint: disable=protected-access

    assert result['avg_price_low'] == 20.0
    assert result['sample_size'] == 3
    assert result['observed_days'] == 3
    assert result['projected_days'] == 0


def test_official_average_ignores_weekends_in_the_projection():
    '''
        Quotations are published on working days only.

        Reading the projection on Saturdays and Sundays would average over 15
        days against a real denominator of about 10, quietly dragging every
        projected official price towards the newest values.
    '''
    window = (date(2026, 9, 1), date(2026, 9, 15))
    # A flat projection on every calendar day of the window.
    projected = {
        date(2026, 9, 1) + timedelta(days = offset): 5.0
        for offset in range(15)
    }

    result = price_forecast._official_average(window, {}, projected) # pylint: disable=protected-access

    weekdays = sum(
        1 for offset in range(15)
        if (date(2026, 9, 1) + timedelta(days = offset)).weekday() < 5
    )
    assert result['sample_size'] == weekdays
    assert result['projected_days'] == weekdays


def test_official_average_prefers_what_was_already_published():
    '''
        Days already quoted are facts and must win over the projection, which is
        what makes the fortnight in course worth reporting at all.
    '''
    window = (date(2026, 9, 1), date(2026, 9, 15))
    observed = {date(2026, 9, 1): 100.0, date(2026, 9, 2): 100.0}
    projected = {
        date(2026, 9, 1) + timedelta(days = offset): 0.0
        for offset in range(15)
    }

    result = price_forecast._official_average(window, observed, projected) # pylint: disable=protected-access

    assert result['observed_days'] == 2
    assert result['avg_price_low'] > 0
    assert result['is_complete'] is True


def test_official_average_marks_a_window_the_horizon_does_not_cover():
    '''A mean missing working days is reported as incomplete, not as the price.'''
    window = (date(2026, 9, 1), date(2026, 9, 15))
    projected = {date(2026, 9, 1): 5.0, date(2026, 9, 2): 5.0}

    result = price_forecast._official_average(window, {}, projected) # pylint: disable=protected-access

    assert result['is_complete'] is False
    assert result['sample_size'] == 2


def test_validity_runs_over_the_following_fortnight():
    '''
        The average of 1-15 September is the price in force from 16 to 30
        September. Averaged window and governed window are never the same one.
    '''
    assert price_forecast._validity_of((2026, 9, 1)) == ( # pylint: disable=protected-access
        date(2026, 9, 16), date(2026, 9, 30)
    )
    # Second half of December rules over the first half of January.
    assert price_forecast._validity_of((2026, 12, 2)) == ( # pylint: disable=protected-access
        date(2027, 1, 1), date(2027, 1, 15)
    )


def test_official_average_rounds_half_up_to_two_decimals():
    '''
        The published quotation carries two decimals and a half rounds up.

        Bismuto is the case that proved it: 12.825 rendered as 12.82 through
        float formatting, because the binary float behind it is 12.8249999….
    '''
    window = (date(2026, 8, 17), date(2026, 8, 18))
    observed = {date(2026, 8, 17): 12.82, date(2026, 8, 18): 12.83}

    result = price_forecast._official_average(window, observed, {}) # pylint: disable=protected-access

    assert result['avg_price_low'] == 12.83


def test_official_average_divides_by_that_mineral_own_records():
    '''
        Each mineral averages over the days it was quoted, not over a fixed
        number: Wolfram may have two quotations in a fortnight where Estaño has
        ten, and both averages are correct.
    '''
    window = (date(2026, 8, 16), date(2026, 8, 31))
    thin = {date(2026, 8, 17): 100.0, date(2026, 8, 20): 200.0}

    result = price_forecast._official_average(window, thin, {}) # pylint: disable=protected-access

    assert result['sample_size'] == 2
    assert result['avg_price_low'] == 150.0


def test_official_history_skips_the_period_already_in_force():
    '''
        The fortnight in force travels as `official_current`; repeating it as
        the newest history row would read as two different prices.
    '''
    # Reference in the first half of September: the period in force is the
    # second half of August, so history must start at the first half.
    observed = {
        date(2026, 8, 3): 10.0,   # 1-15 August
        date(2026, 8, 20): 20.0,  # 16-31 August, the one in force
    }

    history = price_forecast._official_history(date(2026, 9, 3), observed, 6) # pylint: disable=protected-access

    assert [entry['period_start'] for entry in history] == [date(2026, 8, 1)]
    assert history[0]['avg_price_low'] == 10.0
