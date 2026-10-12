'''
    Tests for the main dashboard: each area's salient figure comes from the
    same engine as the area's own view, the months read at their close, and
    what is held now (stock, receivables) at today's rate.
'''
import asyncio

import pandas as pd

from controllers import analytics, dashboard as controller
from schemas.dashboard import DashboardResponse
from services import currency
from services.dashboard import build_client_figures, build_sales_figures
from services.portfolio import build_portfolio
from tests.demo_files import serve_demo_files


def _ten_per_dollar(monkeypatch) -> None:
    '''
        QUOTES at ten bolivianos per dollar and eleven per USDT, every day.

        Args:
            monkeypatch: Pytest fixture that replaces QUOTES.
    '''
    series = {'USD': [{'date': '2025-01-01', 'rate': 10.0}],
              'USDT': [{'date': '2025-01-01', 'rate': 11.0}]}
    monkeypatch.setattr(currency, '_fetch_rates', lambda code, *args: series[code])


def _two_months() -> pd.DataFrame:
    '''
        September and October sales, and October a year before.

        Returns:
            pd.DataFrame: Sales rows with their month-close factors.
    '''
    sales = pd.DataFrame({
        'date': pd.to_datetime(['2025-10-10', '2026-09-05', '2026-10-03', '2026-10-20']),
        'pos_id': ['A', 'A', 'B', 'C'], 'total_amount': [50.0, 100.0, 120.0, 30.0]})
    return currency.with_month_close_factors(sales, 'Bearer t', '2026-10-25')


def test_the_last_month_is_set_against_the_previous_and_last_year(monkeypatch):
    '''October 150 Bs against September 100 (+50 %) and October 2025 50 (+200 %).'''
    _ten_per_dollar(monkeypatch)

    sales = build_sales_figures(_two_months(), None)

    assert sales.month == '2026-10'
    assert (sales.amount.bob, sales.amount.usd) == (150.0, 15.0)
    assert sales.previous_amount.bob == 100.0
    assert sales.last_year_amount.bob == 50.0
    assert (sales.change_vs_previous, sales.change_vs_last_year) == (50.0, 200.0)
    assert sales.attainment is None


def test_the_client_figures_count_the_month_and_the_largest_fifth(monkeypatch):
    '''Two clients bought in October; the largest fifth (one of three) made half.'''
    _ten_per_dollar(monkeypatch)
    frame = _two_months()

    clients = build_client_figures(frame, build_portfolio(frame))

    assert clients.bought_this_month == 2
    assert clients.top_fifth_share == 50.0


def test_the_dashboard_controller_returns_its_model(monkeypatch):
    '''Every area answers, the held amounts in three currencies and the USDT gap.'''
    _ten_per_dollar(monkeypatch)
    serve_demo_files(monkeypatch, (analytics, controller))
    monkeypatch.setattr(controller, 'get_credit_policy', lambda **_: None)

    response = asyncio.run(controller.dashboard_controller(
        dynamodb_resource = None, dataset_id = 'test-dataset-id', params = {},
        current_user = 'tester@bearsoft.com.bo', request = None))

    assert isinstance(response, DashboardResponse)
    assert response.sales.amount.bob > 0
    assert response.receivables.available is True
    assert response.receivables.balance.usd == round(response.receivables.balance.bob / 10, 2)
    assert response.inventory.available is False
    assert response.fx_gap == 10.0
