'''
    Growth engine — turns the sales history into direction, not just volume.

    The commercial summary answers "how much did we sell"; this module answers
    "are we growing, and where is the mix moving". It produces the three things
    a manager asks for right after seeing the totals:

        1. Month-over-month and year-over-year variation.
        2. A seasonality index, so a weak month is read against its own history
           instead of against the annual average.

    The category mix shift moved to `volume.py`: which categories gain weight
    is where the volume comes from, not how fast the total moves.
'''
from typing import List, Optional

import pandas as pd

from schemas.analytics import (
    GrowthBlock,
    KpiCard,
    MetricCode,
    MonthlyChange,
    SeasonIndex
)

from services.environment import load_and_validate_env_vars
from services.analytics_utils import (
    AMOUNT,
    dates,
    money,
    percent_change,
    ratio
)
from services.logger_config import custom_logger as logger

# A seasonality index built on less than a full year compares months that never
# repeat, which reads as signal when it is noise.
_SETTINGS = load_and_validate_env_vars({
    'GROWTH_MIN_MONTHS_FOR_SEASONALITY': int,
})
_MIN_MONTHS_FOR_SEASONALITY = _SETTINGS['GROWTH_MIN_MONTHS_FOR_SEASONALITY']


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
        .assign(_month = parsed_dates[valid].dt.strftime('%Y-%m'))
        .groupby('_month')[AMOUNT].sum().sort_index()
    )


def _monthly_variation(monthly: pd.Series) -> List[MonthlyChange]:
    '''
        Month-by-month series with each month's variation against the previous.

        Args:
            monthly (pd.Series): Amount per 'YYYY-MM'.

        Returns:
            List[Dict[str, Any]]: MonthlyChange(month, amount, change) rows; the first month
                has change None because it has nothing to compare against.
    '''
    rows: List[MonthlyChange] = []
    previous: Optional[float] = None
    for month, amount in monthly.items():
        rows.append(MonthlyChange(
            month = str(month),
            amount = money(amount),
            change = percent_change(amount, previous) if previous is not None else None
        ))
        previous = float(amount)
    return rows


def _seasonality(monthly: pd.Series) -> List[SeasonIndex]:
    '''
        Seasonality index per calendar month: the month's average sales over the
        overall monthly average, as a percentage (100 = an average month).

        Args:
            monthly (pd.Series): Amount per 'YYYY-MM'.

        Returns:
            List[SeasonIndex]: One entry per calendar month, or an empty list
                when there is less than a year of data.
    '''
    if len(monthly) < _MIN_MONTHS_FOR_SEASONALITY:
        return []
    frame = pd.DataFrame({
        'period': pd.to_datetime(monthly.index + '-01'),
        'amount': monthly.values
    })
    overall_average = frame['amount'].mean()
    by_month = frame.assign(_month = frame['period'].dt.month).groupby('_month')['amount'].mean()
    return [
        SeasonIndex(
            month = int(month),
            index_value = round(ratio(average, overall_average) * 100, 1),
            average_amount = money(average)
        )
        for month, average in by_month.sort_index().items()
    ]


def _growth_kpis(monthly: pd.Series) -> List[KpiCard]:
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
        KpiCard(metric_code = MetricCode.LAST_MONTH_SALES.value, value = money(last_amount),
         format = 'money', reference = last_key),
        KpiCard(metric_code = MetricCode.MOM_CHANGE.value,
         value = percent_change(last_amount, previous_amount),
         format = 'percent'),
        # `reference` carries the compared month so the UI can say which year it
        # is contrasting; None means the file has no full year of history.
        KpiCard(metric_code = MetricCode.YOY_CHANGE.value,
         value = percent_change(last_amount, year_ago_amount),
         format = 'percent',
         reference = year_ago_key if year_ago_amount else None),
        KpiCard(metric_code = MetricCode.MONTHLY_AVERAGE.value,
         value = money(monthly.mean()), format = 'money'),
    ]


def build_growth(dataframe: pd.DataFrame) -> GrowthBlock:
    '''
        Builds the growth block of the commercial summary.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by ingest.

        Returns:
            GrowthBlock: 'kpis' (MoM/YoY cards), 'monthly_change' (series
                with per-month change) and 'seasonality' (index per calendar
                month). Every section is empty when the data cannot support it,
                never an error. The category mix moved to the volume-source
                block.
    '''
    parsed_dates = dates(dataframe)
    if parsed_dates is None or AMOUNT not in dataframe.columns:
        message = 'Growth block skipped: the dataset has no usable date or amount column.'
        logger.info(message)
        return GrowthBlock()

    monthly = _monthly_series(dataframe, parsed_dates)
    if monthly.empty:
        return GrowthBlock()

    message = f'Building growth block over {len(monthly)} months.'
    logger.info(message)
    return GrowthBlock(
        kpis = _growth_kpis(monthly),
        monthly_change = _monthly_variation(monthly),
        seasonality = _seasonality(monthly)
    )
