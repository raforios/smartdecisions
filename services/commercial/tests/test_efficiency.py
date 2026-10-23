'''
    Unit tests for the efficiency_engine (drop size, sales force, price drift).
'''
import pandas as pd

from services.efficiency import build_efficiency


# order, date, seller, product, units, amount. Four orders across two periods:
# Café sells at 10 early and at 5 later, the discount price-drift must catch.
_ORDER_LINES: list[tuple] = [
    ('F1', '2024-01-05', 'Ana', 'Café', 10.0, 100.0),
    ('F1', '2024-01-05', 'Ana', 'Leche', 6.0, 60.0),
    ('F2', '2024-01-06', 'Ana', 'Café', 6.0, 60.0),
    ('F3', '2024-03-20', 'Beto', 'Café', 8.0, 40.0),
    ('F4', '2024-03-21', 'Beto', 'Café', 4.0, 20.0),
]


def _orders_frame() -> pd.DataFrame:
    '''
        Builds the normalized sales frame from _ORDER_LINES.

        Returns:
            pd.DataFrame: Five lines across four orders and two salespeople.
    '''
    return pd.DataFrame([
        {
            'order_id': order, 'date': pd.Timestamp(date), 'seller': seller,
            'pos_id': 'C1' if seller == 'Ana' else 'C2',
            'product_id': product, 'product_name': product,
            'quantity': units, 'total_amount': amount
        }
        for order, date, seller, product, units, amount in _ORDER_LINES
    ])


def test_drop_size_is_measured_per_order_not_per_line():
    '''
        34 units across 4 orders is a drop size of 8.5, not the 6.8 you would
        get by averaging the five lines.
    '''
    kpis = {
        kpi.metric_code: kpi.value
        for kpi in build_efficiency(_orders_frame()).kpis
    }
    assert kpis['UNITS_PER_ORDER'] == 8.5
    assert kpis['PRODUCTS_PER_ORDER'] == 1.25
    assert kpis['AMOUNT_PER_ORDER'] == 70.0
    assert kpis['ORDER_COUNT'] == 4.0


def test_seller_productivity_is_broken_down_per_person():
    '''Each salesperson carries their own orders, clients and average ticket.'''
    sellers = {row.seller: row for row in build_efficiency(_orders_frame()).sellers}
    assert sellers['Ana'].amount == 220.0
    assert sellers['Ana'].orders == 2
    assert sellers['Ana'].clients == 1
    assert sellers['Ana'].lines_per_order == 1.5
    assert sellers['Beto'].amount == 60.0


def test_price_drift_compares_recent_against_earlier_sales():
    '''
        The realized price is amount / units, so a discount that never touched
        the price list still shows up as a drop.
    '''
    drift = {row.product: row for row in build_efficiency(_orders_frame()).prices}
    assert drift['Café'].previous_price == 10.0
    assert drift['Café'].current_price < 10.0
    assert drift['Café'].change < 0


def test_products_without_a_base_period_are_skipped():
    '''
        Leche only sold in the first half: there is nothing to compare it
        against, so it is omitted rather than reported as a 100% collapse.
    '''
    products = {row.product for row in build_efficiency(_orders_frame()).prices}
    assert 'Leche' not in products


def test_sections_degrade_when_columns_are_missing():
    '''No seller column means no productivity table, not an error.'''
    frame = _orders_frame().drop(columns = ['seller'])
    assert not build_efficiency(frame).sellers
