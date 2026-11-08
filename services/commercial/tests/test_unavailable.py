'''
    Parts of an analysis the business does use, with too little data yet:
    each comes back empty with its reason instead of silently empty. The data
    is a shop's first month, like the pharmacy's on 8-nov-2026.
'''
import pandas as pd

from schemas.modules import AnalysisUnavailable
from services.efficiency import build_efficiency
from services.forecast import build_forecast
from services.fx_effect import build_fx_effect
from services.growth import build_growth
from services.objectives import build_objectives, resolve_policy
from services.portfolio import build_portfolio
from services.volume import build_volume_source


def _first_month() -> pd.DataFrame:
    '''Three counter sales in one month, with no category.'''
    return pd.DataFrame({
        'date': pd.to_datetime(['2026-11-02', '2026-11-05', '2026-11-08']),
        'order_id': ['A-1', 'A-2', 'A-3'], 'pos_id': ['Mostrador'] * 3,
        'pos_name': ['Mostrador'] * 3, 'product_id': ['P1', 'P2', 'P1'],
        'product_name': ['Leche', 'Pan', 'Leche'], 'quantity': [2.0, 1.0, 3.0],
        'unit_price': [10.0, 5.0, 10.0], 'total_amount': [20.0, 5.0, 30.0]
    })


def test_one_month_says_why_forecast_seasonality_and_churn_are_empty():
    '''Too few months to project, to find a season or to compare one month with another.'''
    sales = _first_month()
    forecast = build_forecast(sales, 'Bearer t')
    assert not forecast.series and forecast.reason_code is AnalysisUnavailable.INSUFFICIENT_HISTORY
    growth = build_growth(sales)
    assert growth.seasonality_reason is AnalysisUnavailable.INSUFFICIENT_HISTORY
    assert build_portfolio(sales).churn_reason is AnalysisUnavailable.SINGLE_MONTH


def test_missing_categories_and_prices_and_objectives_are_named():
    '''No category column, no price history, no objectives loaded: each says so.'''
    sales = _first_month()
    assert build_volume_source(sales).category_mix_reason is AnalysisUnavailable.NO_CATEGORIES
    assert build_efficiency(sales).prices_reason is AnalysisUnavailable.NO_PRICE_HISTORY
    assert build_objectives(sales, None, None, None).reason_code is (
        AnalysisUnavailable.NO_OBJECTIVES)


def test_one_month_has_no_growth_to_measure_in_dollars():
    '''The exchange-rate effect compares months; with one there is nothing to compare.'''
    sales = _first_month()
    block = build_fx_effect(sales, pd.Series([6.96] * len(sales)), 6.96, resolve_policy(None))
    assert block.growth_bob_pct is None and block.growth_reason is AnalysisUnavailable.SINGLE_MONTH
