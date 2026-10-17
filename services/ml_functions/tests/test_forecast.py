'''
    Tests for the shared projection of a series.

    They import only the pure module and the schemas: the CI runs this
    service's tests with no .env.
'''
import pytest
from pydantic import ValidationError

from schemas.prediction import ForecastRequest
from services.forecast import backtest, damped_trend

SMOOTHING = (0.4, 0.1, 0.9)


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


def test_the_error_is_measured_against_the_naive_guess():
    '''On a flat series both are exact; with two points there is nothing to test.'''
    assert backtest([100.0] * 6, SMOOTHING, 3) == (0.0, 0.0)
    assert backtest([100.0, 100.0], SMOOTHING, 3) == (None, None)


def test_the_request_keeps_its_parameters_in_range():
    '''A damping above 1 would make the trend grow instead of fade.'''
    with pytest.raises(ValidationError):
        ForecastRequest(values = [1, 2], horizon = 3, model = 'DAMPED_TREND',
                        smoothing = {'alpha': 0.4, 'beta': 0.1, 'phi': 1.2}, backtest_points = 3)
