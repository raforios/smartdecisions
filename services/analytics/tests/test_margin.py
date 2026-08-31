'''
    Unit tests for the margin_engine (gross profitability).
'''
import pandas as pd

from schemas.analytics import MarginAlertReason
from services.margin import build_margin, has_cost_data


def _sales_frame() -> pd.DataFrame:
    '''
        Two categories with deliberately different economics: CAFES sells less
        but earns more per boliviano than LACTEOS.
    '''
    return pd.DataFrame([
        {'order_id': 'F1', 'pos_id': 'C1', 'pos_name': 'Tienda Uno',
         'product_id': 'P1', 'product_name': 'Café 250g', 'category': 'CAFES',
         'seller': 'Ana', 'quantity': 10.0, 'unit_cost': 6.0, 'total_amount': 100.0},
        {'order_id': 'F2', 'pos_id': 'C2', 'pos_name': 'Tienda Dos',
         'product_id': 'P2', 'product_name': 'Leche 1L', 'category': 'LACTEOS',
         'seller': 'Beto', 'quantity': 10.0, 'unit_cost': 9.0, 'total_amount': 100.0},
    ])


def test_reports_unavailable_without_cost_column():
    '''
        A file with no 'Costo Unitario' must yield an empty, explicitly
        unavailable block — never zeros, which would read as "no profit".
    '''
    frame = _sales_frame().drop(columns = ['unit_cost'])
    result = build_margin(frame)
    assert has_cost_data(frame) is False
    assert result.available is False
    assert not result.kpis
    assert not result.by_category


def test_gross_margin_kpis_are_computed():
    '''Revenue 200, cost 150 -> margin 50 (25%).'''
    result = build_margin(_sales_frame())
    kpis = {kpi.metric_code: kpi.value for kpi in result.kpis}
    assert result.available is True
    assert kpis['GROSS_MARGIN'] == 50.0
    assert kpis['GROSS_MARGIN_PERCENT'] == 25.0
    assert kpis['COST_OF_GOODS'] == 150.0


def test_biggest_seller_is_not_always_the_biggest_earner():
    '''
        Both categories sell exactly 100, but CAFES earns 40 and LACTEOS 10.
        Ranking by margin must put CAFES first — this inversion is the whole
        reason the block exists.
    '''
    result = build_margin(_sales_frame())
    rows = result.by_category
    assert rows[0].label == 'CAFES'
    assert rows[0].margin == 40.0
    assert rows[0].margin_percentage == 40.0
    assert rows[1].label == 'LACTEOS'
    assert rows[1].margin == 10.0


def test_products_sold_below_cost_are_flagged():
    '''A product whose cost exceeds its price is reported with its reason.'''
    frame = _sales_frame()
    frame.loc[1, 'unit_cost'] = 12.0  # cost 120 against revenue 100
    alerts = build_margin(frame).alerts
    assert len(alerts) == 1
    assert alerts[0].label == 'Leche 1L'
    assert alerts[0].margin == -20.0
    assert alerts[0].reason_code == MarginAlertReason.BELOW_COST.value


def test_margin_is_broken_down_by_seller():
    '''Each salesperson carries the margin of what they actually sold.'''
    margin = build_margin(_sales_frame())
    by_seller = {row.label: row.margin for row in margin.by_seller}
    assert by_seller == {'Ana': 40.0, 'Beto': 10.0}
