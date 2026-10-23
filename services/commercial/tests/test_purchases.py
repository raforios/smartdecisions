'''
    Tests for the purchases view (plan phase 6, rules 1, 2 and 7): each
    purchase at the rate of its own day, the last against the previous ones,
    and the same purchase at today's rate.
'''
import asyncio

import pandas as pd

from controllers import purchases as controller
from schemas.analytics import ReferenceRates
from schemas.purchases import PurchasesResponse
from services import currency
from services.purchases import build_purchase_rows, latest_prices, with_costs_in_bolivianos

# The dollar was 10 in August and 12.5 in September; USDT 11 all along.
SERIES = {
    'USD': [{'date': '2026-08-01', 'rate': 10.0}, {'date': '2026-09-01', 'rate': 12.5}],
    'USDT': [{'date': '2026-08-01', 'rate': 11.0}],
}
TODAY = ReferenceRates(usd = 16.0, usdt = 11.0)


def _purchases() -> pd.DataFrame:
    '''
        Film bought twice in dollars; trays once in bolivianos.

        Returns:
            pd.DataFrame: Normalized purchase rows.
    '''
    return pd.DataFrame({
        'purchase_date': ['2026-08-10', '2026-09-10', '2026-09-12'],
        'supplier': ['Plastiforte', 'Plastiforte', 'Bandejas SRL'],
        'product_id': ['FILM', 'FILM', 'TRAY'], 'product_name': ['Film', 'Film', 'Bandeja'],
        'quantity': [100.0, 50.0, 20.0], 'unit_cost': [2.0, 2.0, 30.0],
        'currency': ['USD', 'USD', 'BOB'],
    })


def test_a_cost_in_dollars_becomes_bolivianos_at_its_own_day(monkeypatch):
    '''2 USD were 20 Bs in August and 25 Bs in September: +25 % without a price change.'''
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: SERIES[code])

    rows = build_purchase_rows(with_costs_in_bolivianos(_purchases(), 'Bearer t', TODAY),
                               {'FILM': 40.0}, TODAY)
    film = next(row for row in rows if row.product_id == 'FILM')

    assert (film.last_cost.bob, film.last_cost.usd) == (25.0, 2.0)
    assert film.previous_cost.bob == 20.0
    assert film.change_vs_previous == 25.0


def test_the_same_purchase_today_and_the_margin_it_leaves(monkeypatch):
    '''Today the same 2 USD are 32 Bs: at a 40 Bs price the margin falls from 37.5 % to 20 %.'''
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: SERIES[code])

    rows = build_purchase_rows(with_costs_in_bolivianos(_purchases(), 'Bearer t', TODAY),
                               {'FILM': 40.0}, TODAY)
    film = next(row for row in rows if row.product_id == 'FILM')
    tray = next(row for row in rows if row.product_id == 'TRAY')

    assert film.cost_today.bob == 32.0
    assert film.difference_today.bob == 7.0
    assert (film.margin_at_last_cost, film.margin_at_cost_today) == (37.5, 20.0)
    # Paid in bolivianos, the cost does not move with the rate.
    assert tray.difference_today.bob == 0.0
    assert rows[0].product_id == 'FILM'


def test_the_price_of_the_latest_stock_photo_wins_over_the_last_sale():
    '''The stock carries the price list in force; a sale is only a fallback.'''
    sales = pd.DataFrame({'date': pd.to_datetime(['2026-09-01', '2026-09-20']),
                          'product_id': ['FILM', 'TRAY'], 'unit_price': [38.0, 45.0]})
    stock = pd.DataFrame({'snapshot_date': ['2026-08-31', '2026-09-30'],
                          'product_id': ['FILM', 'FILM'], 'unit_price': [39.0, 41.0]})

    assert latest_prices(sales, stock) == {'FILM': 41.0, 'TRAY': 45.0}


def test_the_controller_says_so_without_purchases(monkeypatch):
    '''A dataset without purchases answers NO_PURCHASES, not an empty view.'''
    monkeypatch.setattr(controller, 'get_dataset_metadata',
                        lambda **_: {'file_s3_key': 'sales.csv'})

    response = asyncio.run(controller.purchases_controller(
        dynamodb_resource = None, dataset_id = 'test-dataset-id', params = {},
        current_user = 'tester@bearsoft.com.bo', request = None))

    assert isinstance(response, PurchasesResponse)
    assert response.reason_code == 'NO_PURCHASES'


def test_the_controller_returns_its_model(monkeypatch):
    '''With purchases: the month at its close and one row per product.'''
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: SERIES[code])
    frames = {'purchases.csv': _purchases(),
              'sales.csv': pd.DataFrame({'date': pd.to_datetime(['2026-09-01']),
                                         'product_id': ['FILM'], 'unit_price': [40.0]})}
    monkeypatch.setattr(controller, 'get_dataset_metadata',
                        lambda **_: {'file_s3_key': 'sales.csv',
                                     'purchases_s3_key': 'purchases.csv'})
    monkeypatch.setattr(controller, 'load_dataframe', lambda key, _token: frames[key])

    response = asyncio.run(controller.purchases_controller(
        dynamodb_resource = None, dataset_id = 'test-dataset-id', params = {},
        current_user = 'tester@bearsoft.com.bo', request = None))

    assert response.month == '2026-09'
    assert response.month_amount.bob == 1850.0
    assert (response.cost_up, response.cost_down) == (1, 0)
    assert len(response.products) == 2
