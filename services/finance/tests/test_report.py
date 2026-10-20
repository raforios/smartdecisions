'''
    Tests for the financial report, with figures worked out by hand.

    What they defend: the layout Rafael approved on 16-oct — IVA and IT come
    off the sales every month, the IVA credit off the invoiced purchases, the
    IUE provision is a reserve and never a guess — and that nothing is
    invented when data is missing.
'''
import pytest

from schemas.entries import EntrySchema, LoadFlow, Periodicity
from schemas.report import FigureOrigin, ReportError
from services.report import Context, build_report, settings_from

# The values docs/parametros.md seeds into PARAMETERS.
FINANCE_VALUES = {
    'SALES_GROUP': '4.1', 'FINANCIAL_EXPENSE_GROUP': '6.3', 'IT_ACCOUNT': '6.1.10',
    'CASH_ACCOUNTS': ['1.1.01', '1.1.02', '1.1.03', '1.1.04', '1.1.05'],
    'CURRENT_ASSETS_GROUP': '1.1', 'CURRENT_LIABILITIES_GROUP': '2.1', 'VAT_CODE': 'IVA',
    'TRANSACTIONS_TAX_CODE': 'IT', 'INCOME_TAX_CODE': 'IUE',
    'INCOME_TAX_PROVISION_CODE': 'IUE_PROVISION', 'COVERAGE_MONTHS': 3.0,
    'MIN_MONTHS_FOR_TRENDS': 3.0, 'MIN_MONTHS_FOR_PROJECTION': 12.0, 'BALANCE_TOLERANCE': 1.0,
}
GLOBAL_VALUES = {'AMOUNT_DECIMALS': 2.0, 'RATIO_DECIMALS': 2.0}
SETTINGS = settings_from(FINANCE_VALUES, GLOBAL_VALUES)

CATALOG = {code: {'account_code': code, 'account_type': code[0], 'group_code': code[:3],
                  **extra}
           for code, extra in {
               '4.1.01': {'invoiced': True}, '4.1.05': {'invoiced': False},
               '4.1.04': {'subtracts': True}, '4.2.01': {},
               '5.1.02': {'invoiced': True}, '5.1.05': {'invoiced': False},
               '6.1.03': {}, '6.1.10': {}, '6.3.01': {},
               '1.1.01': {}, '1.1.06': {}, '1.2.02': {}, '1.2.07': {'subtracts': True},
               '2.1.01': {}, '2.2.01': {}, '3.1.01': {}, '3.2.03': {'subtracts': True},
           }.items()}
RATES = {'IVA': [('1992-03-01', 13.0)], 'IT': [('1995-01-01', 3.0)],
         'IUE': [('1995-01-01', 25.0)]}

# A month worked by hand: sales 1.150 (1.000 invoiced gross, 200 without
# invoice, 50 returned); IVA 130; IT 30; net sales 990; purchases 600 less a
# credit of 65 = cost 535; gross profit 455; rent 100; EBIT 355; other income
# 20 and interest 10; profit before IUE 365; IVA payable 130 - 65 = 65.
MONTH = [('4.1.01', 1000, True), ('4.1.05', 200, None), ('4.1.04', 50, None),
         ('4.2.01', 20, None), ('5.1.02', 500, True), ('5.1.05', 100, None),
         ('6.1.03', 100, None), ('6.3.01', 10, None)]
# Its balance: assets 100 + 300 + 500 - 50 = 850; liabilities 200 + 300 = 500;
# equity 400 - 50 = 350.
BALANCE = [('1.1.01', 100), ('1.1.06', 300), ('1.2.02', 500), ('1.2.07', 50),
           ('2.1.01', 200), ('2.2.01', 300), ('3.1.01', 400), ('3.2.03', 50)]


def _entry(
    code: str,
    amount: float,
    **fields
) -> EntrySchema:
    '''
        One stored amount.

        Returns:
            EntrySchema: The amount.
    '''
    values = {'periodicity': Periodicity.MONTHLY, 'date': '2026-03', 'taxes_included': None,
              'flow': LoadFlow.PROCESSED, 'load_id': 'l', 'user': 'u', 'updated_at': 't',
              **fields}
    return EntrySchema(account_code = code, amount = amount, **values)


def _month(
    flow: LoadFlow = LoadFlow.PROCESSED,
    date: str = '2026-03',
    with_it: bool = True
) -> list[EntrySchema]:
    '''
        The month worked by hand, loaded one way or the other.

        Returns:
            list[EntrySchema]: Its amounts.
    '''
    rows = [_entry(code, amount, taxes_included = taxed, flow = flow, date = date)
            for code, amount, taxed in MONTH]
    if with_it:
        rows.append(_entry('6.1.10', 30, flow = flow, date = date))
    return rows + [_entry(code, amount, flow = flow, date = date) for code, amount in BALANCE]


def _report(
    entries: list[EntrySchema],
    provision: float | None = 2.0
):
    '''
        The report of some amounts.

        Returns:
            FinanceReportSchema: The report.
    '''
    return build_report(entries, Context(CATALOG, RATES, provision, SETTINGS))


def test_the_income_statement_follows_the_approved_layout():
    '''Every line of the month worked by hand, in a processed load.'''
    month = _report(_month()).months[0]
    lines = {name: line.amount for name, line in month.income_statement if line}
    assert lines == {
        'sales': 1150, 'sales_vat': 130, 'transactions_tax': 30, 'net_sales': 990,
        'cost_of_sales': 535, 'gross_profit': 455, 'operating_expenses': 100,
        'operating_profit': 355, 'financial_result': 10, 'profit_before_income_tax': 365,
    }
    assert month.income_statement.transactions_tax.origin is FigureOrigin.LOADED
    assert (month.taxes.vat_payable.amount, month.taxes.income_tax_provision.amount) == (65, 20)


def test_a_base_load_calculates_the_it_and_lands_on_the_same_figures():
    '''Without the IT loaded, a base load gets 3 % of the gross invoiced sales.'''
    month = _report(_month(LoadFlow.BASE, with_it = False)).months[0]
    assert month.income_statement.transactions_tax.amount == 30
    assert month.income_statement.transactions_tax.origin is FigureOrigin.CALCULATED
    assert month.income_statement.profit_before_income_tax.amount == 365


def test_a_processed_load_without_its_it_says_so():
    '''Nothing is invented: the IT that was not loaded is missing, with its code.'''
    month = _report(_month(with_it = False)).months[0]
    assert month.income_statement.transactions_tax.amount is None
    assert ReportError.IT_NOT_LOADED in month.notices


def test_the_provision_is_never_calculated_with_a_rate_nobody_chose():
    '''Until the client sets its own rate, the provision is empty and coded.'''
    month = _report(_month(), provision = None).months[0]
    assert month.taxes.income_tax_provision.amount is None
    assert ReportError.IUE_PROVISION_NOT_SET in month.notices


def test_the_balance_and_its_indicators():
    '''850 = 500 + 350; liquidity 400 / 200; the debt is 500 / 850.'''
    month = _report(_month()).months[0]
    balance = month.balance
    assert (balance.assets, balance.liabilities, balance.equity) == (850, 500, 350)
    assert month.balance.difference == 0 and ReportError.BALANCE_MISMATCH not in month.notices
    assert (month.indicators.liquidity, month.indicators.debt_ratio) == (2.0, 0.59)
    # Cash 100 against an outflow of 600 + 100 + 10 + 30 = 740 a month.
    assert month.indicators.coverage_months == 0.14
    # The margin the owner's goal is compared with: 365 of profit on 990 of net sales.
    assert month.indicators.margin == 0.37


def test_a_balance_that_does_not_square_is_said_not_corrected():
    '''Ten bolivianos off is more than the rounding tolerance.'''
    entries = _month() + [_entry('1.1.01', 110)]
    entries = [e for e in entries if not (e.account_code == '1.1.01' and e.amount == 100)]
    month = _report(entries).months[0]
    assert month.balance.difference == 10
    assert ReportError.BALANCE_MISMATCH in month.notices


def test_a_year_from_its_months_estimates_the_iue():
    '''Two months of 365 make 730 before IUE; 25 % of it is 182,50.'''
    year = _report(_month() + _month(date = '2026-04')).years[0]
    assert (year.period, year.origin) == ('2026', 'MONTHLY')
    assert year.income_statement.profit_before_income_tax.amount == 730
    assert year.income_statement.income_tax_estimated.amount == 182.5
    assert year.income_statement.net_profit_estimated.amount == 547.5


def test_a_loss_pays_no_iue_and_a_month_has_no_annual_lines():
    '''No profit, no IUE; and the estimate only exists for a year.'''
    loss = [_entry('6.1.03', 1000)]
    report = _report(loss)
    assert report.years[0].income_statement.income_tax_estimated.amount == 0
    assert report.months[0].income_statement.income_tax_estimated is None


def test_a_month_of_days_takes_their_sum_and_its_last_balance():
    '''Flows add up; the balance is a picture of the last day loaded.'''
    days = [_entry('6.1.03', 100, periodicity = Periodicity.DAILY, date = day)
            for day in ('2026-03-02', '2026-03-03')]
    days += [_entry('1.1.01', cash, periodicity = Periodicity.DAILY, date = day)
             for day, cash in (('2026-03-02', 500), ('2026-03-03', 450))]
    month = _report(days).months[0]
    assert month.origin == 'DAILY'
    assert month.income_statement.operating_expenses.amount == 200
    assert month.balance.cash == 450


def test_a_year_loaded_whole_is_never_split():
    '''An annual load is its own year and makes no months.'''
    report = _report([_entry(code, amount, taxes_included = taxed, date = '2024',
                             periodicity = Periodicity.ANNUAL)
                      for code, amount, taxed in MONTH] + [
                         _entry('6.1.10', 30, date = '2024', periodicity = Periodicity.ANNUAL)])
    assert report.months == []
    assert (report.years[0].period, report.years[0].origin) == ('2024', 'ANNUAL')
    assert ReportError.NOT_ENOUGH_HISTORY_FOR_TRENDS in report.notices


@pytest.mark.parametrize(('months', 'notices'), [
    (2, {ReportError.NOT_ENOUGH_HISTORY_FOR_TRENDS, ReportError.NOT_ENOUGH_HISTORY_FOR_PROJECTION}),
    (3, {ReportError.NOT_ENOUGH_HISTORY_FOR_PROJECTION}),
    (12, set()),
])
def test_the_minimum_history_is_said(
    months,
    notices
):
    '''3 months for trends, 12 to project (approved by Rafael).'''
    entries = [_entry('6.1.03', 1, date = f'2025-{m:02d}') for m in range(1, months + 1)]
    assert set(_report(entries).notices) == notices


def test_a_value_changed_in_parameters_changes_the_report():
    '''The tolerance the ADMIN sets is the one the balance uses: no release.'''
    entries = [e for e in _month() if e.account_code != '1.1.01'] + [_entry('1.1.01', 105)]
    strict = _report(entries).months[0]
    lenient = build_report(entries, Context(CATALOG, RATES, 2.0, settings_from(
        {**FINANCE_VALUES, 'BALANCE_TOLERANCE': 10.0}, GLOBAL_VALUES))).months[0]
    assert ReportError.BALANCE_MISMATCH in strict.notices
    assert ReportError.BALANCE_MISMATCH not in lenient.notices


def test_the_unfinished_year_is_compared_with_the_same_months_before():
    '''Two months of 2026 against January and February of 2025, not the whole of 2025.'''
    months = ('2025-01', '2025-02', '2025-03', '2026-01', '2026-02')
    report = _report([entry for month in months for entry in _month(date = month)])
    cut = report.year_to_date
    assert cut.through == '2026-02'
    assert cut.previous.period == '2025'
    assert cut.previous.income_statement.net_sales.amount == 2 * 990
    assert report.years[0].income_statement.net_sales.amount == 3 * 990


def test_without_every_month_before_there_is_nothing_to_compare_with():
    '''February of 2025 was never loaded: the comparison is not made up.'''
    months = ('2025-01', '2026-01', '2026-02')
    cut = _report([entry for month in months for entry in _month(date = month)]).year_to_date
    assert (cut.through, cut.previous) == ('2026-02', None)
