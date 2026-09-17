'''
    Unit tests for the receivables engine.

    Covers what the module is for: the balance at invoice level, the aging
    against the file's own reference date, the provision that separates
    recoverable from uncollectible, the policy falling back field by field, the
    credit margin once financed, and the tables somebody acts on.
'''
import pandas as pd

from schemas.receivables import AgingBucket, CreditRisk, ReceivablesUnavailable
from services.receivables import build_receivables, resolve_policy


def _sale(order: str, client: str, date: str, amount: float,
          terms: str = 'CREDITO') -> dict:
    '''
        One sales line of an invoice.

        Args:
            order (str): Invoice number.
            client (str): Client name.
            date (str): Invoice date.
            amount (float): Line amount.
            terms (str): CONTADO or CREDITO.

        Returns:
            dict: A normalized sales row with its credit columns.
    '''
    return {
        'order_id': order, 'pos_id': client, 'pos_name': client,
        'product_id': 'P1', 'product_name': 'Galleta', 'quantity': 1.0,
        'unit_price': amount, 'unit_cost': amount * 0.7, 'total_amount': amount,
        'date': pd.Timestamp(date), 'payment_terms': terms, 'credit_days': 30,
        'due_date': pd.NaT, 'collector': 'Juan Pérez', 'credit_limit': 10000.0
    }


def _payment(order: str, date: str, amount: float) -> dict:
    '''
        One payment row.

        Args:
            order (str): Invoice it pays.
            date (str): Payment date.
            amount (float): Amount collected.

        Returns:
            dict: A normalized collections row.
    '''
    return {
        'order_id': order, 'payment_date': pd.Timestamp(date),
        'paid_amount': amount, 'payment_method': 'EFECTIVO',
        'collector': 'Juan Pérez'
    }


def test_balance_is_the_invoice_total_not_the_line():
    '''
        An invoice spans several product lines: a payment is imputed against
        the whole document, so two lines of 600 and 400 paid with 1.000 leave
        nothing open.
    '''
    sales = pd.DataFrame([
        _sale('F-1', 'Tienda', '2026-03-01', 600.0),
        _sale('F-1', 'Tienda', '2026-03-01', 400.0),
    ])
    payments = pd.DataFrame([_payment('F-1', '2026-03-20', 1000.0)])

    block = build_receivables(sales, payments)

    assert block.available is True
    assert block.kpis.receivable_total == 0.0
    assert block.kpis.open_invoices == 0


def test_an_invoice_without_payments_is_an_open_balance():
    '''
        No payment rows is not an error and not zero debt: it is the whole
        invoice, still open.
    '''
    sales = pd.DataFrame([_sale('F-1', 'Tienda', '2026-03-01', 500.0)])

    block = build_receivables(sales, None)

    assert block.kpis.receivable_total == 500.0
    assert block.kpis.clients_with_debt == 1


def test_aging_is_measured_against_the_last_day_of_the_file():
    '''
        The reference date is the newest date in the data, not today. An
        invoice issued on the last day with a 30-day term is CURRENT, and one
        from four months earlier is deep in the overdue buckets.
    '''
    sales = pd.DataFrame([
        _sale('F-OLD', 'Vieja', '2026-01-01', 1000.0),
        _sale('F-NEW', 'Nueva', '2026-06-01', 1000.0),
    ])
    block = build_receivables(sales, None)
    buckets = {row.bucket_code: row for row in block.aging}

    assert block.kpis.as_of == '2026-06-01'
    assert buckets[AgingBucket.CURRENT].amount == 1000.0
    assert AgingBucket.DAYS_91_120 in buckets or AgingBucket.DAYS_OVER_120 in buckets
    assert block.kpis.overdue_amount == 1000.0


def test_aging_survives_pandas_python_string_storage():
    '''
        The Lambda package has no pyarrow, so pandas 3 keeps text in its Python
        storage, where a column of str-Enum members compared with an Enum is
        False on every row. The aging came back empty in production while this
        suite passed on a laptop with pyarrow: the block has to fill under both.
    '''
    previous = pd.options.mode.string_storage
    pd.options.mode.string_storage = 'python'
    try:
        sales = pd.DataFrame([
            _sale('F-OLD', 'Vieja', '2026-01-01', 1000.0),
            _sale('F-NEW', 'Nueva', '2026-06-01', 1000.0),
        ])
        for column in sales.columns:
            if pd.api.types.is_string_dtype(sales[column]):
                sales[column] = sales[column].astype('str')
        block = build_receivables(sales, None)
    finally:
        pd.options.mode.string_storage = previous

    buckets = {row.bucket_code: row for row in block.aging}
    assert buckets[AgingBucket.CURRENT].amount == 1000.0
    assert sum(row.provision for row in block.aging) > 0


def test_partial_payment_leaves_the_rest_open_and_ageing():
    '''Half collected is half a receivable, and it keeps getting older.'''
    sales = pd.DataFrame([_sale('F-1', 'Tienda', '2026-01-01', 1000.0)])
    payments = pd.DataFrame([_payment('F-1', '2026-02-01', 400.0)])

    block = build_receivables(sales, payments)

    assert block.kpis.receivable_total == 600.0
    assert block.kpis.overdue_amount == 600.0


def test_provision_splits_recoverable_from_uncollectible():
    '''
        The provision is the loss rate of each bucket applied to its balance,
        and what is left is what the client can expect back.
    '''
    sales = pd.DataFrame([
        _sale('F-1', 'Tienda', '2026-01-01', 1000.0),
        _sale('F-2', 'Market', '2026-06-01', 1000.0),
    ])
    block = build_receivables(sales, None)

    provisioned = sum(row.provision for row in block.aging)
    assert block.kpis.uncollectible_amount == round(provisioned, 2)
    assert round(
        block.kpis.recoverable_amount + block.kpis.uncollectible_amount, 2
    ) == block.kpis.receivable_total
    # The old bucket weighs more than the recent one, which is the point of
    # the provisioning matrix.
    assert block.kpis.uncollectible_rate > 0


def test_cash_only_dataset_reports_a_code_instead_of_an_empty_dashboard():
    '''
        A file with no credit sales is not a book with zero debt: the view says
        it cannot be built, with its code.
    '''
    sales = pd.DataFrame([_sale('F-1', 'Tienda', '2026-03-01', 500.0, terms = 'CONTADO')])

    block = build_receivables(sales, None)

    assert block.available is False
    assert block.reason_code == ReceivablesUnavailable.NO_CREDIT_SALES.value


def test_dataset_without_credit_columns_reports_its_own_code():
    '''A file from before the contract had credit columns is a different case.'''
    sales = pd.DataFrame([{
        'order_id': 'F-1', 'pos_id': 'C1', 'pos_name': 'Tienda',
        'product_id': 'P1', 'product_name': 'Galleta', 'quantity': 1.0,
        'total_amount': 100.0, 'date': pd.Timestamp('2026-03-01')
    }])

    block = build_receivables(sales, None)

    assert block.available is False
    assert block.reason_code == ReceivablesUnavailable.NO_CREDIT_COLUMNS.value


def test_policy_falls_back_field_by_field():
    '''
        Somebody who only wants to change the interest rate must not have to
        restate the buckets and the loss matrix.
    '''
    default = resolve_policy(None)
    partial = resolve_policy({'financial_rate_daily': 0.002})

    assert default.source_code == 'DEFAULT'
    assert partial.source_code == 'CLIENT'
    assert partial.financial_rate_daily == 0.002
    assert partial.buckets == default.buckets
    assert partial.loss_rates == default.loss_rates


def test_client_policy_changes_the_provision():
    '''
        Two clients with the same book get different provisions, which is the
        reason the policy travels with the answer.
    '''
    sales = pd.DataFrame([_sale('F-1', 'Tienda', '2026-01-01', 1000.0)])

    harsh = [0.5, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9]
    soft = [0.0, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01]
    strict = build_receivables(sales, None, {'loss_rates': harsh})
    lenient = build_receivables(sales, None, {'loss_rates': soft})

    assert strict.kpis.uncollectible_amount > lenient.kpis.uncollectible_amount
    assert strict.policy.source_code == 'CLIENT'


def test_credit_margin_subtracts_financing_and_expected_loss():
    '''
        The gross margin of a credit sale is not what it leaves: the money is
        out for a number of days and part of it never comes back.
    '''
    sales = pd.DataFrame([_sale('F-1', 'Tienda', '2026-01-01', 1000.0)])

    margin = build_receivables(sales, None).margin

    assert margin.available is True
    assert margin.credit_gross_margin == 300.0
    assert margin.financing_cost >= 0
    assert margin.net_margin == round(
        margin.credit_gross_margin - margin.financing_cost - margin.expected_loss, 2
    )


def test_margin_reports_its_code_without_a_cost_column():
    '''No cost column means no margin, and saying so beats reporting zero.'''
    sales = pd.DataFrame([_sale('F-1', 'Tienda', '2026-03-01', 500.0)]).drop(
        columns = ['unit_cost']
    )

    margin = build_receivables(sales, None).margin

    assert margin.available is False
    assert margin.reason_code == 'NO_COST_COLUMN'


def test_debtors_and_priority_rank_by_what_can_be_recovered():
    '''
        The list to call is ordered by expected recovery, not by age: an old
        balance that is 95% provisioned is worth less than a recent one.
    '''
    sales = pd.DataFrame([
        _sale('F-OLD', 'Incobrable', '2025-06-01', 1000.0),
        _sale('F-MID', 'Recuperable', '2026-04-20', 900.0),
        _sale('F-NEW', 'Corriente', '2026-06-01', 5000.0),
    ])
    block = build_receivables(sales, None)

    names = [row.label for row in block.priority]
    assert names[0] == 'Recuperable'
    assert 'Corriente' not in names            # todavía no está vencido

    debtors = {row.label: row for row in block.debtors}
    assert debtors['Incobrable'].risk_code == CreditRisk.CRITICAL
    assert debtors['Corriente'].risk_code == CreditRisk.HEALTHY
    assert debtors['Corriente'].limit_utilization == 50.0


def test_unknown_credit_limit_travels_empty_not_as_zero_usage():
    '''An unknown limit is not an unused one.'''
    sales = pd.DataFrame([_sale('F-1', 'Tienda', '2026-03-01', 500.0)]).drop(
        columns = ['credit_limit']
    )

    debtor = build_receivables(sales, None).debtors[0]

    assert debtor.credit_limit is None
    assert debtor.limit_utilization is None


def test_collector_carries_both_its_book_and_its_effectiveness():
    '''
        The overdue amount measures the book they were handed; the on-time rate
        measures them. Both travel so one is not read as the other.
    '''
    sales = pd.DataFrame([
        _sale('F-1', 'Tienda', '2026-01-01', 1000.0),
        _sale('F-2', 'Market', '2026-02-01', 1000.0),
    ])
    payments = pd.DataFrame([_payment('F-2', '2026-02-20', 1000.0)])

    collector = build_receivables(sales, payments).collectors[0]

    assert collector.label == 'Juan Pérez'
    assert collector.open_amount == 1000.0
    assert collector.on_time_rate == 100.0


def test_due_calendar_separates_overdue_from_what_is_coming():
    '''
        Overdue money is not a cash projection: it should already have been
        collected, so it travels in its own window.
    '''
    sales = pd.DataFrame([
        _sale('F-OLD', 'Vieja', '2026-01-01', 400.0),
        _sale('F-SOON', 'Nueva', '2026-05-25', 600.0),
    ])
    block = build_receivables(sales, None)
    windows = {row.window_code: row.amount for row in block.due_windows}

    assert windows['OVERDUE'] == 400.0
    assert windows['DAYS_30'] == 600.0
    assert [row.due_date for row in block.due_dates] == ['2026-06-24']


def test_collection_curve_leaves_an_unelapsed_horizon_empty():
    '''
        Last month cannot have a 90-day figure. Reporting one would read as a
        collapse in collection speed.
    '''
    sales = pd.DataFrame([
        _sale('F-1', 'Tienda', '2026-01-05', 1000.0),
        _sale('F-2', 'Tienda', '2026-06-05', 1000.0),
    ])
    payments = pd.DataFrame([
        _payment('F-1', '2026-01-25', 1000.0),
        _payment('F-2', '2026-06-10', 500.0),
    ])
    block = build_receivables(sales, payments)
    curve = {point.cohort_month: point for point in block.collection_curve}

    assert curve['2026-01'].collected_30 == 100.0
    assert curve['2026-06'].collected_30 is None
    assert curve['2026-06'].collected_90 is None
