'''
    Demand forecast engine.

    Projects future monthly sales from a normalized sales DataFrame: linear
    trend or moving average. The projection itself is asked of ML_FUNCTIONS,
    the base service of calculations (Rafael, 17-oct-2026), which keeps the one
    copy of both models; this module builds the monthly series and shapes
    the answer. The series can be the whole
    business or split by category, so a mass-consumption distributor can forecast
    each product line separately.

    Everything is returned pre-labeled and split into a historical series and a
    forecast series, ready to plot on one chart.
'''
from typing import Any

import pandas as pd
import requests

from schemas.analytics import AnalyticsError, ForecastBlock
from services.analytics_utils import AMOUNT_DECIMALS, FORECAST_MONTHS_AHEAD
from services.currency import money_row, money_sums
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.utils import API_URL, REQUEST_TIMEOUT_SECONDS

# How the projection is shaped. The moving-average window, the ceiling on how
# far ahead anybody may ask and how many category lines fit on one chart are
# all judgements about the business being forecast, so an operation can retune
# them without a release.
_SETTINGS = load_and_validate_env_vars({
    'FORECAST_MOVING_AVERAGE_MONTHS': int,
    'FORECAST_MAX_MONTHS_AHEAD': int,
    'FORECAST_MAX_CATEGORIES': int,
})
MOVING_AVERAGE_MONTHS = _SETTINGS['FORECAST_MOVING_AVERAGE_MONTHS']
MAX_MONTHS_AHEAD = _SETTINGS['FORECAST_MAX_MONTHS_AHEAD']
MAX_CATEGORIES = _SETTINGS['FORECAST_MAX_CATEGORIES']

_AMOUNT = 'total_amount'
METHOD_LINEAR = 'linear'
METHOD_MOVING_AVERAGE = 'moving_average'
_VALID_METHODS = (METHOD_LINEAR, METHOD_MOVING_AVERAGE)
# The name each method has in ML_FUNCTIONS.
_ML_MODELS = {METHOD_LINEAR: 'LINEAR', METHOD_MOVING_AVERAGE: 'MOVING_AVERAGE'}
def _next_months(
    last_month: str,
    count: int
) -> list[str]:
    '''
        Returns the `count` month labels (YYYY-MM) following `last_month`.
    '''
    period = pd.Period(last_month, freq = 'M')
    return [str(period + offset) for offset in range(1, count + 1)]


def _forecast_values(
    history: list[float],
    months_ahead: int,
    method: str,
    auth_token: str
) -> list[float]:
    '''
        Projects `months_ahead` values from the historical series with the
        chosen method, asked of ML_FUNCTIONS. Negative projections are clamped
        to 0: sales can't be negative.

        Args:
            history (list[float]): Ordered monthly totals.
            months_ahead (int): How many months to project.
            method (str): 'linear' or 'moving_average'.
            auth_token (str): The caller's Authorization header.

        Returns:
            list[float]: The projected monthly values.

        Raises:
            ServiceUnavailableError: FORECAST_UNAVAILABLE.
    '''
    body = {'values': history, 'horizon': months_ahead, 'models': [_ML_MODELS[method]],
            'window': MOVING_AVERAGE_MONTHS, 'backtest_points': max(1, len(history) - 1)}
    try:
        response = requests.post(f'{API_URL}/v1/prediction/forecast', json = body,
                                 headers = {'Authorization': auth_token},
                                 timeout = REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as error:
        error_msg = f'Network error asking ML_FUNCTIONS for a {method} forecast: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = AnalyticsError.FORECAST_UNAVAILABLE.value) from error
    if not response.ok:
        error_msg = (f'ML_FUNCTIONS refused the {method} forecast: '
                     f'status={response.status_code} body={response.text[:200]}')
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = AnalyticsError.FORECAST_UNAVAILABLE.value)
    projected = response.json().get('forecast') or []
    return [round(max(float(value), 0.0), AMOUNT_DECIMALS) for value in projected]


def _monthly_totals(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Returns monthly total sales indexed by 'YYYY-MM' (chronological):
        `bob` and, with the month-close factors, each month at its closing dollar.
    '''
    fechas = pd.to_datetime(dataframe['date'], errors = 'coerce')
    valid = fechas.notna()
    frame = dataframe.loc[valid]
    return money_sums(frame, frame[_AMOUNT], fechas[valid].dt.strftime('%Y-%m'),
                      by_month = True).sort_index()


def _series_block(
    name: str,
    monthly: pd.DataFrame,
    months_ahead: int,
    method: str,
    auth_token: str
) -> dict[str, Any] | None:
    '''
        Builds one forecast block (historical + projected) for a named series.
        Returns None when there are fewer than two months (nothing to project).

        The history is what was sold, each month at its closing dollar; the
        projection is fitted on the bolivianos and stays in them, so the
        response shows it at today's rate.
    '''
    if len(monthly) < 2:
        return None
    history = [{'month': str(idx), 'amount': money_row(sums)}
               for idx, sums in monthly.iterrows()]
    future_months = _next_months(str(monthly.index[-1]), months_ahead)
    future_values = _forecast_values([float(value) for value in monthly['bob'].values],
                                     months_ahead, method, auth_token)
    forecast = [{'month': month, 'amount': val}
                for month, val in zip(future_months, future_values)]
    return {
        'name': name,
        'history': history,
        'forecast': forecast,
        'total_forecast': round(sum(future_values), AMOUNT_DECIMALS),
    }


def build_forecast(
    dataframe: pd.DataFrame,
    auth_token: str,
    months_ahead: int = FORECAST_MONTHS_AHEAD,
    method: str = METHOD_LINEAR,
    group_by: str | None = None
) -> dict[str, Any]:
    '''
        Builds the demand forecast.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            auth_token (str): The caller's Authorization header, for ML_FUNCTIONS.
            months_ahead (int): Months to project (1..12).
            method (str): 'linear' (trend) or 'moving_average'.
            group_by (str | None): 'category' to forecast per category;
                None for a single total series.

        Returns:
            dict[str, Any]: method, months_ahead and the list of forecast series
                (each with its historical and projected points).
    '''
    method = method if method in _VALID_METHODS else METHOD_LINEAR
    months_ahead = max(1, min(int(months_ahead), MAX_MONTHS_AHEAD))
    message = (f'Building forecast method={method} months={months_ahead} '
               f'group_by={group_by}.')
    logger.info(message)

    if 'date' not in dataframe.columns or _AMOUNT not in dataframe.columns:
        return ForecastBlock(method = method, months_ahead = months_ahead)

    series: list[dict[str, Any]] = []
    if group_by == 'category' and 'category' in dataframe.columns:
        # One forecast per category, largest first, capped so the chart stays readable.
        totals = dataframe.groupby(dataframe['category'].fillna(''))[_AMOUNT].sum()
        for category in totals.sort_values(ascending = False).head(MAX_CATEGORIES).index:
            subset = dataframe[dataframe['category'].fillna('') == category]
            block = _series_block(str(category), _monthly_totals(subset), months_ahead,
                                  method, auth_token)
            if block:
                series.append(block)
    else:
        # No category: the aggregate series. The UI names it.
        block = _series_block('', _monthly_totals(dataframe), months_ahead, method, auth_token)
        if block:
            series.append(block)

    return ForecastBlock(
        method = method,
        months_ahead = months_ahead,
        series = series
    )
