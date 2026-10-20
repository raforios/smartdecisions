'''
    Tests for the shared projection of a series.

    They import only the pure module and the schemas: the CI runs this
    service's tests with no .env.
'''
import pytest
from pydantic import ValidationError

from schemas.prediction import ForecastRequest
from services.forecast import (
    DAMPED_TREND,
    HOLT_WINTERS,
    NAIVE,
    backtest,
    candidates,
    choose_and_project,
    damped_trend,
    fit,
    holt_winters,
    minimum_history
)

SMOOTHING = (0.4, 0.1, 0.9)

# Monthly net sales with a December peak and a January drop, each month of
# the second year 15.39 % above the same month of the first: the shape of the
# FINANCE test company, whose projection did worse than the naive guess
# while the model ignored the seasons (19-oct-2026).
SEASONAL = [548467.2, 542982.52, 592237.08, 605522.72, 625294.9, 645454.41, 640392.01,
            654557.48, 655853.64, 683635.6, 711989.88, 802103.62, 632873.36, 626544.62,
            683379.18, 698709.42, 721524.42, 744786.37, 738944.91, 755290.36, 756785.99]


def test_a_flat_series_stays_flat():
    '''Nothing moves, nothing is projected to move.'''
    assert damped_trend([100.0] * 6, 3, SMOOTHING) == pytest.approx([100, 100, 100])


def test_a_rising_series_keeps_rising_ever_less():
    '''The trend continues and fades step by step.'''
    projected = damped_trend([100.0, 110, 120, 130, 140, 150], 3, SMOOTHING)
    steps = [projected[1] - projected[0], projected[2] - projected[1]]
    assert all(step > 0 for step in steps) and steps[0] > steps[1]


def test_without_damping_the_line_goes_on():
    '''With phi = 1 and full weight on the last value, a straight line stays straight.'''
    assert damped_trend([1.0, 2, 3, 4], 2, (1.0, 1.0, 1.0)) == pytest.approx([5, 6])


def test_a_repeated_season_is_projected_again():
    '''Two identical seasons: the next one repeats them.'''
    season = [10.0, 20, 30, 20]
    projected = holt_winters(season * 3, 4, (0.3, 0.1, 0.3, 0.9), 4)
    assert projected == pytest.approx(season, abs = 1e-6)


def test_the_fit_follows_a_straight_line():
    '''On a clean line the fitted trend projects the line.'''
    line = [float(value) for value in range(10, 130, 10)]
    projected = damped_trend(line, 1, fit(line, DAMPED_TREND, None))
    assert projected[0] == pytest.approx(130, rel = 0.02)


def test_each_model_needs_enough_history():
    '''A season needs one whole season plus two points to be fitted.'''
    assert minimum_history(NAIVE, None) == 1
    assert minimum_history(DAMPED_TREND, None) == 3
    assert minimum_history(HOLT_WINTERS, 12) == 14


def test_every_model_is_tested_on_the_same_points():
    '''With 21 months and seasons of 12, the comparison starts where all can predict.'''
    models, start = candidates(SEASONAL, 12, 12)
    assert models == [NAIVE, DAMPED_TREND, HOLT_WINTERS]
    assert start == 14
    assert candidates(SEASONAL, None, 12) == ([NAIVE, DAMPED_TREND], 9)


def test_the_naive_error_is_measured_out_of_sample():
    '''On a flat series the naive guess is exact; with one point nothing is tested.'''
    assert backtest([100.0] * 6, NAIVE, None, 3) == 0.0
    assert backtest([100.0], NAIVE, None, 1) is None


def test_a_seasonal_series_is_projected_with_its_seasons():
    '''The case of 19-oct: the seasonal model beats the naive guess and sees December.'''
    projection = choose_and_project(SEASONAL, 12, 12, 12)
    assert projection.model == HOLT_WINTERS
    assert projection.error_percent < projection.naive_error_percent
    assert projection.tested_points == 7
    october, november, december, january = projection.forecast[:4]
    assert december > november > october and january < december


def test_a_model_that_does_not_beat_the_naive_guess_is_not_used():
    '''Without seasons the trend loses to the naive guess here, so the naive one projects.'''
    projection = choose_and_project(SEASONAL, 3, None, 12)
    assert projection.model == NAIVE
    assert projection.forecast == [SEASONAL[-1]] * 3
    assert projection.error_percent == projection.naive_error_percent


def test_too_short_a_series_is_projected_naively():
    '''Two points fit no model: the projection is the last value, tested on the second.'''
    projection = choose_and_project([100.0, 120.0], 2, 12, 3)
    assert (projection.model, projection.forecast) == (NAIVE, [120.0, 120.0])
    assert projection.error_percent == pytest.approx(100 * 20 / 120)
    assert projection.tested_points == 1
    assert choose_and_project([100.0], 1, None, 3).tested_points == 0


def test_the_request_keeps_the_season_in_range():
    '''A season of one point is no season.'''
    with pytest.raises(ValidationError):
        ForecastRequest(values = [1, 2], horizon = 3, season_length = 1, backtest_points = 3)


def test_an_older_caller_is_still_understood():
    '''The fields a caller sent before 19-oct are ignored, not rejected.'''
    request = ForecastRequest(values = [1, 2], horizon = 3, backtest_points = 3,
                              model = 'DAMPED_TREND',
                              smoothing = {'alpha': 0.4, 'beta': 0.1, 'phi': 0.9})
    assert request.season_length is None
