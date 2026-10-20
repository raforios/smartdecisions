'''
    The financial analysis report: income statement, taxes of the period,
    balance sheet and indicators, per month and per year.

    Computed when it is asked for and never stored (Rafael, 16-oct): a
    corrected amount or a new law rate can never leave a stale figure. The
    income statement follows the layout Rafael approved on 16-oct — the IVA
    and the IT come off the sales every month, the IVA credit off the
    purchases, and the IUE provision is a cash reserve, not an expense.

    Nothing is invented: a figure without the data behind it is None and the
    report says why with a code.
'''
from collections.abc import Callable
from typing import Any
from dataclasses import dataclass
from datetime import date as date_type

from boto3.resources.base import ServiceResource

from schemas.entries import EntrySchema, LoadFlow, Periodicity
from schemas.finance import AccountType
from schemas.report import (
    BalanceSheetSchema,
    FigureOrigin,
    FinanceReportSchema,
    IncomeStatementSchema,
    IndicatorsSchema,
    LineSchema,
    PeriodReportSchema,
    PeriodTaxesSchema,
    ReportError,
    YearToDateSchema
)
from services.entries import list_entries, local_now
from services.finance import catalog_by_code
from services.parameters import client_value, law_rates, rate_on
from services.rates import period_rates
from services.report_periods import Period, add_month, split_periods
from services.utils import read_parameters, required_parameters

# The business values the report reads, by their code in PARAMETERS: the
# `finance` scope and the `global` one. They are read on every request (kept a
# few minutes by the PARAMETERS block), never from the .env (CLAUDE.md §5.3).
FINANCE_SCOPE = 'finance'
GLOBAL_SCOPE = 'global'
FINANCE_CODES = (
    'SALES_GROUP', 'FINANCIAL_EXPENSE_GROUP', 'IT_ACCOUNT', 'CASH_ACCOUNTS',
    'CURRENT_ASSETS_GROUP', 'CURRENT_LIABILITIES_GROUP', 'VAT_CODE', 'TRANSACTIONS_TAX_CODE',
    'INCOME_TAX_CODE', 'INCOME_TAX_PROVISION_CODE', 'COVERAGE_MONTHS', 'MIN_MONTHS_FOR_TRENDS',
    'MIN_MONTHS_FOR_PROJECTION', 'BALANCE_TOLERANCE',
)
GLOBAL_CODES = ('AMOUNT_DECIMALS', 'RATIO_DECIMALS')


@dataclass(frozen = True)
class ReportSettings:  # pylint: disable=too-many-instance-attributes
    '''
        The business values of the report, as PARAMETERS holds them. Sixteen
        values the ADMIN can change without a release; grouped here so every
        function receives one argument instead of sixteen.
    '''
    sales_group: str
    financial_expense_group: str
    it_account: str
    cash_accounts: tuple[str, ...]
    current_assets_group: str
    current_liabilities_group: str
    vat_code: str
    it_code: str
    iue_code: str
    iue_provision_code: str
    coverage_months: int
    min_months_for_trends: int
    min_months_for_projection: int
    balance_tolerance: float
    amount_decimals: int
    ratio_decimals: int


def settings_from(
    finance: dict[str, Any],
    general: dict[str, Any]
) -> ReportSettings:
    '''
        The report's values from what PARAMETERS answered for both scopes.

        Args:
            finance (dict[str, Any]): The `finance` scope.
            general (dict[str, Any]): The `global` scope.

        Returns:
            ReportSettings: The values.
    '''
    return ReportSettings(
        sales_group = finance['SALES_GROUP'],
        financial_expense_group = finance['FINANCIAL_EXPENSE_GROUP'],
        it_account = finance['IT_ACCOUNT'], cash_accounts = tuple(finance['CASH_ACCOUNTS']),
        current_assets_group = finance['CURRENT_ASSETS_GROUP'],
        current_liabilities_group = finance['CURRENT_LIABILITIES_GROUP'],
        vat_code = finance['VAT_CODE'], it_code = finance['TRANSACTIONS_TAX_CODE'],
        iue_code = finance['INCOME_TAX_CODE'],
        iue_provision_code = finance['INCOME_TAX_PROVISION_CODE'],
        coverage_months = int(finance['COVERAGE_MONTHS']),
        min_months_for_trends = int(finance['MIN_MONTHS_FOR_TRENDS']),
        min_months_for_projection = int(finance['MIN_MONTHS_FOR_PROJECTION']),
        balance_tolerance = float(finance['BALANCE_TOLERANCE']),
        amount_decimals = int(general['AMOUNT_DECIMALS']),
        ratio_decimals = int(general['RATIO_DECIMALS'])
    )




@dataclass(frozen = True)
class Context:
    '''
        What the calculation reads besides the amounts.
    '''
    catalog: dict[str, dict]
    rates: dict[str, list[tuple[str, float]]]
    provision_rate: float | None
    settings: ReportSettings


def _in_group(
    code: str,
    group: str
) -> bool:
    '''
        Whether an account sits in a group: 4.1.05 is in 4.1, 4.10.01 is not.

        Args:
            code (str): Account code.
            group (str): Group code.

        Returns:
            bool: True when the account belongs to the group.
    '''
    return code.startswith(f'{group}.')


def _round(
    value: float | None,
    decimals: int
) -> float | None:
    '''
        A published figure, rounded; None stays None.

        Args:
            value (float | None): The figure.
            decimals (int): Decimals to keep.

        Returns:
            float | None: The rounded figure.
    '''
    return None if value is None else round(value, decimals)


def _line(
    value: float | None,
    origin: FigureOrigin = FigureOrigin.CALCULATED
) -> LineSchema:
    '''
        One line of a report.

        Args:
            value (float | None): The figure.
            origin (FigureOrigin): Loaded or calculated.

        Returns:
            LineSchema: The line.
    '''
    return LineSchema(amount = value, origin = origin)


def _start_of(period: str) -> date_type:
    '''
        The first day of a month (YYYY-MM) or a year (YYYY): the day whose
        law rates apply to the period.

        Args:
            period (str): The period key.

        Returns:
            date: Its first day.
    '''
    return date_type.fromisoformat(f'{period}-01' if len(period) == 7 else f'{period}-01-01')


class _Sums:
    '''
        Signed sums of a set of amounts: an account marked «(Menos)» subtracts.
    '''

    def __init__(
        self,
        entries: list[EntrySchema],
        catalog: dict[str, dict]
    ) -> None:
        self.entries = entries
        self.catalog = catalog

    def account(
        self,
        code: str
    ) -> dict:
        '''
            The catalog item of an account.

            Args:
                code (str): Account code.

            Returns:
                dict: The account.
        '''
        return self.catalog[code]

    def total(
        self,
        keep: Callable[[EntrySchema, dict], bool]
    ) -> float:
        '''
            The signed sum of the amounts `keep` accepts.

            Args:
                keep (Callable[[EntrySchema, dict], bool]): Filter on the
                    amount and its account.

            Returns:
                float: The sum.
        '''
        return sum((-1 if self.account(e.account_code).get('subtracts') else 1) * e.amount
                   for e in self.entries if keep(e, self.account(e.account_code)))


def _year_to_date(
    months: dict[str, Period],
    context: Context
) -> YearToDateSchema | None:
    '''
        The year before, cut at the last loaded month, so the unfinished year
        is compared with the same months and not with a whole year.

        Args:
            months (dict[str, Period]): Every month the client has.
            context (Context): Catalog, law rates and the client's provision.

        Returns:
            YearToDateSchema | None: None without months.
    '''
    if not months:
        return None
    through = max(months)
    keys = [f'{int(through[:4]) - 1}-{month:02d}' for month in range(1, int(through[5:]) + 1)]
    if not all(key in months for key in keys):
        return YearToDateSchema(through = through)
    previous = Period(keys[0][:4], Periodicity.MONTHLY, months = 0)
    for key in keys:
        add_month(previous, months[key])
    return YearToDateSchema(through = through, previous = _period_report(
        previous, context, lambda outflow: outflow / len(keys)))


def _transactions_tax(
    period: Period,
    sums: _Sums,
    rate: float,
    settings: ReportSettings
) -> tuple[float | None, FigureOrigin, list[ReportError]]:
    '''
        The IT of the period, paid every month: the one loaded in its account
        (processed load), or 3 % of the gross invoiced sales (base load).

        Args:
            period (Period): The period.
            sums (_Sums): Its amounts.
            rate (float): The IT rate in force.
            settings (ReportSettings): The business values of the report.

        Returns:
            tuple: The amount, its origin and the notices it raises.
    '''
    if any(e.account_code == settings.it_account for e in period.flows):
        return (sums.total(lambda e, a: e.account_code == settings.it_account),
                FigureOrigin.LOADED, [])
    gross_invoiced = sums.total(
        lambda e, a: a.get('invoiced') is True and _in_group(e.account_code, settings.sales_group)
        and e.taxes_included is True)
    if any(e.flow is LoadFlow.BASE for e in period.flows):
        return gross_invoiced * rate, FigureOrigin.CALCULATED, []
    if not gross_invoiced:
        return 0.0, FigureOrigin.LOADED, []
    return None, FigureOrigin.LOADED, [ReportError.IT_NOT_LOADED]


def _taxed(
    account: dict,
    entry: EntrySchema
) -> bool:
    '''
        With invoice and its taxes inside the amount: the IVA is in there.

        Args:
            account (dict): The account.
            entry (EntrySchema): The amount.

        Returns:
            bool: True when the amount carries IVA.
    '''
    return account.get('invoiced') is True and entry.taxes_included is True


def _is_type(
    entry: EntrySchema,
    kind: AccountType
) -> bool:
    '''
        Whether an amount belongs to a type of the plan: its code says it.

        Args:
            entry (EntrySchema): The amount.
            kind (AccountType): The type.

        Returns:
            bool: True when the code starts with the digit of the type.
    '''
    return entry.account_code[0] == kind.value


def _vat(
    sums: _Sums,
    rate: float,
    sales_group: str
) -> tuple[float, float]:
    '''
        The IVA of a period: the debit inside the invoiced gross sales and
        the credit inside the invoiced gross purchases.

        Args:
            sums (_Sums): The amounts of the period.
            rate (float): The IVA rate in force.
            sales_group (str): The group the report takes as sales.

        Returns:
            tuple[float, float]: Debit and credit.
    '''
    debit = sums.total(lambda e, a: _in_group(e.account_code, sales_group) and _taxed(a, e))
    credit = sums.total(lambda e, a: _is_type(e, AccountType.COST) and _taxed(a, e))
    return debit * rate, credit * rate


def _statement(
    sums: _Sums,
    vat: tuple[float, float],
    transactions_tax: tuple[float | None, FigureOrigin],
    settings: ReportSettings
) -> IncomeStatementSchema:
    '''
        The income statement of a period, as Rafael approved it on 16-oct.

        Args:
            sums (_Sums): The amounts of the period.
            vat (tuple[float, float]): IVA debit and credit.
            transactions_tax (tuple[float | None, FigureOrigin]): The IT and its origin.
            settings (ReportSettings): The business values of the report.

        Returns:
            IncomeStatementSchema: The statement.
    '''
    vat_debit, vat_credit = vat
    it_amount, it_origin = transactions_tax
    sales_group, financial_group = settings.sales_group, settings.financial_expense_group
    sales = sums.total(lambda e, a: _in_group(e.account_code, sales_group))
    net_sales = sales - vat_debit - (it_amount or 0)
    gross = net_sales - (sums.total(lambda e, a: _is_type(e, AccountType.COST)) - vat_credit)
    operating = sums.total(lambda e, a: _is_type(e, AccountType.EXPENSE)
                           and not _in_group(e.account_code, financial_group)
                           and e.account_code != settings.it_account)
    financial = (sums.total(lambda e, a: _is_type(e, AccountType.INCOME)
                            and not _in_group(e.account_code, sales_group))
                 - sums.total(lambda e, a: _in_group(e.account_code, financial_group)))
    return IncomeStatementSchema(
        sales = _line(sales, FigureOrigin.LOADED), sales_vat = _line(vat_debit),
        transactions_tax = _line(it_amount, it_origin), net_sales = _line(net_sales),
        cost_of_sales = _line(net_sales - gross), gross_profit = _line(gross),
        operating_expenses = _line(operating, FigureOrigin.LOADED),
        operating_profit = _line(gross - operating), financial_result = _line(financial),
        profit_before_income_tax = _line(gross - operating + financial)
    )


def _provision(
    sums: _Sums,
    rate: float | None,
    sales_group: str
) -> float | None:
    '''
        The IUE provision: the share of everything invoiced the client chose
        to set aside. None while it has not chosen one — the suggestion is
        never applied on its own (Rafael, 16-oct).

        Args:
            sums (_Sums): The amounts of the period.
            rate (float | None): The client's percentage.
            sales_group (str): The group the report takes as sales.

        Returns:
            float | None: The reserve.
    '''
    if rate is None:
        return None
    invoiced = sums.total(lambda e, a: a.get('invoiced') is True
                          and _in_group(e.account_code, sales_group))
    return invoiced * rate / 100


def _estimate_income_tax(
    statement: IncomeStatementSchema,
    rate: float
) -> None:
    '''
        Adds the estimated IUE and net profit to an annual statement: 25 % of
        the profit, and nothing on a loss.

        Args:
            statement (IncomeStatementSchema): The annual statement, completed in place.
            rate (float): The IUE rate in force.
    '''
    before_tax = statement.profit_before_income_tax.amount
    estimated = max(before_tax, 0) * rate
    statement.income_tax_estimated = _line(estimated)
    statement.net_profit_estimated = _line(before_tax - estimated)


def income_statement(
    period: Period,
    context: Context
) -> tuple[IncomeStatementSchema, PeriodTaxesSchema, float, list[ReportError]]:
    '''
        The income statement and the taxes of one period.

        Args:
            period (Period): The period.
            context (Context): Catalog, law rates and the client's provision.

        Returns:
            tuple: The statement, the taxes, the period's outflow (for the
                coverage) and the notices.
    '''
    sums = _Sums(period.flows, context.catalog)
    day = _start_of(period.key)
    settings = context.settings
    vat_debit, vat_credit = _vat(sums, rate_on(context.rates, settings.vat_code, day),
                                 settings.sales_group)
    it_amount, it_origin, notices = _transactions_tax(
        period, sums, rate_on(context.rates, settings.it_code, day), settings)
    statement = _statement(sums, (vat_debit, vat_credit), (it_amount, it_origin), settings)
    if len(period.key) == 4:
        # The IUE is paid on the year: only an annual report estimates it.
        _estimate_income_tax(statement, rate_on(context.rates, settings.iue_code, day))

    provision = _provision(sums, context.provision_rate, settings.sales_group)
    if provision is None:
        notices.append(ReportError.IUE_PROVISION_NOT_SET)
    taxes = PeriodTaxesSchema(
        vat_payable = _line(vat_debit - vat_credit),
        transactions_tax = _line(it_amount, it_origin),
        income_tax_provision = _line(provision)
    )
    outflow = (sums.total(lambda e, a: _is_type(e, AccountType.COST)
                          or _is_type(e, AccountType.EXPENSE))
               + (it_amount if it_origin is FigureOrigin.CALCULATED else 0))
    return statement, taxes, outflow, notices


def balance_sheet(
    period: Period,
    catalog: dict[str, dict],
    settings: ReportSettings
) -> tuple[BalanceSheetSchema, list[ReportError]]:
    '''
        The balances at the end of the period, with what the client loaded.

        Args:
            period (Period): The period.
            catalog (dict[str, dict]): The accounts, by code.
            settings (ReportSettings): The business values of the report.

        Returns:
            tuple[BalanceSheetSchema, list[ReportError]]: The balance and its notices.
    '''
    if not period.balances:
        return BalanceSheetSchema(assets = None, current_assets = None, cash = None,
                                  liabilities = None, current_liabilities = None,
                                  equity = None), [ReportError.NO_BALANCE]
    sums = _Sums(period.balances, catalog)

    def of_type(kind: AccountType) -> float:
        return sums.total(lambda e, a: e.account_code[0] == kind.value)

    assets, liabilities, equity = (of_type(AccountType.ASSET), of_type(AccountType.LIABILITY),
                                   of_type(AccountType.EQUITY))
    difference = assets - liabilities - equity
    sheet = BalanceSheetSchema(
        assets = assets,
        current_assets = sums.total(lambda e, a: _in_group(e.account_code,
                                                           settings.current_assets_group)),
        cash = sums.total(lambda e, a: e.account_code in settings.cash_accounts),
        liabilities = liabilities,
        current_liabilities = sums.total(lambda e, a: _in_group(
            e.account_code, settings.current_liabilities_group)),
        equity = equity, difference = difference
    )
    # A balance that does not square is said, never corrected (Rafael, 15-oct).
    mismatch = abs(difference) > settings.balance_tolerance
    return sheet, [ReportError.BALANCE_MISMATCH] if mismatch else []


def _ratio(
    numerator: float | None,
    denominator: float | None
) -> float | None:
    '''
        A ratio, or None when either side is missing or the divisor is zero.

        Args:
            numerator (float | None): Top.
            denominator (float | None): Bottom.

        Returns:
            float | None: The ratio, unrounded: the report rounds at the end.
    '''
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def indicators(
    statement: IncomeStatementSchema,
    sheet: BalanceSheetSchema,
    monthly_outflow: float | None
) -> IndicatorsSchema:
    '''
        The ratios of a period.

        Args:
            statement (IncomeStatementSchema): Its income statement.
            sheet (BalanceSheetSchema): Its balance.
            monthly_outflow (float | None): Average monthly outflow behind it.

        Returns:
            IndicatorsSchema: Margin, liquidity, debt, solvency and months of coverage.
    '''
    return IndicatorsSchema(
        margin = _ratio(statement.profit_before_income_tax.amount, statement.net_sales.amount),
        liquidity = _ratio(sheet.current_assets, sheet.current_liabilities),
        debt_ratio = _ratio(sheet.liabilities, sheet.assets),
        solvency = _ratio(sheet.assets, sheet.liabilities),
        coverage_months = _ratio(sheet.cash, monthly_outflow)
    )


def _period_report(
    period: Period,
    context: Context,
    monthly_outflow: Callable[[float], float]
) -> PeriodReportSchema:
    '''
        The report of one month or one year.

        Args:
            period (Period): The period.
            context (Context): Catalog, law rates and the client's provision.
            monthly_outflow (Callable[[float], float]): Turns the period's
                outflow into the average monthly outflow its coverage uses.

        Returns:
            PeriodReportSchema: The report.
    '''
    statement, taxes, outflow, notices = income_statement(period, context)
    sheet, sheet_notices = balance_sheet(period, context.catalog, context.settings)
    return PeriodReportSchema(
        period = period.key, origin = period.origin.value, income_statement = statement,
        taxes = taxes, balance = sheet,
        indicators = indicators(statement, sheet, monthly_outflow(outflow)),
        notices = notices + sheet_notices
    )


def build_report(
    entries: list[EntrySchema],
    context: Context
) -> FinanceReportSchema:
    '''
        The whole report of a client, from its amounts. Pure: everything it
        reads arrives as arguments.

        Args:
            entries (list[EntrySchema]): Every amount of the client.
            context (Context): Catalog, law rates and the client's provision.

        Returns:
            FinanceReportSchema: Every month and every year, oldest first.
    '''
    months, years = split_periods(entries)
    outflows: dict[str, float] = {}
    month_reports = []
    for key in sorted(months):
        def recent_average(
            outflow: float,
            key: str = key
        ) -> float:
            outflows[key] = outflow
            recent = [outflows[k] for k in sorted(outflows)[-context.settings.coverage_months:]]
            return sum(recent) / len(recent)
        month_reports.append(_period_report(months[key], context, recent_average))
    year_reports = [
        _period_report(years[key], context,
                       lambda outflow, months_in = years[key].months: outflow / max(months_in, 1))
        for key in sorted(years)
    ]
    history = len(months)
    report_notices = []
    if history < context.settings.min_months_for_trends:
        report_notices.append(ReportError.NOT_ENOUGH_HISTORY_FOR_TRENDS)
    if history < context.settings.min_months_for_projection:
        report_notices.append(ReportError.NOT_ENOUGH_HISTORY_FOR_PROJECTION)
    return _rounded(FinanceReportSchema(months = month_reports, years = year_reports,
                                        year_to_date = _year_to_date(months, context),
                                        notices = report_notices), context.settings)


def _rounded(
    report: FinanceReportSchema,
    settings: ReportSettings
) -> FinanceReportSchema:
    '''
        The report as it is published: amounts and ratios rounded once, at
        the end, with the decimals PARAMETERS holds. The calculation itself
        never rounds, so no error piles up from one line to the next.

        Args:
            report (FinanceReportSchema): The report, unrounded.
            settings (ReportSettings): The decimals to publish with.

        Returns:
            FinanceReportSchema: The same report, rounded.
    '''
    for period in _published(report):
        lines = [line for _, line in period.income_statement if line is not None]
        lines += [line for _, line in period.taxes]
        for line in lines:
            line.amount = _round(line.amount, settings.amount_decimals)
        for name, value in period.balance:
            setattr(period.balance, name, _round(value, settings.amount_decimals))
        for name, value in period.indicators:
            setattr(period.indicators, name, _round(value, settings.ratio_decimals))
    return report


def _published(report: FinanceReportSchema) -> list[PeriodReportSchema]:
    '''
        Every period the report carries: its months, its years and the
        same months of the year before, when there are.

        Args:
            report (FinanceReportSchema): The report.

        Returns:
            list[PeriodReportSchema]: The periods.
    '''
    previous = report.year_to_date.previous if report.year_to_date else None
    return report.months + report.years + ([previous] if previous else [])


def report_settings(auth_token: str | None) -> ReportSettings:
    '''
        The report's business values, read from PARAMETERS with the caller's
        token. A missing one stops the report: there is no default in the code.

        Args:
            auth_token (str | None): The caller's Authorization header.

        Returns:
            ReportSettings: The values.
    '''
    return settings_from(
        required_parameters(read_parameters(FINANCE_SCOPE, auth_token), FINANCE_CODES),
        required_parameters(read_parameters(GLOBAL_SCOPE, auth_token), GLOBAL_CODES)
    )


def finance_report(
    dynamodb_resource: ServiceResource,
    client: str,
    auth_token: str | None
) -> FinanceReportSchema:
    '''
        The report of a client, read from its amounts and the parameters.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            auth_token (str | None): The caller's Authorization header, for PARAMETERS.

        Returns:
            FinanceReportSchema: The report.
    '''
    settings = report_settings(auth_token)
    context = Context(
        catalog = catalog_by_code(dynamodb_resource),
        rates = law_rates(dynamodb_resource),
        provision_rate = client_value(dynamodb_resource, client, settings.iue_provision_code),
        settings = settings
    )
    report = build_report(list_entries(dynamodb_resource, client).entries, context)
    rates, notices = period_rates([p.period for p in report.months + report.years],
                                  local_now().date(), auth_token)
    for period in report.months + report.years:
        period.exchange = rates.get(period.period)
    if report.year_to_date and report.year_to_date.previous:
        # The same months of the year before close on their last month.
        cut = f'{report.year_to_date.previous.period}-{report.year_to_date.through[5:]}'
        report.year_to_date.previous.exchange = rates.get(cut)
    report.notices += notices
    return report
