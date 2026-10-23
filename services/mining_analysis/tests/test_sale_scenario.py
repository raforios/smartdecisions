'''
    "Vender hoy o esperar", priced with the dollar QUOTES projects.
'''
import pytest

from schemas.market import SaleScenarioRequest
from services.sale_scenario import sale_scenario

FORECAST = {'last_rate': 10.0, 'final_rate': 11.0, 'confidence': 'MEDIUM',
            'change_percent': 10.0}


def test_waiting_weighs_the_dollar_and_the_mineral() -> None:
    '''10 units at 100 USD: 10.000 Bs today; +5 % mineral at 11 Bs, 11.550 Bs later.'''
    result = sale_scenario(SaleScenarioRequest(quantity = 10, unit_price_usd = 100,
                                               days_ahead = 30,
                                               mineral_change_percent = 5), FORECAST)
    assert result.today.amount_bob == pytest.approx(10000.0)
    assert result.model_dump()['projected']['amount_bob'] == pytest.approx(11550.0)
    assert result.difference_bob == pytest.approx(1550.0)
    assert result.difference_percent == pytest.approx(15.5)
    assert (result.rate_confidence, result.rate_change_percent) == ('MEDIUM', 10.0)


def test_without_a_projection_only_today_is_priced() -> None:
    '''A history too short to project leaves the wait unpriced, not invented.'''
    result = sale_scenario(SaleScenarioRequest(quantity = 1, unit_price_usd = 50),
                           {**FORECAST, 'final_rate': None, 'confidence': 'INSUFFICIENT'})
    assert result.projected is None and result.difference_bob is None
    assert result.today.amount_bob == pytest.approx(500.0)
