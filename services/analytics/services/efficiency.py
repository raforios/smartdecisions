'''
    Commercial efficiency engine — the quality of each sale, not its size.

    In mass consumption the total is driven by three levers that a summary of
    revenue alone never exposes:

        * Drop size: how many units and how many distinct products travel in a
          single order. Growing it is cheaper than winning a new client.
        * Seller productivity: sales, clients served, average ticket and lines
          per order side by side, so the team is compared on the same yardstick.
        * Selling price drift: the average price actually charged per product
          against the previous period, which surfaces silent discounting.
'''
from typing import List, Optional

import pandas as pd

from schemas.analytics import (
    EfficiencyBlock,
    KpiCard,
    MetricCode,
    PriceDrift,
    SellerProductivity
)

from services.analytics_utils import (
    QUANTITY,
    CLIENT_ID,
    AMOUNT,
    PRODUCT_ID,
    PRODUCT_NAME,
    SELLER,
    dates,
    label_series,
    money,
    order_count,
    percent_change,
    ratio,
    setting
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

# Price drift is only reported for products with enough movement in both halves
# of the period; a single invoice is an anecdote, not a trend.
_SETTINGS = load_and_validate_env_vars({}, optional_env_vars = {
    'EFFICIENCY_MAX_SELLERS': int,
    'EFFICIENCY_MAX_PRICE_ROWS': int,
    'EFFICIENCY_MIN_UNITS_FOR_PRICE': int,
})
_MAX_SELLERS = setting(_SETTINGS, 'EFFICIENCY_MAX_SELLERS', 50)
_MAX_PRICE_ROWS = setting(_SETTINGS, 'EFFICIENCY_MAX_PRICE_ROWS', 100)
_MIN_UNITS_FOR_PRICE = setting(_SETTINGS, 'EFFICIENCY_MIN_UNITS_FOR_PRICE', 5)


def _drop_size_kpis(dataframe: pd.DataFrame) -> List[KpiCard]:
    '''
        Builds the drop-size cards: units per order, distinct lines per order
        and the average amount per order.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            List[Dict[str, Any]]: KPI cards ready for the UI.
    '''
    orders = order_count(dataframe)
    units = float(dataframe[QUANTITY].sum()) if QUANTITY in dataframe.columns else 0.0
    amount = float(dataframe[AMOUNT].sum()) if AMOUNT in dataframe.columns else 0.0
    # Every row of the normalized frame is one product line of one order.
    lines_per_order = ratio(len(dataframe), orders)

    return [
        KpiCard(metric_code = MetricCode.UNITS_PER_ORDER,
                value = round(ratio(units, orders), 2), format = 'decimal'),
        KpiCard(metric_code = MetricCode.PRODUCTS_PER_ORDER,
                value = round(lines_per_order, 2), format = 'decimal'),
        KpiCard(metric_code = MetricCode.AMOUNT_PER_ORDER,
                value = money(ratio(amount, orders)), format = 'money'),
        KpiCard(metric_code = MetricCode.ORDER_COUNT,
                value = float(orders), format = 'int'),
    ]


def _seller_productivity(dataframe: pd.DataFrame) -> List[SellerProductivity]:
    '''
        Compares sellers on sales, clients served, orders, average ticket and
        lines per order.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            List[Dict[str, Any]]: One row per seller, best sales first. Empty
                when the file has no seller column.
    '''
    if SELLER not in dataframe.columns or AMOUNT not in dataframe.columns:
        return []

    labelled = dataframe.assign(
        _seller = dataframe[SELLER].fillna('').astype(str))
    rows: List[SellerProductivity] = []
    for seller, group in labelled.groupby('_seller'):
        orders = order_count(group)
        amount = float(group[AMOUNT].sum())
        clients = int(group[CLIENT_ID].nunique()) if CLIENT_ID in group.columns else 0
        rows.append(SellerProductivity(
            seller = str(seller),
            amount = money(amount),
            orders = orders,
            clients = clients,
            average_ticket = money(ratio(amount, orders)),
            lines_per_order = round(ratio(len(group), orders), 2),
            amount_per_client = money(ratio(amount, clients)) if clients else 0.0
        ))
    rows.sort(key = lambda row: row.amount, reverse = True)
    return rows[:_MAX_SELLERS]


def _average_price(group: pd.DataFrame) -> Optional[float]:
    '''
        Average price actually charged: amount divided by units, which reflects
        discounts far better than the nominal unit price.

        Args:
            group (pd.DataFrame): Rows of a single product.

        Returns:
            float | None: The realized average price, or None when the group
                does not move enough units to be meaningful.
    '''
    units = float(group[QUANTITY].sum())
    if units < _MIN_UNITS_FOR_PRICE:
        return None
    return ratio(float(group[AMOUNT].sum()), units)


def _price_drift(dataframe: pd.DataFrame) -> List[PriceDrift]:
    '''
        Realized average price per product in the second half of the period
        against the first half.

        Splitting by the median date (instead of by month) keeps the comparison
        available on short datasets, where a month-over-month cut would leave
        most products with no base period.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            List[Dict[str, Any]]: Products whose price moved, largest drop
                first. Empty when quantities, amounts or dates are missing.
    '''
    parsed_dates = dates(dataframe)
    labels = label_series(dataframe, PRODUCT_ID, PRODUCT_NAME)
    if parsed_dates is None or labels is None:
        return []
    if QUANTITY not in dataframe.columns or AMOUNT not in dataframe.columns:
        return []

    valid = parsed_dates.notna()
    scoped = dataframe.loc[valid].assign(
        _label = labels[valid].values, _date = parsed_dates[valid].values)
    if scoped.empty:
        return []

    cut = scoped['_date'].median()
    recent = scoped.loc[scoped['_date'] >= cut]
    earlier = scoped.loc[scoped['_date'] < cut]
    if earlier.empty or recent.empty:
        return []

    recent_prices = {
        label: _average_price(group) for label, group in recent.groupby('_label')
    }
    earlier_prices = {
        label: _average_price(group) for label, group in earlier.groupby('_label')
    }

    rows: List[PriceDrift] = []
    for label, current in recent_prices.items():
        previous = earlier_prices.get(label)
        if current is None or previous is None:
            continue
        variation = percent_change(current, previous)
        if variation is None or variation == 0:
            continue
        rows.append(PriceDrift(
            product = str(label),
            current_price = money(current),
            previous_price = money(previous),
            change = variation
        ))
    rows.sort(key = lambda row: row.change)
    return rows[:_MAX_PRICE_ROWS]


def build_efficiency(dataframe: pd.DataFrame) -> EfficiencyBlock:
    '''
        Builds the commercial efficiency block of the summary.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by ingest.

        Returns:
            Dict[str, Any]: 'kpis' (drop size), 'sellers' (productivity
                table) and 'prices' (realized price drift). Sections the data
                cannot support come back empty rather than raising.
    '''
    message = f'Building efficiency block over {len(dataframe)} rows.'
    logger.info(message)
    return EfficiencyBlock(
        kpis = _drop_size_kpis(dataframe),
        sellers = _seller_productivity(dataframe),
        prices = _price_drift(dataframe)
    )
