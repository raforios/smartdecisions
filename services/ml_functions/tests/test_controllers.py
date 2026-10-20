'''
    The forecast endpoint answers its model, built, with the chosen model.

    The controller imports nothing that validates the environment, so the CI
    runs this with no .env.
'''
import asyncio

from controllers.prediction import forecast_series
from schemas.prediction import ForecastModel, ForecastRequest, ForecastResponse
from tests.test_forecast import SEASONAL


def test_the_forecast_answers_its_model_with_the_chosen_projection():
    '''A monthly seasonal series comes back projected by the seasonal model.'''
    answer = asyncio.run(forecast_series(ForecastRequest(
        values = SEASONAL, horizon = 12, season_length = 12, backtest_points = 12)))
    assert isinstance(answer, ForecastResponse)
    assert answer.model is ForecastModel.HOLT_WINTERS
    assert len(answer.forecast) == 12 and answer.tested_points == 7
