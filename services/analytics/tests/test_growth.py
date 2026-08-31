'''
    Unit tests for the growth_engine (MoM / YoY / seasonality / category mix).
'''
import pandas as pd

from services.growth import build_growth


def _monthly_frame(months: int, amount: float = 100.0) -> pd.DataFrame:
    '''
        One sale on the first of each month, all of the same amount.

        Args:
            months (int): How many consecutive months to generate.
            amount (float): Amount of every sale.

        Returns:
            pd.DataFrame: Normalized sales rows.
    '''
    return pd.DataFrame({
        'date': pd.date_range('2023-01-01', periods = months, freq = 'MS'),
        'order_id': [f'F{index}' for index in range(months)],
        'total_amount': [amount] * months,
        'category': ['CAFES'] * months,
    })


def test_month_over_month_variation_is_reported():
    '''A month that doubles the previous one reports +100%.'''
    frame = _monthly_frame(3)
    frame.loc[2, 'total_amount'] = 200.0
    kpis = {kpi.metric_code: kpi.value for kpi in build_growth(frame).kpis}
    assert kpis['MOM_CHANGE'] == 100.0


def test_seasonality_needs_a_full_year():
    '''
        A seasonality index built from less than 12 months would compare a month
        against itself. The section stays empty rather than inventing a pattern.
    '''
    assert not build_growth(_monthly_frame(6)).seasonality
    assert len(build_growth(_monthly_frame(12)).seasonality) == 12


def test_seasonality_index_centers_on_one_hundred():
    '''With identical months every index is exactly the average, i.e. 100.'''
    indices = [row.index_value for row in build_growth(_monthly_frame(12)).seasonality]
    assert all(index == 100.0 for index in indices)


def test_monthly_series_has_no_variation_on_its_first_point():
    '''
        The first month has no predecessor, so its variation is None, never 0 —
        a flat month and an unknown one are different statements.
    '''
    series = build_growth(_monthly_frame(4)).monthly_change
    assert series[0].change is None
    assert series[1].change == 0.0


def test_empty_sections_when_dates_are_missing():
    '''A file without a usable date column yields empty sections, not an error.'''
    frame = _monthly_frame(3).drop(columns = ['date'])
    result = build_growth(frame)
    assert not result.monthly_change
    assert not result.seasonality
