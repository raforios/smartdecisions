'''
    Stock engine — what is in the warehouse, and what that implies.

    A snapshot of balances is an ERP screen; this module is the analysis of it.
    It answers the questions a balance alone cannot: how many days the stock
    lasts at the demand actually observed, which products are about to run out
    and on what date, how much capital is immobilized in stock nobody buys, and
    how all of that lines up with the ABC of the catalogue.

    Two lines this module does not cross, on purpose:

      * `available = on_hand - committed` REPORTS a commitment the client's ERP
        already made. Nothing here reserves, holds or promises anything: owning
        that truth would mean owning concurrency, idempotency and the blame when
        the ERP disagrees — a fight this product loses against the ERP.
      * The demand is read from the sales history, not from the forecast module.
        Coverage in days is a measurement, and mixing a projection into it would
        make a stockout date look measured when it is inferred.
'''
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd

from schemas.stock import (
    StockBlock,
    StockKpis,
    StockRow,
    StockStatus,
    StockUnavailable
)
from services.analytics_utils import (
    AMOUNT,
    DATE,
    PRODUCT_ID,
    PRODUCT_NAME,
    QUANTITY,
    money,
    ratio,
    unavailable_block
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

# Business thresholds. Days of coverage are a policy of the operation —a
# distributor with weekly deliveries reads 10 days very differently from one
# importing by sea— so they are configured, never literals.
_SETTINGS = load_and_validate_env_vars({
    'STOCK_DEMAND_WINDOW_DAYS': int,
    'STOCK_CRITICAL_COVERAGE_DAYS': int,
    'STOCK_LOW_COVERAGE_DAYS': int,
    'STOCK_EXCESS_COVERAGE_DAYS': int,
    'STOCK_TOP_ROWS': int,
    'STOCK_MAX_PRODUCT_ROWS': int,
})
_DEMAND_WINDOW = _SETTINGS['STOCK_DEMAND_WINDOW_DAYS']
_CRITICAL_DAYS = _SETTINGS['STOCK_CRITICAL_COVERAGE_DAYS']
_LOW_DAYS = _SETTINGS['STOCK_LOW_COVERAGE_DAYS']
_EXCESS_DAYS = _SETTINGS['STOCK_EXCESS_COVERAGE_DAYS']
_TOP_ROWS = _SETTINGS['STOCK_TOP_ROWS']
_MAX_PRODUCT_ROWS = _SETTINGS['STOCK_MAX_PRODUCT_ROWS']

# Contract columns of the stock snapshot.
SNAPSHOT_DATE = 'snapshot_date'
ON_HAND = 'on_hand'
COMMITTED = 'committed'
IN_TRANSIT = 'in_transit'
UNIT_COST = 'unit_cost'

_COVERAGE_DECIMALS = 1

# ABC cut points of the catalogue: the first 80% of the sales is A, the next
# 15% is B and the tail is C. They match the volume block's so a product is not
# an A on one screen and a B on another.
_ABC_A_LIMIT = 0.80
_ABC_B_LIMIT = 0.95

# What is looked at first. The order is the order of action: what already ran
# out, what is about to, and only at the end what there is too much of.
_URGENCY = {
    StockStatus.OUT_OF_STOCK: 0, StockStatus.CRITICAL: 1, StockStatus.LOW: 2,
    StockStatus.HEALTHY: 3, StockStatus.EXCESS: 4, StockStatus.NO_DEMAND: 5
}


def _latest_snapshot(stock: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[pd.Timestamp]]:
    '''
        Keeps the most recent photo of each product.

        The file may carry several days —a client dumping a week of snapshots
        at once— and the view is about today. Summing them would report a
        warehouse several times its real size.

        Args:
            stock (pd.DataFrame): Normalized snapshot rows.

        Returns:
            tuple: The latest rows per product, and the date of the photo.
    '''
    frame = stock.copy()
    if SNAPSHOT_DATE in frame.columns:
        frame[SNAPSHOT_DATE] = pd.to_datetime(frame[SNAPSHOT_DATE], errors = 'coerce')
        latest = frame[SNAPSHOT_DATE].max()
        if pd.notna(latest):
            frame = frame.loc[frame[SNAPSHOT_DATE] == latest]
            return frame, latest

    return frame, None


def _daily_demand(sales: pd.DataFrame) -> pd.Series:
    '''
        Units sold per day of each product, over the configured window.

        Measured over the window and not over the whole history: what a product
        sold two years ago says nothing about how long today's stock lasts.

        Args:
            sales (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.Series: Units per day, indexed by product id. Empty when the
                frame cannot support the measurement.
    '''
    if PRODUCT_ID not in sales.columns or QUANTITY not in sales.columns:
        return pd.Series(dtype = 'float64')
    if DATE not in sales.columns:
        return pd.Series(dtype = 'float64')

    dates = pd.to_datetime(sales[DATE], errors = 'coerce')
    last = dates.max()
    if pd.isna(last):
        return pd.Series(dtype = 'float64')

    window_start = last - pd.Timedelta(days = _DEMAND_WINDOW)
    recent = sales.loc[dates > window_start]
    if recent.empty:
        return pd.Series(dtype = 'float64')

    # The days the data actually spans, not the days asked for: a file holding
    # 20 days cannot be divided by 90, or the daily demand would come out four
    # times smaller. The "+ 1" is the day of the first sale, which sold too:
    # without it, 30 days of history are divided by 29 and demand comes out
    # inflated.
    first = max(window_start, dates.min())
    span = max((last - first).days + 1, 1)
    units = recent.groupby(recent[PRODUCT_ID].astype(str))[QUANTITY].sum()
    return (units / span).astype('float64')


def _unit_values(sales: pd.DataFrame) -> pd.Series:
    '''
        Unit cost per product, preferring the snapshot's own and falling back
        to the sales history.

        Args:
            sales (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.Series: Unit cost indexed by product id, empty when unknown.
    '''
    if PRODUCT_ID not in sales.columns or UNIT_COST not in sales.columns:
        return pd.Series(dtype = 'float64')
    costs = pd.to_numeric(sales[UNIT_COST], errors = 'coerce')
    return costs.groupby(sales[PRODUCT_ID].astype(str)).mean().dropna()


def _abc_classes(sales: pd.DataFrame) -> pd.Series:
    '''
        The ABC class of each product, so a stockout on an A is not read like
        one on a C.

        Args:
            sales (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.Series: 'A', 'B' or 'C' indexed by product id.
    '''
    if PRODUCT_ID not in sales.columns or AMOUNT not in sales.columns:
        return pd.Series(dtype = 'object')

    totals = sales.groupby(sales[PRODUCT_ID].astype(str))[AMOUNT].sum()
    totals = totals[totals > 0].sort_values(ascending = False)
    if totals.empty:
        return pd.Series(dtype = 'object')

    # The share accumulated BEFORE each product, not the one that includes it:
    # a product concentrating 99% of the sales has a cumulative share of 0.99
    # and came out class C, when by definition it is the first A of the
    # catalogue. The item that crosses a threshold belongs to the class that
    # crosses it.
    shares = totals / totals.sum()
    preceding = shares.cumsum() - shares
    return preceding.map(
        lambda share: 'A' if share < _ABC_A_LIMIT
        else ('B' if share < _ABC_B_LIMIT else 'C')
    )


def _status_of(
    coverage: Optional[float],
    on_hand: float,
    demand: float
) -> StockStatus:
    '''
        Reads one product's situation.

        Args:
            coverage (float | None): Days of coverage, None when no demand.
            on_hand (float): Units in the warehouse.
            demand (float): Units sold per day.

        Returns:
            StockStatus: The status code; the UI words it.
    '''
    if on_hand <= 0:
        return StockStatus.OUT_OF_STOCK
    if demand <= 0 or coverage is None:
        # With stock and no measured demand there is no coverage to compute:
        # it is idle capital, and saying so is more honest than reporting
        # infinite coverage.
        return StockStatus.NO_DEMAND
    if coverage <= _CRITICAL_DAYS:
        return StockStatus.CRITICAL
    if coverage <= _LOW_DAYS:
        return StockStatus.LOW
    if coverage >= _EXCESS_DAYS:
        return StockStatus.EXCESS
    return StockStatus.HEALTHY


def _rows(
    snapshot: pd.DataFrame,
    demand: pd.Series,
    costs: pd.Series,
    classes: pd.Series,
    as_of: Optional[pd.Timestamp]
) -> List[StockRow]:
    '''
        Builds one row per product in the warehouse.

        Args:
            snapshot (pd.DataFrame): Latest snapshot rows.
            demand (pd.Series): Units sold per day, per product.
            costs (pd.Series): Unit cost per product.
            classes (pd.Series): ABC class per product.
            as_of (pd.Timestamp | None): Date of the photo, for the stockout date.

        Returns:
            List[StockRow]: Rows sorted by how urgent they are.
    '''
    grouped = snapshot.groupby(snapshot[PRODUCT_ID].astype(str)).agg(
        label = (PRODUCT_NAME, 'first') if PRODUCT_NAME in snapshot.columns
                else (PRODUCT_ID, 'first'),
        on_hand = (ON_HAND, 'sum'),
        committed = (COMMITTED, 'sum') if COMMITTED in snapshot.columns
                    else (ON_HAND, 'size'),
        in_transit = (IN_TRANSIT, 'sum') if IN_TRANSIT in snapshot.columns
                     else (ON_HAND, 'size'),
        unit_cost = (UNIT_COST, 'mean') if UNIT_COST in snapshot.columns
                    else (ON_HAND, 'size')
    )
    present = {'committed': COMMITTED in snapshot.columns,
               'in_transit': IN_TRANSIT in snapshot.columns,
               'unit_cost': UNIT_COST in snapshot.columns}

    rows = [
        _row_of(product, row, present, _Context(demand, costs, classes, as_of))
        for product, row in grouped.iterrows()
    ]
    # The urgent first: out of stock, critical, low — and inside each group,
    # whatever moves the most money.
    rows.sort(key = lambda row: (_URGENCY[row.status_code], -(row.stock_value or 0.0)))
    return rows


@dataclass(frozen = True)
class _Context:
    '''
        What every row needs from outside the snapshot, grouped so the row
        builder stays inside the argument budget.
    '''
    demand: pd.Series
    costs: pd.Series
    classes: pd.Series
    as_of: Optional[pd.Timestamp]


def _excess_units(
    on_hand: float,
    daily: float,
    coverage: Optional[float]
) -> float:
    '''
        Units above the configured coverage ceiling.

        Args:
            on_hand (float): Units in the warehouse.
            daily (float): Units sold per day.
            coverage (float | None): Days of coverage.

        Returns:
            float: The surplus. With no measured demand every unit counts as
                immobilized capital, which is the honest reading of stock
                nobody is buying.
    '''
    if daily > 0 and coverage is not None and coverage > _EXCESS_DAYS:
        return round(on_hand - daily * _EXCESS_DAYS, 2)
    if daily <= 0 < on_hand:
        return round(on_hand, 2)
    return 0.0


def _row_of(
    product: object,
    row: pd.Series,
    present: dict,
    context: _Context
) -> StockRow:
    '''
        Builds one product's row.

        Args:
            product (object): Product id.
            row (pd.Series): Its aggregated snapshot values.
            present (dict): Which optional columns the snapshot carries.
            context (_Context): Demand, costs, ABC classes and the photo date.

        Returns:
            StockRow: The product as the view reports it.
    '''
    on_hand = float(row['on_hand'])
    committed = float(row['committed']) if present['committed'] else 0.0
    daily = float(context.demand.get(product, 0.0))

    cost = (
        float(row['unit_cost'])
        if present['unit_cost'] and pd.notna(row['unit_cost']) else None
    )
    if cost is None:
        fallback = context.costs.get(product)
        cost = float(fallback) if fallback is not None and pd.notna(fallback) else None

    coverage = round(ratio(on_hand, daily), _COVERAGE_DECIMALS) if daily > 0 else None
    surplus = _excess_units(on_hand, daily, coverage)

    return StockRow(
        label = str(row['label']),
        product_id = str(product),
        on_hand = money(on_hand),
        committed = money(committed),
        available = money(on_hand - committed),
        in_transit = money(float(row['in_transit'])) if present['in_transit'] else 0.0,
        daily_demand = round(daily, 2),
        coverage_days = coverage,
        stockout_date = (
            (context.as_of + pd.Timedelta(days = coverage)).date().isoformat()
            if coverage is not None and context.as_of is not None else None
        ),
        status_code = _status_of(coverage, on_hand, daily),
        abc_class = (
            str(context.classes.get(product)) if product in context.classes.index else None
        ),
        stock_value = money(on_hand * cost) if cost is not None else None,
        excess_units = surplus,
        excess_value = money(surplus * cost) if cost is not None else None
    )


_AT_RISK = (StockStatus.OUT_OF_STOCK, StockStatus.CRITICAL, StockStatus.LOW)
_EXCESS = (StockStatus.EXCESS, StockStatus.NO_DEMAND)


def _kpis(
    rows: List[StockRow],
    as_of: Optional[pd.Timestamp]
) -> StockKpis:
    '''
        The headline figures of the warehouse.

        Args:
            rows (List[StockRow]): Every product of the snapshot.
            as_of (pd.Timestamp | None): Date of the photo.

        Returns:
            StockKpis: Position, money at rest and what is at risk.
    '''
    values = [row.stock_value for row in rows if row.stock_value is not None]
    excess_values = [row.excess_value for row in rows if row.excess_value is not None]
    coverages = [row.coverage_days for row in rows if row.coverage_days is not None]
    at_risk = [row for row in rows if row.status_code in _AT_RISK]

    return StockKpis(
        snapshot_date = as_of.date().isoformat() if as_of is not None else None,
        products = len(rows),
        units_on_hand = money(sum(row.on_hand for row in rows)),
        units_committed = money(sum(row.committed for row in rows)),
        units_available = money(sum(row.available for row in rows)),
        stock_value = money(sum(values)) if values else None,
        out_of_stock = sum(1 for row in rows if row.status_code == StockStatus.OUT_OF_STOCK),
        at_risk = len(at_risk),
        excess_products = sum(1 for row in rows if row.status_code in _EXCESS),
        excess_value = money(sum(excess_values)) if excess_values else None,
        average_coverage_days = (
            round(sum(coverages) / len(coverages), _COVERAGE_DECIMALS)
            if coverages else None
        ),
        # What stops being sold per day if nothing is replenished: the daily
        # demand of what is at risk, valued.
        stockout_value_at_risk = money(sum(
            row.daily_demand * (row.stock_value or 0.0) / row.on_hand
            for row in at_risk if row.on_hand > 0
        ))
    )


def build_stock(
    sales: pd.DataFrame,
    stock: Optional[pd.DataFrame] = None
) -> StockBlock:
    '''
        Builds the stock view from the snapshot and the sales that measure it.

        Args:
            sales (pd.DataFrame): Normalized sales rows, which provide the
                observed demand, the ABC class and the fallback unit cost.
            stock (pd.DataFrame | None): Normalized snapshot rows. Their absence
                means no snapshot was ever loaded, which is reported with a code
                rather than as an empty warehouse.

        Returns:
            StockBlock: The whole view, or an unavailable block with its code.
    '''
    if stock is None or stock.empty:
        return unavailable_block(StockBlock, 'Stock', StockUnavailable.NO_SNAPSHOT)
    if PRODUCT_ID not in stock.columns or ON_HAND not in stock.columns:
        return unavailable_block(StockBlock, 'Stock', StockUnavailable.NO_SNAPSHOT)

    snapshot, as_of = _latest_snapshot(stock)
    if snapshot.empty:
        return unavailable_block(StockBlock, 'Stock', StockUnavailable.NO_PRODUCTS)

    rows = _rows(
        snapshot = snapshot,
        demand = _daily_demand(sales),
        costs = _unit_values(sales),
        classes = _abc_classes(sales),
        as_of = as_of
    )
    if not rows:
        return unavailable_block(StockBlock, 'Stock', StockUnavailable.NO_PRODUCTS)

    kpis = _kpis(rows, as_of)
    message = (f'Building stock block: {kpis.products} product(s) as of '
               f'{kpis.snapshot_date}, {kpis.at_risk} at risk.')
    logger.info(message)

    return StockBlock(
        available = True,
        kpis = kpis,
        at_risk = [row for row in rows if row.status_code in _AT_RISK][:_TOP_ROWS],
        excess = sorted(
            [row for row in rows if row.status_code in _EXCESS],
            key = lambda row: -(row.excess_value or row.excess_units)
        )[:_TOP_ROWS],
        products = rows[:_MAX_PRODUCT_ROWS]
    )
