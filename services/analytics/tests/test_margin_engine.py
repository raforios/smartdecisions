'''
    Unit tests for the margin_engine (gross profitability).
'''
import pandas as pd

from services.margin_engine import build_margin, has_cost_data


def _sales_frame() -> pd.DataFrame:
    '''
        Two categories with deliberately different economics: CAFES sells less
        but earns more per boliviano than LACTEOS.
    '''
    return pd.DataFrame([
        {'id_pedido': 'F1', 'id_punto_venta': 'C1', 'nombre_pdv': 'Tienda Uno',
         'id_producto': 'P1', 'nombre_producto': 'Café 250g', 'categoria': 'CAFES',
         'vendedor': 'Ana', 'cantidad': 10.0, 'costo_unitario': 6.0, 'monto_total': 100.0},
        {'id_pedido': 'F2', 'id_punto_venta': 'C2', 'nombre_pdv': 'Tienda Dos',
         'id_producto': 'P2', 'nombre_producto': 'Leche 1L', 'categoria': 'LACTEOS',
         'vendedor': 'Beto', 'cantidad': 10.0, 'costo_unitario': 9.0, 'monto_total': 100.0},
    ])


def test_reports_unavailable_without_cost_column():
    '''
        A file with no 'Costo Unitario' must yield an empty, explicitly
        unavailable block — never zeros, which would read as "no profit".
    '''
    frame = _sales_frame().drop(columns = ['costo_unitario'])
    result = build_margin(frame)
    assert has_cost_data(frame) is False
    assert result['disponible'] is False
    assert not result['kpis']
    assert not result['por_categoria']


def test_gross_margin_kpis_are_computed():
    '''Revenue 200, cost 150 -> margin 50 (25%).'''
    result = build_margin(_sales_frame())
    kpis = {kpi['label']: kpi['value'] for kpi in result['kpis']}
    assert result['disponible'] is True
    assert kpis['Margen bruto'] == 50.0
    assert kpis['Margen bruto %'] == 25.0
    assert kpis['Costo de la mercadería'] == 150.0


def test_biggest_seller_is_not_always_the_biggest_earner():
    '''
        Both categories sell exactly 100, but CAFES earns 40 and LACTEOS 10.
        Ranking by margin must put CAFES first — this inversion is the whole
        reason the block exists.
    '''
    result = build_margin(_sales_frame())
    rows = result['por_categoria']
    assert rows[0]['label'] == 'CAFES'
    assert rows[0]['margen'] == 40.0
    assert rows[0]['margen_porcentaje'] == 40.0
    assert rows[1]['label'] == 'LACTEOS'
    assert rows[1]['margen'] == 10.0


def test_products_sold_below_cost_are_flagged():
    '''A product whose cost exceeds its price is reported with its reason.'''
    frame = _sales_frame()
    frame.loc[1, 'costo_unitario'] = 12.0  # cost 120 against revenue 100
    alerts = build_margin(frame)['alertas']
    assert len(alerts) == 1
    assert alerts[0]['label'] == 'Leche 1L'
    assert alerts[0]['margen'] == -20.0
    assert alerts[0]['motivo'] == 'Se vende por debajo del costo'


def test_margin_is_broken_down_by_seller():
    '''Each salesperson carries the margin of what they actually sold.'''
    margin = build_margin(_sales_frame())
    by_seller = {row['label']: row['margen'] for row in margin['por_vendedor']}
    assert by_seller == {'Ana': 40.0, 'Beto': 10.0}
