'''
    Unit tests for the commercial_summary engine.
'''
import pandas as pd

from services.commercial_summary import build_commercial_summary


def _sales_frame() -> pd.DataFrame:
    '''Small sales frame with two clients, two products and two categories.'''
    return pd.DataFrame([
        {'id_pedido': 'F1', 'fecha': '2026-01-05', 'id_punto_venta': 'C1',
         'nombre_pdv': 'Tienda A', 'id_producto': 'P1', 'nombre_producto': 'Galleta',
         'categoria': 'Galletas', 'canal': 'Detalle', 'vendedor': 'Ana',
         'cantidad': 10, 'monto_total': 100.0},
        {'id_pedido': 'F1', 'fecha': '2026-01-05', 'id_punto_venta': 'C1',
         'nombre_pdv': 'Tienda A', 'id_producto': 'P2', 'nombre_producto': 'Yogurt',
         'categoria': 'Lácteos', 'canal': 'Detalle', 'vendedor': 'Ana',
         'cantidad': 5, 'monto_total': 75.0},
        {'id_pedido': 'F2', 'fecha': '2026-02-10', 'id_punto_venta': 'C2',
         'nombre_pdv': 'Tienda B', 'id_producto': 'P1', 'nombre_producto': 'Galleta',
         'categoria': 'Galletas', 'canal': 'Detalle', 'vendedor': 'Beto',
         'cantidad': 2, 'monto_total': 20.0},
    ])


def test_kpis_are_correct():
    '''Headline KPIs reflect the sample: total, orders, ticket, clients.'''
    summary = build_commercial_summary(_sales_frame())
    kpis = {card['label']: card['value'] for card in summary['kpis']}
    assert kpis['Venta total'] == 195.0
    assert kpis['Número de ventas'] == 2          # F1, F2
    assert kpis['Ticket promedio'] == 97.5         # 195 / 2
    assert kpis['Clientes'] == 2
    assert kpis['Productos'] == 2


def test_best_client_and_top_product_ranked_by_amount():
    '''Rankings use readable names and are ordered by amount.'''
    summary = build_commercial_summary(_sales_frame())
    assert summary['mejor_cliente'][0]['label'] == 'Tienda A'   # 175 > 20
    assert summary['top_productos'][0]['label'] == 'Galleta'    # 120 > 75


def test_distribution_and_trend():
    '''Category shares sum to 100% and the monthly trend has both months.'''
    summary = build_commercial_summary(_sales_frame())
    total_pct = sum(row['porcentaje'] for row in summary['por_categoria'])
    assert round(total_pct) == 100
    meses = [point['mes'] for point in summary['tendencia_mensual']]
    assert meses == ['2026-01', '2026-02']


def test_missing_optional_columns_do_not_break():
    '''A minimal frame without category/seller still produces KPIs.'''
    minimal = pd.DataFrame([
        {'id_pedido': 'F1', 'id_punto_venta': 'C1', 'id_producto': 'P1',
         'cantidad': 1, 'monto_total': 10.0}
    ])
    summary = build_commercial_summary(minimal)
    assert summary['kpis'][0]['value'] == 10.0
    assert summary['por_categoria'] == []
