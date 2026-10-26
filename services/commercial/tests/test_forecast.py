'''
    Unit tests for the forecast engine.

    The projection is asked of ML_FUNCTIONS; here a stand-in answers as it
    does, so what is tested is the series ANALYTICS builds, what it asks for
    and what it does with the answer.
'''
from typing import Any

import pandas as pd
import pytest

from services import calculations, forecast
from services.forecast import build_forecast
from tests.conftest import Answer


@pytest.fixture(name = 'asked')
def _ml_functions(monkeypatch) -> list[dict[str, Any]]:
    '''
        Stands in for ML_FUNCTIONS: projects the line or the moving average the
        way it does, and keeps every request it received.
    '''
    received: list[dict[str, Any]] = []

    def _post(
        url: str,
        json: dict[str, Any],
        **_: Any
    ) -> Answer:
        received.append({'url': url, **json})
        values, horizon = json['values'], json['horizon']
        if json['models'] == ['MOVING_AVERAGE']:
            last = values[-json['window']:]
            return Answer({'forecast': [sum(last) / len(last)] * horizon})
        step = values[-1] - values[-2]
        return Answer({'forecast': [values[-1] + step * ahead for ahead in range(1, horizon + 1)]})

    monkeypatch.setattr(calculations.requests, 'post', _post)
    return received


def _monthly_frame() -> pd.DataFrame:
    '''Four months of clearly increasing total sales (100, 200, 300, 400).'''
    rows = []
    for month, amount in [('2026-01', 100), ('2026-02', 200),
                          ('2026-03', 300), ('2026-04', 400)]:
        rows.append({'date': f'{month}-15', 'total_amount': amount, 'category': 'A'})
    return pd.DataFrame(rows)


def test_linear_forecast_continues_the_trend(asked) -> None:
    '''A +100/month history projects 500, 600, 700 next, asked of ML_FUNCTIONS.'''
    result = build_forecast(_monthly_frame(), 'Bearer t', months_ahead = 3, method = 'linear')
    series = result.series[0]
    assert [point.month for point in series.history] == ['2026-01', '2026-02', '2026-03',
                                                         '2026-04']
    assert [round(point.amount) for point in series.forecast] == [500, 600, 700]
    assert [point.month for point in series.forecast] == ['2026-05', '2026-06', '2026-07']
    assert asked[0]['url'].endswith('/v1/prediction/forecast')
    assert (asked[0]['models'], asked[0]['values']) == (['LINEAR'], [100.0, 200.0, 300.0, 400.0])


def test_moving_average_is_flat(asked) -> None:
    '''Moving average projects the recent mean, flat, with the configured window.'''
    result = build_forecast(_monthly_frame(), 'Bearer t', months_ahead = 2,
                            method = 'moving_average')
    projected = [point.amount for point in result.series[0].forecast]
    assert projected == [300.0, 300.0]
    assert (asked[0]['models'], asked[0]['window']) == (['MOVING_AVERAGE'],
                                                       forecast.MOVING_AVERAGE_MONTHS)


def test_forecast_never_goes_negative(asked) -> None:  # pylint: disable=unused-argument
    '''A steep decline is clamped at 0, not negative.'''
    rows = [{'date': f'2026-0{month}-15', 'total_amount': value}
            for month, value in [(1, 400), (2, 300), (3, 200), (4, 100)]]
    result = build_forecast(pd.DataFrame(rows), 'Bearer t', months_ahead = 4, method = 'linear')
    assert all(point.amount >= 0 for point in result.series[0].forecast)


def test_group_by_category_returns_one_series_each(asked) -> None:
    '''Grouping by category yields one forecast block per category.'''
    frame = _monthly_frame()
    frame = pd.concat([frame, frame.assign(category = 'B')], ignore_index = True)
    result = build_forecast(frame, 'Bearer t', months_ahead = 2, method = 'linear',
                            group_by = 'category')
    assert {series.name for series in result.series} == {'A', 'B'}
    assert len(asked) == 2
