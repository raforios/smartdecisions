'''
    Demand forecast engine.

    Projects future monthly sales from a normalized sales DataFrame using
    lightweight methods (no heavy stats libraries, so it fits the Lambda size
    budget): linear trend and moving average. The series can be the whole
    business or split by category, so a mass-consumption distributor can forecast
    each product line separately.

    Everything is returned pre-labeled and split into a historical series and a
    forecast series, ready to plot on one chart.
'''
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from services.logger_config import custom_logger as logger

_MONTO = 'monto_total'
METHOD_LINEAR = 'linear'
METHOD_MOVING_AVERAGE = 'moving_average'
_VALID_METHODS = (METHOD_LINEAR, METHOD_MOVING_AVERAGE)
_METHOD_LABELS = {
    METHOD_LINEAR: 'Tendencia lineal',
    METHOD_MOVING_AVERAGE: 'Media móvil',
}


def _next_months(last_month: str, count: int) -> List[str]:
    '''
        Returns the `count` month labels (YYYY-MM) following `last_month`.
    '''
    period = pd.Period(last_month, freq = 'M')
    return [str(period + offset) for offset in range(1, count + 1)]


def _forecast_values(history: List[float], months_ahead: int, method: str) -> List[float]:
    '''
        Projects `months_ahead` values from the historical series using the
        chosen method. Negative projections are clamped to 0 (sales can't be
        negative).

        Args:
            history (List[float]): Ordered monthly totals.
            months_ahead (int): How many months to project.
            method (str): 'linear' or 'moving_average'.

        Returns:
            List[float]: The projected monthly values.
    '''
    series = np.array(history, dtype = float)
    if method == METHOD_MOVING_AVERAGE:
        window = min(3, len(series))
        baseline = float(series[-window:].mean())
        projected = [baseline] * months_ahead
    else:  # linear trend via least-squares on the month index
        x = np.arange(len(series))
        slope, intercept = np.polyfit(x, series, 1)
        projected = [float(slope * (len(series) + i) + intercept)
                     for i in range(months_ahead)]
    return [round(max(value, 0.0), 2) for value in projected]


def _monthly_totals(dataframe: pd.DataFrame) -> pd.Series:
    '''
        Returns monthly total sales indexed by 'YYYY-MM' (chronological).
    '''
    fechas = pd.to_datetime(dataframe['fecha'], errors = 'coerce')
    valid = fechas.notna()
    frame = dataframe.loc[valid].assign(_mes = fechas[valid].dt.strftime('%Y-%m'))
    return frame.groupby('_mes')[_MONTO].sum().sort_index()


def _series_block(name: str, monthly: pd.Series, months_ahead: int, method: str
                  ) -> Optional[Dict[str, Any]]:
    '''
        Builds one forecast block (historical + projected) for a named series.
        Returns None when there are fewer than two months (nothing to project).
    '''
    if len(monthly) < 2:
        return None
    history = [{'mes': str(idx), 'monto': round(float(val), 2)}
               for idx, val in monthly.items()]
    future_months = _next_months(str(monthly.index[-1]), months_ahead)
    future_values = _forecast_values(list(monthly.values), months_ahead, method)
    forecast = [{'mes': mes, 'monto': val}
                for mes, val in zip(future_months, future_values)]
    return {
        'nombre': name,
        'historico': history,
        'pronostico': forecast,
        'total_pronosticado': round(sum(future_values), 2),
    }


def build_forecast(
    dataframe: pd.DataFrame,
    months_ahead: int = 3,
    method: str = METHOD_LINEAR,
    group_by: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Builds the demand forecast.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            months_ahead (int): Months to project (1..12).
            method (str): 'linear' (trend) or 'moving_average'.
            group_by (Optional[str]): 'categoria' to forecast per category;
                None for a single total series.

        Returns:
            Dict[str, Any]: method, months_ahead and the list of forecast series
                (each with its historical and projected points).
    '''
    method = method if method in _VALID_METHODS else METHOD_LINEAR
    months_ahead = max(1, min(int(months_ahead), 12))
    message = (f'Building forecast method={method} months={months_ahead} '
               f'group_by={group_by}.')
    logger.info(message)

    if 'fecha' not in dataframe.columns or _MONTO not in dataframe.columns:
        return {'method': method, 'method_label': _METHOD_LABELS[method],
                'months_ahead': months_ahead, 'series': []}

    series: List[Dict[str, Any]] = []
    if group_by == 'categoria' and 'categoria' in dataframe.columns:
        # One forecast per category, largest first, capped so the chart stays readable.
        totals = dataframe.groupby(dataframe['categoria'].fillna('Sin especificar'))[_MONTO].sum()
        for categoria in totals.sort_values(ascending = False).head(6).index:
            subset = dataframe[dataframe['categoria'].fillna('Sin especificar') == categoria]
            block = _series_block(str(categoria), _monthly_totals(subset), months_ahead, method)
            if block:
                series.append(block)
    else:
        block = _series_block('Total', _monthly_totals(dataframe), months_ahead, method)
        if block:
            series.append(block)

    return {
        'method': method,
        'method_label': _METHOD_LABELS[method],
        'months_ahead': months_ahead,
        'series': series,
    }
