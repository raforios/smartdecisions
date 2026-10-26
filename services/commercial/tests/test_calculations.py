'''
    Tests for the calculations asked of ML_FUNCTIONS.
'''
from typing import Any

import pandas as pd
import pytest
import requests

from schemas.analytics import AnalyticsError
from services import calculations
from services.calculations import ask_ml_functions, rank_tiers
from services.exceptions import ServiceUnavailableError
from services.optimization import build_client_points
from services.segmentation import build_segmentation

TOKEN = 'Bearer test'
CODE = AnalyticsError.CALCULATION_UNAVAILABLE.value


def test_the_tiers_come_from_ml_functions_with_the_caller_token(monkeypatch):
    '''The values, the cuts and the token travel; the tiers come back.'''
    asked: list[dict[str, Any]] = []
    answer = calculations.requests.post

    def _post(
        url: str,
        json: dict[str, Any],
        headers: dict[str, str],
        timeout: float
    ) -> Any:
        asked.append({'url': url, 'headers': headers, **json})
        return answer(url, json = json, headers = headers, timeout = timeout)

    monkeypatch.setattr(calculations.requests, 'post', _post)
    assert rank_tiers([1.0, 3.0, 2.0], [0.5], TOKEN, CODE) == [1, 0, 0]
    assert asked[0]['url'].endswith('/v1/classification/tiers')
    assert asked[0]['headers'] == {'Authorization': TOKEN}
    assert asked[0]['cuts'] == [0.5]


def test_an_unreachable_ml_functions_answers_the_callers_code(monkeypatch):
    '''A network error becomes the code the caller chose, never a 500.'''
    def _down(
        *_: Any,
        **__: Any
    ) -> None:
        raise requests.exceptions.ConnectionError('down')

    monkeypatch.setattr(calculations.requests, 'post', _down)
    with pytest.raises(ServiceUnavailableError) as raised:
        ask_ml_functions('/v1/routing/order', {}, TOKEN, CODE)
    assert raised.value.detail == CODE


def test_a_refused_calculation_answers_the_callers_code(monkeypatch):
    '''A 4xx or 5xx from ML_FUNCTIONS becomes the caller's code too.'''
    class _Refused:  # pylint: disable=too-few-public-methods
        ok = False
        status_code = 422
        text = 'invalid'

    monkeypatch.setattr(calculations.requests, 'post', lambda *_, **__: _Refused())
    with pytest.raises(ServiceUnavailableError) as raised:
        ask_ml_functions('/v1/classification/tiers', {}, TOKEN, CODE)
    assert raised.value.detail == CODE


def test_a_client_is_the_same_tier_on_the_segmentation_and_on_the_map():
    '''
        The segmentation cut the ranking and the map cut quantiles of the
        amount: with ties, the same client could be HIGH on one screen and
        MEDIUM on the other. Both now ask ML_FUNCTIONS the same cut.
    '''
    amounts = [500.0, 500.0, 500.0, 100.0, 90.0, 80.0, 70.0, 60.0, 50.0, 40.0]
    frame = pd.DataFrame([{
        'order_id': f'F{index}', 'pos_id': f'C{index}', 'pos_name': f'C{index}',
        'date': '2026-01-10', 'latitude': -16.5 - index * 0.001, 'longitude': -68.1,
        'total_amount': amount} for index, amount in enumerate(amounts)])
    segmentation = {client.client: client.tier
                    for client in build_segmentation(frame, TOKEN).clients}
    route_map = dict(zip(build_client_points(frame, TOKEN)['client_id'],
                         build_client_points(frame, TOKEN)['segment']))
    assert segmentation == route_map
