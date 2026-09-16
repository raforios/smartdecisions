'''
    Unit tests for the stock engine.

    Covers the line the module does not cross —it reports what the ERP
    committed and never reserves— plus the figures that turn a balance into a
    decision: coverage in days at the observed demand, the stockout date, the
    capital immobilized in stock nobody buys, and the codes a dataset without a
    snapshot gets.
'''
import pandas as pd

from schemas.stock import StockStatus, StockUnavailable
from services.stock import build_stock


def _sales(product: str, units: float, date: str, amount: float = 100.0,
           cost: float = 5.0) -> dict:
    '''
        One sales line.

        Args:
            product (str): Product name, which is also its id here.
            units (float): Units sold.
            date (str): Sale date.
            amount (float): Line amount.
            cost (float): Unit cost.

        Returns:
            dict: A normalized sales row.
    '''
    return {
        'order_id': f'F-{product}-{date}', 'pos_id': 'C1', 'pos_name': 'Tienda',
        'product_id': product, 'product_name': product, 'quantity': units,
        'unit_price': 10.0, 'unit_cost': cost, 'total_amount': amount,
        'date': pd.Timestamp(date)
    }


def _snapshot(product: str, on_hand: float, date: str = '2026-06-30',
              committed: float = 0.0, cost: float = 5.0) -> dict:
    '''
        One stock snapshot row.

        Args:
            product (str): Product name, which is also its id here.
            on_hand (float): Units in the warehouse.
            date (str): Date of the photo.
            committed (float): Units the ERP already committed.
            cost (float): Unit cost.

        Returns:
            dict: A normalized snapshot row.
    '''
    return {
        'snapshot_date': pd.Timestamp(date), 'product_id': product,
        'product_name': product, 'on_hand': on_hand, 'committed': committed,
        'in_transit': 0.0, 'warehouse': 'Central', 'unit_cost': cost
    }


def _daily_sales(product: str, units_per_day: float, days: int = 30,
                 end: str = '2026-06-30') -> list:
    '''
        A steady sales history, so the measured daily demand is predictable.

        Args:
            product (str): Product sold.
            units_per_day (float): Units sold each day.
            days (int): How many days of history.
            end (str): Last day of the history.

        Returns:
            list: Normalized sales rows.
    '''
    last = pd.Timestamp(end)
    return [
        _sales(product, units_per_day, (last - pd.Timedelta(days = offset)).date().isoformat())
        for offset in range(days)
    ]


def test_available_reports_what_the_erp_committed():
    '''
        `available` is on hand minus committed: it reports a decision the ERP
        already took. Nothing here reserves anything.
    '''
    sales = pd.DataFrame(_daily_sales('Galleta', 10.0))
    stock = pd.DataFrame([_snapshot('Galleta', 500.0, committed = 120.0)])

    row = build_stock(sales, stock).products[0]

    assert row.on_hand == 500.0
    assert row.committed == 120.0
    assert row.available == 380.0


def test_coverage_is_measured_at_the_observed_demand():
    '''
        Ten units a day and 100 in the warehouse is ten days of coverage, and
        the stockout date is the photo plus that.
    '''
    sales = pd.DataFrame(_daily_sales('Galleta', 10.0))
    stock = pd.DataFrame([_snapshot('Galleta', 100.0)])

    row = build_stock(sales, stock).products[0]

    assert row.daily_demand == 10.0
    assert row.coverage_days == 10.0
    assert row.stockout_date == '2026-07-10'
    assert row.status_code == StockStatus.LOW


def test_a_product_about_to_run_out_is_flagged_critical():
    '''Under the critical threshold the product leads the at-risk list.'''
    sales = pd.DataFrame(_daily_sales('Leche', 20.0))
    stock = pd.DataFrame([_snapshot('Leche', 60.0)])

    block = build_stock(sales, stock)

    assert block.at_risk[0].status_code == StockStatus.CRITICAL
    assert block.kpis.at_risk == 1


def test_out_of_stock_leads_the_risk_list_and_its_own_count():
    '''Zero on hand is its own situation, not just low coverage.'''
    sales = pd.DataFrame(_daily_sales('Leche', 20.0))
    stock = pd.DataFrame([_snapshot('Leche', 0.0)])

    block = build_stock(sales, stock)

    assert block.kpis.out_of_stock == 1
    assert block.at_risk[0].status_code == StockStatus.OUT_OF_STOCK
    assert block.at_risk[0].coverage_days == 0.0


def test_stock_without_demand_is_immobilized_capital_not_infinite_coverage():
    '''
        A product with stock and no measured sales has no coverage to compute:
        reporting infinite days would dress up dead capital as a healthy
        balance.
    '''
    sales = pd.DataFrame(_daily_sales('Galleta', 10.0))
    stock = pd.DataFrame([
        _snapshot('Galleta', 300.0),
        _snapshot('Descontinuado', 80.0, cost = 12.0),
    ])
    block = build_stock(sales, stock)
    dead = {row.product_id: row for row in block.products}['Descontinuado']

    assert dead.coverage_days is None
    assert dead.status_code == StockStatus.NO_DEMAND
    assert dead.excess_units == 80.0
    assert dead.excess_value == 960.0


def test_excess_counts_only_what_exceeds_the_coverage_ceiling():
    '''
        Excess is not the whole balance: it is what sits above the configured
        ceiling of coverage.
    '''
    sales = pd.DataFrame(_daily_sales('Galleta', 10.0))
    # 90 days of ceiling x 10 per day = 900 units of healthy coverage; the
    # warehouse holds 1,500.
    stock = pd.DataFrame([_snapshot('Galleta', 1500.0)])

    row = build_stock(sales, stock).excess[0]

    assert row.status_code == StockStatus.EXCESS
    assert row.excess_units == 600.0
    assert row.excess_value == 3000.0


def test_only_the_latest_photo_is_read():
    '''
        A file carrying several days is a week of snapshots, not a warehouse
        several times its size.
    '''
    sales = pd.DataFrame(_daily_sales('Galleta', 10.0))
    stock = pd.DataFrame([
        _snapshot('Galleta', 400.0, date = '2026-06-28'),
        _snapshot('Galleta', 100.0, date = '2026-06-30'),
    ])
    block = build_stock(sales, stock)

    assert block.kpis.snapshot_date == '2026-06-30'
    assert block.kpis.units_on_hand == 100.0
    assert len(block.products) == 1


def test_abc_class_travels_so_a_stockout_can_be_weighed():
    '''A stockout on an A is not read like one on a C.'''
    sales = pd.DataFrame(
        _daily_sales('Estrella', 10.0) + [_sales('Cola', 1.0, '2026-06-30', amount = 5.0)]
    )
    stock = pd.DataFrame([_snapshot('Estrella', 50.0), _snapshot('Cola', 50.0)])
    rows = {row.product_id: row for row in build_stock(sales, stock).products}

    assert rows['Estrella'].abc_class == 'A'
    assert rows['Cola'].abc_class in ('B', 'C')


def test_stock_value_uses_the_snapshot_cost_and_falls_back_to_sales():
    '''
        The warehouse's own cost wins; without it the sales history answers,
        and without either the value travels empty instead of as zero.
    '''
    sales = pd.DataFrame(_daily_sales('Galleta', 10.0, end = '2026-06-30'))
    with_cost = pd.DataFrame([_snapshot('Galleta', 100.0, cost = 7.0)])
    assert build_stock(sales, with_cost).kpis.stock_value == 700.0

    without_cost = pd.DataFrame([_snapshot('Galleta', 100.0)]).drop(columns = ['unit_cost'])
    # Falls back to the cost in the sales history, which is 5.
    assert build_stock(sales, without_cost).kpis.stock_value == 500.0

    blind = sales.drop(columns = ['unit_cost'])
    assert build_stock(blind, without_cost).kpis.stock_value is None


def test_no_snapshot_reports_its_code_instead_of_an_empty_warehouse():
    '''A dataset nobody uploaded stock for is not a warehouse with nothing in it.'''
    sales = pd.DataFrame(_daily_sales('Galleta', 10.0))

    block = build_stock(sales, None)

    assert block.available is False
    assert block.reason_code == StockUnavailable.NO_SNAPSHOT.value


def test_snapshot_without_the_contract_columns_reports_the_same_code():
    '''A file that is not a snapshot cannot be read as one.'''
    sales = pd.DataFrame(_daily_sales('Galleta', 10.0))
    junk = pd.DataFrame([{'producto': 'Galleta', 'cantidad': 10}])

    block = build_stock(sales, junk)

    assert block.available is False
    assert block.reason_code == StockUnavailable.NO_SNAPSHOT.value
