'''
    Unit tests for the commercial_summary engine.
'''
import pandas as pd

from services.analytics import build_commercial_summary


def _sales_frame() -> pd.DataFrame:
    '''Small sales frame with two clients, two products and two categories.'''
    return pd.DataFrame([
        {'order_id': 'F1', 'date': '2026-01-05', 'pos_id': 'C1',
         'pos_name': 'Tienda A', 'product_id': 'P1', 'product_name': 'Galleta',
         'category': 'Galletas', 'channel': 'Detalle', 'seller': 'Ana',
         'quantity': 10, 'total_amount': 100.0},
        {'order_id': 'F1', 'date': '2026-01-05', 'pos_id': 'C1',
         'pos_name': 'Tienda A', 'product_id': 'P2', 'product_name': 'Yogurt',
         'category': 'Lácteos', 'channel': 'Detalle', 'seller': 'Ana',
         'quantity': 5, 'total_amount': 75.0},
        {'order_id': 'F2', 'date': '2026-02-10', 'pos_id': 'C2',
         'pos_name': 'Tienda B', 'product_id': 'P1', 'product_name': 'Galleta',
         'category': 'Galletas', 'channel': 'Detalle', 'seller': 'Beto',
         'quantity': 2, 'total_amount': 20.0},
    ])


def test_kpis_are_correct():
    '''Headline KPIs reflect the sample: total, orders, ticket, clients.'''
    summary = build_commercial_summary(_sales_frame())
    kpis = {card.metric_code: card.value for card in summary.kpis}
    assert kpis['TOTAL_SALES'] == 195.0
    assert kpis['SALES_COUNT'] == 2          # F1, F2
    assert kpis['AVERAGE_TICKET'] == 97.5         # 195 / 2
    assert kpis['CLIENT_COUNT'] == 2
    assert kpis['PRODUCT_COUNT'] == 2


def test_best_client_and_top_product_ranked_by_amount():
    '''Rankings use readable names and are ordered by amount.'''
    summary = build_commercial_summary(_sales_frame())
    assert summary.best_clients[0].label == 'Tienda A'   # 175 > 20
    assert summary.top_products[0].label == 'Galleta'    # 120 > 75


def test_distribution_and_trend():
    '''Category shares sum to 100% and the monthly trend has both months.'''
    summary = build_commercial_summary(_sales_frame())
    total_pct = sum(row.percentage for row in summary.by_category)
    assert round(total_pct) == 100
    months = [point.month for point in summary.monthly_trend]
    assert months == ['2026-01', '2026-02']


def test_missing_optional_columns_do_not_break():
    '''A minimal frame without category/seller still produces KPIs.'''
    minimal = pd.DataFrame([
        {'order_id': 'F1', 'pos_id': 'C1', 'product_id': 'P1',
         'quantity': 1, 'total_amount': 10.0}
    ])
    summary = build_commercial_summary(minimal)
    assert summary.kpis[0].value == 10.0
    assert not summary.by_category
