'''
    Growth engine — turns the sales history into direction, not just volume.

    The commercial summary answers "how much did we sell"; this module answers
    "are we growing, and where is the mix moving". It produces the three things
    a manager asks for right after seeing the totals:

        1. Month-over-month and year-over-year variation.
        2. A seasonality index, so a weak month is read against its own history
           instead of against the annual average.
        3. The category mix shift between the last month and the previous one —
           what is gaining and losing weight inside the same total.
'''
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from services.frame_utils import CATEGORIA, MONTO, dates, money, percent_change, ratio
from services.logger_config import custom_logger as logger

_MONTH_NAMES = (
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
)

# A seasonality index built on less than a full year compares months that never
# repeat, which reads as signal when it is noise.
_MIN_MONTHS_FOR_SEASONALITY = 12


def _monthly_series(dataframe: pd.DataFrame, parsed_dates: pd.Series) -> pd.Series:
    '''
        Aggregates sales by calendar month.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            parsed_dates (pd.Series): Coerced datetimes aligned to the frame.

        Returns:
            pd.Series: Amount per 'YYYY-MM', chronologically sorted.
    '''
    valid = parsed_dates.notna()
    return (
        dataframe.loc[valid]
        .assign(_mes = parsed_dates[valid].dt.strftime('%Y-%m'))
        .groupby('_mes')[MONTO].sum().sort_index()
    )


def _monthly_variation(monthly: pd.Series) -> List[Dict[str, Any]]:
    '''
        Month-by-month series with each month's variation against the previous.

        Args:
            monthly (pd.Series): Amount per 'YYYY-MM'.

        Returns:
            List[Dict[str, Any]]: {mes, monto, variacion} rows; the first month
                has variacion None because it has nothing to compare against.
    '''
    rows: List[Dict[str, Any]] = []
    previous: Optional[float] = None
    for month, amount in monthly.items():
        rows.append({
            'mes': str(month),
            'monto': money(amount),
            'variacion': percent_change(amount, previous) if previous is not None else None
        })
        previous = float(amount)
    return rows


def _seasonality(monthly: pd.Series) -> List[Dict[str, Any]]:
    '''
        Seasonality index per calendar month: the month's average sales over the
        overall monthly average, as a percentage (100 = an average month).

        Args:
            monthly (pd.Series): Amount per 'YYYY-MM'.

        Returns:
            List[Dict[str, Any]]: {mes, indice, monto_promedio} in calendar
                order, or an empty list when there is less than a year of data.
    '''
    if len(monthly) < _MIN_MONTHS_FOR_SEASONALITY:
        return []
    frame = pd.DataFrame({
        'periodo': pd.to_datetime(monthly.index + '-01'),
        'monto': monthly.values
    })
    overall_average = frame['monto'].mean()
    by_month = frame.assign(_mes = frame['periodo'].dt.month).groupby('_mes')['monto'].mean()
    return [
        {
            'mes': _MONTH_NAMES[int(month) - 1],
            'indice': round(ratio(average, overall_average) * 100, 1),
            'monto_promedio': money(average)
        }
        for month, average in by_month.sort_index().items()
    ]


def _category_mix(dataframe: pd.DataFrame, parsed_dates: pd.Series,
                  monthly: pd.Series) -> List[Dict[str, Any]]:
    '''
        Category shares of the last month against the previous one, so a shift
        inside a flat total becomes visible.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            parsed_dates (pd.Series): Coerced datetimes aligned to the frame.
            monthly (pd.Series): Amount per 'YYYY-MM'.

        Returns:
            List[Dict[str, Any]]: Per-category current/previous amounts, shares
                and the share change in percentage points, biggest gain first.
                Empty when there is no category column or a single month.
    '''
    if CATEGORIA not in dataframe.columns or len(monthly) < 2:
        return []

    months = list(monthly.index)
    current_key, previous_key = months[-1], months[-2]
    labelled = dataframe.assign(
        _mes = parsed_dates.dt.strftime('%Y-%m'),
        _cat = dataframe[CATEGORIA].fillna('Sin especificar').astype(str)
    )
    current = labelled.loc[labelled['_mes'] == current_key].groupby('_cat')[MONTO].sum()
    previous = labelled.loc[labelled['_mes'] == previous_key].groupby('_cat')[MONTO].sum()
    current_total, previous_total = current.sum(), previous.sum()

    rows = [
        _mix_row(category, (current, previous), (current_total, previous_total))
        for category in sorted(set(current.index) | set(previous.index))
    ]
    return sorted(rows, key = lambda row: row['cambio_participacion'], reverse = True)


def _mix_row(category: str, amounts: Tuple[pd.Series, pd.Series],
             totals: Tuple[float, float]) -> Dict[str, Any]:
    '''
        Builds one category row of the mix comparison.

        Args:
            category (str): Category being described.
            amounts (tuple): (current month series, previous month series).
            totals (tuple): (current month total, previous month total).

        Returns:
            Dict[str, Any]: Amounts, shares and the share change in points.
    '''
    current_amount = float(amounts[0].get(category, 0.0))
    previous_amount = float(amounts[1].get(category, 0.0))
    current_share = round(ratio(current_amount, totals[0]) * 100, 1)
    previous_share = round(ratio(previous_amount, totals[1]) * 100, 1)
    return {
        'label': str(category),
        'monto_actual': money(current_amount),
        'monto_anterior': money(previous_amount),
        'variacion': percent_change(current_amount, previous_amount),
        'participacion_actual': current_share,
        'participacion_anterior': previous_share,
        'cambio_participacion': round(current_share - previous_share, 1)
    }


def _growth_kpis(monthly: pd.Series) -> List[Dict[str, Any]]:
    '''
        Headline growth cards: last month's sales and its variation against the
        previous month and against the same month a year earlier.

        Args:
            monthly (pd.Series): Amount per 'YYYY-MM'.

        Returns:
            List[Dict[str, Any]]: KPI cards; percentage values are None when
                there is no comparable base period.
    '''
    months = list(monthly.index)
    last_key = months[-1]
    last_amount = float(monthly.iloc[-1])
    previous_amount = float(monthly.iloc[-2]) if len(months) >= 2 else None

    # Same calendar month, previous year: only meaningful when that month exists.
    year_ago_key = f'{int(last_key[:4]) - 1}-{last_key[5:7]}'
    year_ago_amount = float(monthly[year_ago_key]) if year_ago_key in monthly.index else None

    return [
        {'label': f'Venta de {last_key}', 'value': money(last_amount), 'format': 'money',
         'hint': 'Último mes con datos en el período'},
        {'label': 'Variación vs mes anterior',
         'value': percent_change(last_amount, previous_amount),
         'format': 'percent',
         'hint': 'Crecimiento mes contra mes (MoM)'},
        {'label': 'Variación vs año anterior',
         'value': percent_change(last_amount, year_ago_amount),
         'format': 'percent',
         'hint': f'Mismo mes de {year_ago_key[:4]} (YoY)' if year_ago_amount
                 else 'Se necesita un año de historial'},
        {'label': 'Promedio mensual', 'value': money(monthly.mean()), 'format': 'money',
         'hint': 'Venta media por mes del período'},
    ]


def build_growth(dataframe: pd.DataFrame) -> Dict[str, Any]:
    '''
        Builds the growth block of the commercial summary.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by ingest.

        Returns:
            Dict[str, Any]: 'kpis' (MoM/YoY cards), 'variacion_mensual' (series
                with per-month change), 'estacionalidad' (index per calendar
                month) and 'mix_categoria' (share shift). Every section is empty
                when the data cannot support it, never an error.
    '''
    parsed_dates = dates(dataframe)
    if parsed_dates is None or MONTO not in dataframe.columns:
        message = 'Growth block skipped: the dataset has no usable date or amount column.'
        logger.info(message)
        return {'kpis': [], 'variacion_mensual': [], 'estacionalidad': [], 'mix_categoria': []}

    monthly = _monthly_series(dataframe, parsed_dates)
    if monthly.empty:
        return {'kpis': [], 'variacion_mensual': [], 'estacionalidad': [], 'mix_categoria': []}

    message = f'Building growth block over {len(monthly)} months.'
    logger.info(message)
    return {
        'kpis': _growth_kpis(monthly),
        'variacion_mensual': _monthly_variation(monthly),
        'estacionalidad': _seasonality(monthly),
        'mix_categoria': _category_mix(dataframe, parsed_dates, monthly)
    }
