'''
    Analytics domain — main module.

    Commercial summary engine — the general sales dashboard.

    One question per module: this one answers "how are we doing?". The rest of
    the questions live in their own engine and the controller imports each one
    from where it is defined. Re-exporting them through here added a layer that
    hid which module actually answers what.

    Turns a normalized sales DataFrame (from ingest) into a clear, business-
    readable snapshot: headline KPIs, best/worst performers, top/bottom products,
    breakdowns by category/channel/region/seller and the monthly trend. Every
    piece is pre-labeled in Spanish and pre-aggregated so the frontend only has
    to render tables and charts — the meaning is decided here.

    Columns used (all produced by ingest normalization; each is optional and
    simply skipped when absent):
        total_amount, quantity, order_id, pos_id, pos_name,
        product_id, product_name, category, channel, region, city,
        seller, date
'''
from typing import List

import pandas as pd

from schemas.analytics import (
    CommercialSummaryBlock,
    DistRow,
    KpiCard,
    MetricCode,
    RankRow,
    TrendPoint
)

from services.analytics_utils import AMOUNT_DECIMALS, RANKING_SIZE
from services.logger_config import custom_logger as logger

_AMOUNT = 'total_amount'
_QUANTITY = 'quantity'
_ORDER = 'order_id'
_CLIENT_ID = 'pos_id'
_CLIENT_NAME = 'pos_name'
_PRODUCT_ID = 'product_id'
_PRODUCT_NAME = 'product_name'


def _money(value: float) -> float:
    '''Rounds a monetary amount to 2 decimals, guarding against NaN.'''
    return round(float(value), AMOUNT_DECIMALS) if pd.notna(value) else 0.0


def _label_series(dataframe: pd.DataFrame, id_col: str, name_col: str) -> pd.Series:
    '''
        Returns a readable label per row: the human name when available, else the
        id. Lets rankings show "Tienda Doña Rosa" instead of "PDV-007".
    '''
    if name_col in dataframe.columns:
        names = dataframe[name_col].fillna('').astype(str).str.strip()
        ids = dataframe[id_col].astype(str) if id_col in dataframe.columns else ''
        return names.where(names != '', ids)
    return dataframe[id_col].astype(str)


def _kpis(dataframe: pd.DataFrame) -> List[KpiCard]:
    '''
        Builds the headline KPI cards: a metric code and its value, so the UI
        renders each one without the backend naming it.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            List[KpiCard]: The headline cards of the commercial summary.
    '''
    total_sales = _money(dataframe[_AMOUNT].sum()) if _AMOUNT in dataframe else 0.0
    sales_count = int(dataframe[_ORDER].nunique()) if _ORDER in dataframe else len(dataframe)
    units = _money(dataframe[_QUANTITY].sum()) if _QUANTITY in dataframe else 0.0
    ticket = _money(total_sales / sales_count) if sales_count else 0.0
    client_count = int(dataframe[_CLIENT_ID].nunique()) if _CLIENT_ID in dataframe else 0
    product_count = int(dataframe[_PRODUCT_ID].nunique()) if _PRODUCT_ID in dataframe else 0

    return [
        KpiCard(metric_code = MetricCode.TOTAL_SALES, value = total_sales, format = 'money'),
        KpiCard(metric_code = MetricCode.SALES_COUNT, value = sales_count, format = 'int'),
        KpiCard(metric_code = MetricCode.AVERAGE_TICKET, value = ticket, format = 'money'),
        KpiCard(metric_code = MetricCode.UNITS_SOLD, value = units, format = 'int'),
        KpiCard(metric_code = MetricCode.CLIENT_COUNT, value = client_count, format = 'int'),
        KpiCard(metric_code = MetricCode.PRODUCT_COUNT, value = product_count, format = 'int'),
    ]


def _ranking(dataframe: pd.DataFrame, label_series: pd.Series, top: int, ascending: bool
             ) -> List[RankRow]:
    '''
        Aggregates total_amount by a label and returns the top (or bottom) N as
        {label, amount} rows. Shared by best/worst client and top/bottom products.

        Rows with zero sales are excluded: a "least sold" list is only useful
        among items that actually sold — listing products with 0 adds no value.
    '''
    if _AMOUNT not in dataframe.columns:
        return []
    grouped = dataframe.assign(_label = label_series.values).groupby('_label')[_AMOUNT].sum()
    grouped = grouped[grouped > 0].sort_values(ascending = ascending).head(top)
    rows = [RankRow(label = str(idx), amount = _money(val)) for idx, val in grouped.items()]
    # Bottom rankings read better ascending → smallest first; keep that order.
    return rows


def _distribution(dataframe: pd.DataFrame, dimension: str) -> List[DistRow]:
    '''
        Sales share by a categorical dimension (category/channel/region/...),
        returned as {label, amount, percentage} sorted by amount desc. Empty when
        the column is absent so the UI can hide that chart.
    '''
    if dimension not in dataframe.columns or _AMOUNT not in dataframe.columns:
        return []
    grouped = (
        dataframe.assign(_dim = dataframe[dimension].fillna('').astype(str))
        .groupby('_dim')[_AMOUNT].sum().sort_values(ascending = False)
    )
    total = grouped.sum()
    if total <= 0:
        return []
    return [
        DistRow(
            label = str(idx),
            amount = _money(val),
            percentage = round(float(val) / float(total) * 100, 1)
        )
        for idx, val in grouped.items()
    ]


def _monthly_trend(dataframe: pd.DataFrame) -> List[TrendPoint]:
    '''
        Monthly sales series as {month: 'YYYY-MM', amount}. Empty when there is no
        parseable date column.
    '''
    if 'date' not in dataframe.columns or _AMOUNT not in dataframe.columns:
        return []
    parsed_dates = pd.to_datetime(dataframe['date'], errors = 'coerce')
    valid = parsed_dates.notna()
    if not valid.any():
        return []
    monthly = (
        dataframe.loc[valid].assign(_month = parsed_dates[valid].dt.strftime('%Y-%m'))
        .groupby('_month')[_AMOUNT].sum().sort_index()
    )
    return [
        TrendPoint(month = str(idx), amount = _money(val))
        for idx, val in monthly.items()
    ]


def build_commercial_summary(dataframe: pd.DataFrame) -> CommercialSummaryBlock:
    '''
        Builds the full commercial summary from a normalized sales DataFrame.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows (one product line
                per row) as produced by the ingest service.

        Returns:
            Dict[str, Any]: KPIs, best/worst client, top/bottom products, the
                distributions by dimension and the monthly trend — all labeled
                and aggregated, ready for tables and charts.
    '''
    message = f'Building commercial summary over {len(dataframe)} rows.'
    logger.info(message)

    client_labels = _label_series(dataframe, _CLIENT_ID, _CLIENT_NAME)
    product_labels = _label_series(dataframe, _PRODUCT_ID, _PRODUCT_NAME)

    return CommercialSummaryBlock(
        kpis = _kpis(dataframe),
        best_clients = _ranking(dataframe, client_labels, top = RANKING_SIZE, ascending = False),
        worst_clients = _ranking(dataframe, client_labels, top = RANKING_SIZE, ascending = True),
        top_products = _ranking(dataframe, product_labels, top = RANKING_SIZE, ascending = False),
        bottom_products = _ranking(dataframe, product_labels, top = RANKING_SIZE, ascending = True),
        by_category = _distribution(dataframe, 'category'),
        by_channel = _distribution(dataframe, 'channel'),
        by_region = _distribution(dataframe, 'region'),
        by_seller = _distribution(dataframe, 'seller'),
        monthly_trend = _monthly_trend(dataframe)
    )
