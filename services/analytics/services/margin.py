'''
    Gross-margin engine: turns a sales report into a profitability report.

    Everything here depends on the optional 'unit_cost' column. Most ERP
    exports do not carry it, so every section degrades to empty rather than
    raising: a client without cost data still gets the full commercial summary,
    just without the margin blocks.

    The distinction this module exists to make is the one a commercial manager
    actually cares about: the biggest seller and the biggest earner are rarely
    the same product, the same client or the same salesperson.
'''
from typing import List, Optional

import pandas as pd

from schemas.analytics import (
    KpiCard,
    MarginAlert,
    MarginAlertReason,
    MarginBlock,
    MarginRow,
    MetricCode
)

from services.environment import load_and_validate_env_vars
from services.analytics_utils import (
    setting,
    QUANTITY,
    CATEGORY,
    CLIENT_ID,
    CLIENT_NAME,
    COST,
    AMOUNT,
    PRODUCT_ID,
    PRODUCT_NAME,
    SELLER,
    label_series,
    money,
    order_count,
    ratio
)


_SETTINGS = load_and_validate_env_vars({}, optional_env_vars = {
    'MARGIN_TOP_ROWS': int,
    'MARGIN_THIN_THRESHOLD': float,
})

# Rows kept in each breakdown, so the response stays renderable in a table.
_TOP_ROWS: int = setting(_SETTINGS, 'MARGIN_TOP_ROWS', 15)
# A product is flagged when its realized margin falls below this share of
# revenue. What counts as "too thin" depends on the client's cost structure,
# so it is configurable; 2% is a distribution-business default.
_THIN_MARGIN: float = setting(_SETTINGS, 'MARGIN_THIN_THRESHOLD', 0.02)


def has_cost_data(dataframe: pd.DataFrame) -> bool:
    '''
        Reports whether the frame can support any margin analysis at all.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            bool: True when unit cost, quantity and amount are all usable.
    '''
    required = {COST, QUANTITY, AMOUNT}
    if not required.issubset(dataframe.columns):
        return False
    return bool(pd.to_numeric(dataframe[COST], errors = 'coerce').notna().any())


def _with_margin(dataframe: pd.DataFrame) -> pd.DataFrame:
    '''
        Adds the per-line cost and gross margin columns, keeping only the rows
        where both operands are usable.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.DataFrame: Rows carrying 'line_cost' and 'line_margin'.
    '''
    frame = dataframe.copy()
    frame[COST] = pd.to_numeric(frame[COST], errors = 'coerce')
    frame[QUANTITY] = pd.to_numeric(frame[QUANTITY], errors = 'coerce')
    frame[AMOUNT] = pd.to_numeric(frame[AMOUNT], errors = 'coerce')

    frame = frame[frame[COST].notna() & frame[QUANTITY].notna() & frame[AMOUNT].notna()]
    frame['line_cost'] = frame[COST] * frame[QUANTITY]
    frame['line_margin'] = frame[AMOUNT] - frame['line_cost']
    return frame


def _kpis(frame: pd.DataFrame) -> List[KpiCard]:
    '''
        Builds the headline profitability cards.

        Args:
            frame (pd.DataFrame): Rows already carrying the margin columns.

        Returns:
            List[Dict[str, Any]]: KPI cards ready for the dashboard.
    '''
    revenue = float(frame[AMOUNT].sum())
    cost = float(frame['line_cost'].sum())
    margin = revenue - cost
    orders = order_count(frame)

    return [
        KpiCard(
            metric_code = MetricCode.GROSS_MARGIN.value, value = money(margin), format = 'money'
        ),
        KpiCard(
            metric_code = MetricCode.GROSS_MARGIN_PERCENT.value,
            value = round(ratio(margin, revenue) * 100, 1), format = 'percent'
        ),
        KpiCard(
            metric_code = MetricCode.COST_OF_GOODS.value, value = money(cost), format = 'money'
        ),
        KpiCard(
            metric_code = MetricCode.MARGIN_PER_ORDER.value, value = money(ratio(margin, orders)),
            format = 'money'
        ),
    ]


def _breakdown(frame: pd.DataFrame,
               labels: Optional[pd.Series],
               top: int) -> List[MarginRow]:
    '''
        Aggregates revenue, cost and margin by an arbitrary label series.

        Args:
            frame (pd.DataFrame): Rows carrying the margin columns.
            labels (pd.Series | None): Grouping label per row; None skips the
                section entirely.
            top (int): Maximum rows returned, ordered by margin contribution.

        Returns:
            List[Dict[str, Any]]: One row per group, richest margin first.
    '''
    if labels is None or labels.empty:
        return []

    grouped = frame.groupby(labels.values, dropna = False).agg(
        amount = (AMOUNT, 'sum'),
        cost = ('line_cost', 'sum'),
        margin = ('line_margin', 'sum')
    ).sort_values('margin', ascending = False).head(top)

    return [
        MarginRow(
            label = str(label),
            amount = money(row['amount']),
            cost = money(row['cost']),
            margin = money(row['margin']),
            margin_percentage = round(ratio(row['margin'], row['amount']) * 100, 1)
        )
        for label, row in grouped.iterrows()
    ]


def _thin_margin_products(frame: pd.DataFrame) -> List[MarginAlert]:
    '''
        Lists products whose realized margin is negative or negligible.

        This is the section a manager acts on first: it usually surfaces a
        mispriced item or a promotion that was never switched off.

        Args:
            frame (pd.DataFrame): Rows carrying the margin columns.

        Returns:
            List[Dict[str, Any]]: Loss-making or barely profitable products.
        '''
    labels = label_series(frame, PRODUCT_ID, PRODUCT_NAME)
    if labels is None:
        return []

    grouped = frame.groupby(labels.values, dropna = False).agg(
        amount = (AMOUNT, 'sum'),
        margin = ('line_margin', 'sum')
    )
    grouped = grouped[grouped['amount'] > 0]
    grouped['share'] = grouped['margin'] / grouped['amount']

    flagged = grouped[grouped['share'] < _THIN_MARGIN].sort_values('margin')
    return [
        MarginAlert(
            label = str(label),
            amount = money(row['amount']),
            margin = money(row['margin']),
            margin_percentage = round(row['share'] * 100, 1),
            reason_code = (
                MarginAlertReason.BELOW_COST.value if row['margin'] < 0
                else MarginAlertReason.THIN_MARGIN.value
            )
        )
        for label, row in flagged.head(_TOP_ROWS).iterrows()
    ]


def build_margin(dataframe: pd.DataFrame) -> MarginBlock:
    '''
        Builds the whole profitability block from the normalized sales frame.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by ingest.

        Returns:
            Dict[str, Any]: 'available' (whether the file carried cost data),
                'kpis', 'by_category', 'by_product', 'by_client',
                'by_seller' and 'alerts'. When cost data is absent every
                section is empty and 'available' is False — never an error.
    '''
    if not has_cost_data(dataframe):
        return MarginBlock()

    frame = _with_margin(dataframe)
    if frame.empty:
        return MarginBlock()

    categories = frame[CATEGORY] if CATEGORY in frame.columns else None
    sellers = frame[SELLER] if SELLER in frame.columns else None

    return MarginBlock(
        available = True,
        kpis = _kpis(frame),
        by_category = _breakdown(frame, categories, _TOP_ROWS),
        by_product = _breakdown(
            frame, label_series(frame, PRODUCT_ID, PRODUCT_NAME), _TOP_ROWS
        ),
        by_client = _breakdown(
            frame, label_series(frame, CLIENT_ID, CLIENT_NAME), _TOP_ROWS
        ),
        by_seller = _breakdown(frame, sellers, _TOP_ROWS),
        alerts = _thin_margin_products(frame)
    )
