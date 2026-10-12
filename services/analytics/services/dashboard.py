'''
    The main dashboard: the most salient figure of each area, taken from the
    same engines that build each area's view, so the number on entry and the
    number inside are one and the same.
'''
import math

import pandas as pd

from schemas.analytics import MetricCode, PortfolioBlock
from schemas.dashboard import (
    ClientFigures,
    InventoryFigures,
    ReceivableFigures,
    SalesFigures
)
from schemas.objectives import ObjectivesBlockSchema
from schemas.receivables import ReceivablesBlock
from schemas.stock import StockBlock
from services.analytics_utils import AMOUNT, CLIENT_ID, DATE
from services.currency import money_row, money_sums
from services.margin import build_margin

# The largest fifth of the clients: how much of the sales hangs on a few.
_TOP_SHARE = 0.2
_PERCENT = 100.0


def _months(dataframe: pd.DataFrame) -> pd.Series:
    '''
        The month of each row, YYYY-MM.

        Args:
            dataframe (pd.DataFrame): Sales rows with `date`.

        Returns:
            pd.Series: One month per row.
    '''
    return pd.to_datetime(dataframe[DATE]).dt.strftime('%Y-%m')


def _change(
    now: float,
    before: float | None
) -> float | None:
    '''
        The percent change between two amounts in bolivianos.

        Args:
            now (float): The later amount.
            before (float | None): The earlier one.

        Returns:
            float | None: Percent, or None with nothing to compare with.
    '''
    if not before:
        return None
    return round((now - before) / before * _PERCENT, 1)


def _gross_margin_percent(month_rows: pd.DataFrame) -> float | None:
    '''
        The gross margin of the month, when the file carries costs.

        Args:
            month_rows (pd.DataFrame): The month's sales rows.

        Returns:
            float | None: Percent, or None without cost data.
    '''
    margin = build_margin(month_rows)
    card = next((card for card in margin.kpis
                 if card.metric_code == MetricCode.GROSS_MARGIN_PERCENT.value), None)
    return float(card.value) if card and card.value is not None else None


def build_sales_figures(
    dataframe: pd.DataFrame,
    objectives: ObjectivesBlockSchema | None
) -> SalesFigures:
    '''
        The last month with sales against the month before and the same month
        a year earlier, each at its own close.

        Args:
            dataframe (pd.DataFrame): Sales rows with the month-close factors.
            objectives (ObjectivesBlockSchema | None): The latest objectives
                month, when the account loaded objectives.

        Returns:
            SalesFigures: The month and its comparisons.
    '''
    if dataframe.empty:
        return SalesFigures()
    months = _months(dataframe)
    sums = money_sums(dataframe, dataframe[AMOUNT], months, by_month = True)
    month = str(months.max())
    period = pd.Period(month, freq = 'M')
    previous, last_year = str(period - 1), str(period - 12)
    keys = [key for key in (month, previous, last_year) if key in sums.index]
    amounts = {key: money_row(sums.loc[key]) for key in keys}
    bobs = {key: float(sums.loc[key, 'bob']) for key in keys}
    totals = objectives.totals if objectives is not None else None
    return SalesFigures(
        month = month,
        amount = amounts.get(month),
        previous_amount = amounts.get(previous),
        last_year_amount = amounts.get(last_year),
        change_vs_previous = _change(bobs[month], bobs.get(previous)),
        change_vs_last_year = _change(bobs[month], bobs.get(last_year)),
        attainment = round(totals.invoiced_ratio * _PERCENT, 1)
        if totals is not None and totals.target_amount else None,
        gross_margin_percent = _gross_margin_percent(dataframe.loc[months == month])
    )


def build_client_figures(
    dataframe: pd.DataFrame,
    portfolio: PortfolioBlock
) -> ClientFigures:
    '''
        Who bought in the last month, who is at risk, who came and who left,
        and how much of the sales hangs on the largest fifth of the clients.

        Args:
            dataframe (pd.DataFrame): Sales rows.
            portfolio (PortfolioBlock): The portfolio-health view.

        Returns:
            ClientFigures: The client figures.
    '''
    if dataframe.empty or CLIENT_ID not in dataframe.columns:
        return ClientFigures()
    months = _months(dataframe)
    totals = dataframe.groupby(CLIENT_ID)[AMOUNT].sum().sort_values(ascending = False)
    top = math.ceil(len(totals) * _TOP_SHARE)
    last = portfolio.movement[-1] if portfolio.movement else None
    return ClientFigures(
        bought_this_month = int(dataframe.loc[months == months.max(), CLIENT_ID].nunique()),
        at_risk = portfolio.total_at_risk,
        new_clients = last.new_clients if last else 0,
        lost = last.lost if last else 0,
        top_fifth_share = round(float(totals.iloc[:top].sum() / totals.sum()) * _PERCENT, 1)
        if totals.sum() else None
    )


def inventory_figures(stock: StockBlock) -> InventoryFigures:
    '''
        The figures of the stock photo, in bolivianos.

        Args:
            stock (StockBlock): The stock view.

        Returns:
            InventoryFigures: Value, what runs out, coverage and idle capital.
    '''
    if not stock.available:
        return InventoryFigures()
    kpis = stock.kpis
    return InventoryFigures(
        available = True, value = kpis.stock_value, out_of_stock = kpis.out_of_stock,
        at_risk = kpis.at_risk, coverage_days = kpis.average_coverage_days,
        idle_capital = kpis.excess_value
    )


def receivable_figures(receivables: ReceivablesBlock) -> ReceivableFigures:
    '''
        The figures of the credit book, in bolivianos.

        Args:
            receivables (ReceivablesBlock): The receivables view.

        Returns:
            ReceivableFigures: Balance, overdue share, recoverable and days.
    '''
    if not receivables.available:
        return ReceivableFigures()
    kpis = receivables.kpis
    return ReceivableFigures(
        available = True, balance = kpis.receivable_total, overdue_rate = kpis.overdue_rate,
        recoverable = kpis.recoverable_amount, days_to_collect = kpis.days_sales_outstanding
    )
