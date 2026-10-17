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
from dataclasses import dataclass, field
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
    ReportError
)
from services.entries import list_entries
from services.environment import load_and_validate_env_vars
from services.finance import catalog_by_code
from services.parameters import client_value, law_rates, rate_on

ENV_VARS = load_and_validate_env_vars({
    'REPORT_SALES_GROUP': str,
    'REPORT_FINANCIAL_EXPENSE_GROUP': str,
    'REPORT_IT_ACCOUNT': str,
    'REPORT_CASH_ACCOUNTS': str,
    'REPORT_CURRENT_ASSETS_GROUP': str,
    'REPORT_CURRENT_LIABILITIES_GROUP': str,
    'LAW_VAT_CODE': str,
    'LAW_TRANSACTIONS_TAX_CODE': str,
    'LAW_INCOME_TAX_CODE': str,
    'INCOME_TAX_PROVISION_CODE': str,
    'COVERAGE_MONTHS': int,
    'MIN_MONTHS_FOR_TRENDS': int,
    'MIN_MONTHS_FOR_PROJECTION': int,
    'REPORT_AMOUNT_DECIMALS': int,
    'REPORT_RATIO_DECIMALS': int,
    'BALANCE_TOLERANCE': float,
})
SALES_GROUP = ENV_VARS['REPORT_SALES_GROUP']
FINANCIAL_EXPENSE_GROUP = ENV_VARS['REPORT_FINANCIAL_EXPENSE_GROUP']
IT_ACCOUNT = ENV_VARS['REPORT_IT_ACCOUNT']
# A list in the .env is joined with hyphens: a comma would break the deploy.
CASH_ACCOUNTS = tuple(ENV_VARS['REPORT_CASH_ACCOUNTS'].split('-'))
CURRENT_ASSETS_GROUP = ENV_VARS['REPORT_CURRENT_ASSETS_GROUP']
CURRENT_LIABILITIES_GROUP = ENV_VARS['REPORT_CURRENT_LIABILITIES_GROUP']
VAT_CODE = ENV_VARS['LAW_VAT_CODE']
IT_CODE = ENV_VARS['LAW_TRANSACTIONS_TAX_CODE']
IUE_CODE = ENV_VARS['LAW_INCOME_TAX_CODE']
IUE_PROVISION_CODE = ENV_VARS['INCOME_TAX_PROVISION_CODE']
COVERAGE_MONTHS = ENV_VARS['COVERAGE_MONTHS']
MIN_MONTHS_FOR_TRENDS = ENV_VARS['MIN_MONTHS_FOR_TRENDS']
MIN_MONTHS_FOR_PROJECTION = ENV_VARS['MIN_MONTHS_FOR_PROJECTION']
AMOUNT_DECIMALS = ENV_VARS['REPORT_AMOUNT_DECIMALS']
RATIO_DECIMALS = ENV_VARS['REPORT_RATIO_DECIMALS']
BALANCE_TOLERANCE = ENV_VARS['BALANCE_TOLERANCE']

# Account types that are a picture at a date, and those that move in a period.
_BALANCE_TYPES = (AccountType.ASSET.value, AccountType.LIABILITY.value, AccountType.EQUITY.value)


@dataclass
class Period:
    '''
        The amounts of one month or one year, split into what moved during
        it and the balances at its end.
    '''
    key: str
    origin: Periodicity
    flows: list[EntrySchema] = field(default_factory = list)
    balances: list[EntrySchema] = field(default_factory = list)
    months: int = 1


@dataclass(frozen = True)
class Context:
    '''
        What the calculation reads besides the amounts.
    '''
    catalog: dict[str, dict]
    rates: dict[str, list[tuple[str, float]]]
    provision_rate: float | None


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
    decimals: int = AMOUNT_DECIMALS
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
    return LineSchema(amount = _round(value), origin = origin)


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


def _split_periods(entries: list[EntrySchema]) -> tuple[dict[str, Period], dict[str, Period]]:
    '''
        The months and the years the client has. A month with days takes the
        sum of its days for what moved and the last loaded day for its
        balances; a year loaded as such is used whole, and any other year is
        built from its months — never split into invented ones.

        Args:
            entries (list[EntrySchema]): Every amount of the client.

        Returns:
            tuple[dict[str, Period], dict[str, Period]]: Months and years.
    '''
    months: dict[str, Period] = {}
    years: dict[str, Period] = {}
    last_day: dict[str, str] = {}
    for entry in entries:
        if entry.periodicity is Periodicity.ANNUAL:
            target = years.setdefault(entry.date, Period(entry.date, Periodicity.ANNUAL,
                                                         months = 12))
        else:
            key = entry.date[:7]
            target = months.setdefault(key, Period(key, entry.periodicity))
        (target.balances if _is_balance(entry) else target.flows).append(entry)
        if entry.periodicity is Periodicity.DAILY and _is_balance(entry):
            last_day[entry.date[:7]] = max(last_day.get(entry.date[:7], ''), entry.date)
    for key, day in last_day.items():
        months[key].balances = [e for e in months[key].balances if e.date == day]
    for key in sorted(months):
        year = years.get(key[:4])
        if year is not None and year.origin is Periodicity.ANNUAL:
            continue
        if year is None:
            year = years[key[:4]] = Period(key[:4], Periodicity.MONTHLY, months = 0)
        year.flows += months[key].flows
        year.months += 1
        if months[key].balances:
            year.balances = months[key].balances
    return months, years


def _is_balance(entry: EntrySchema) -> bool:
    '''
        Whether an amount is a balance (types 1 to 3): its code says it.

        Args:
            entry (EntrySchema): The amount.

        Returns:
            bool: True for assets, liabilities and equity.
    '''
    return entry.account_code[0] in _BALANCE_TYPES


def _transactions_tax(
    period: Period,
    sums: _Sums,
    rate: float
) -> tuple[float | None, FigureOrigin, list[ReportError]]:
    '''
        The IT of the period, paid every month: the one loaded in its account
        (processed load), or 3 % of the gross invoiced sales (base load).

        Args:
            period (Period): The period.
            sums (_Sums): Its amounts.
            rate (float): The IT rate in force.

        Returns:
            tuple: The amount, its origin and the notices it raises.
    '''
    if any(e.account_code == IT_ACCOUNT for e in period.flows):
        return sums.total(lambda e, a: e.account_code == IT_ACCOUNT), FigureOrigin.LOADED, []
    gross_invoiced = sums.total(
        lambda e, a: a.get('invoiced') is True and _in_group(e.account_code, SALES_GROUP)
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
    rate: float
) -> tuple[float, float]:
    '''
        The IVA of a period: the debit inside the invoiced gross sales and
        the credit inside the invoiced gross purchases.

        Args:
            sums (_Sums): The amounts of the period.
            rate (float): The IVA rate in force.

        Returns:
            tuple[float, float]: Debit and credit.
    '''
    debit = sums.total(lambda e, a: _in_group(e.account_code, SALES_GROUP) and _taxed(a, e))
    credit = sums.total(lambda e, a: _is_type(e, AccountType.COST) and _taxed(a, e))
    return debit * rate, credit * rate


def _statement(
    sums: _Sums,
    vat: tuple[float, float],
    transactions_tax: tuple[float | None, FigureOrigin]
) -> IncomeStatementSchema:
    '''
        The income statement of a period, as Rafael approved it on 16-oct.

        Args:
            sums (_Sums): The amounts of the period.
            vat (tuple[float, float]): IVA debit and credit.
            transactions_tax (tuple[float | None, FigureOrigin]): The IT and its origin.

        Returns:
            IncomeStatementSchema: The statement.
    '''
    vat_debit, vat_credit = vat
    it_amount, it_origin = transactions_tax
    sales = sums.total(lambda e, a: _in_group(e.account_code, SALES_GROUP))
    net_sales = sales - vat_debit - (it_amount or 0)
    gross = net_sales - (sums.total(lambda e, a: _is_type(e, AccountType.COST)) - vat_credit)
    operating = sums.total(lambda e, a: _is_type(e, AccountType.EXPENSE)
                           and not _in_group(e.account_code, FINANCIAL_EXPENSE_GROUP)
                           and e.account_code != IT_ACCOUNT)
    financial = (sums.total(lambda e, a: _is_type(e, AccountType.INCOME)
                            and not _in_group(e.account_code, SALES_GROUP))
                 - sums.total(lambda e, a: _in_group(e.account_code, FINANCIAL_EXPENSE_GROUP)))
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
    rate: float | None
) -> float | None:
    '''
        The IUE provision: the share of everything invoiced the client chose
        to set aside. None while it has not chosen one — the suggestion is
        never applied on its own (Rafael, 16-oct).

        Args:
            sums (_Sums): The amounts of the period.
            rate (float | None): The client's percentage.

        Returns:
            float | None: The reserve.
    '''
    if rate is None:
        return None
    invoiced = sums.total(lambda e, a: a.get('invoiced') is True
                          and _in_group(e.account_code, SALES_GROUP))
    return invoiced * rate / 100


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
    vat_debit, vat_credit = _vat(sums, rate_on(context.rates, VAT_CODE, day))
    it_amount, it_origin, notices = _transactions_tax(
        period, sums, rate_on(context.rates, IT_CODE, day))
    statement = _statement(sums, (vat_debit, vat_credit), (it_amount, it_origin))
    if len(period.key) == 4:
        # The IUE is paid on the year: only an annual report estimates it.
        before_tax = statement.profit_before_income_tax.amount
        estimated = max(before_tax, 0) * rate_on(context.rates, IUE_CODE, day)
        statement.income_tax_estimated = _line(estimated)
        statement.net_profit_estimated = _line(before_tax - estimated)

    provision = _provision(sums, context.provision_rate)
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
    catalog: dict[str, dict]
) -> tuple[BalanceSheetSchema, list[ReportError]]:
    '''
        The balances at the end of the period, with what the client loaded.

        Args:
            period (Period): The period.
            catalog (dict[str, dict]): The accounts, by code.

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
        assets = _round(assets),
        current_assets = _round(sums.total(lambda e, a: _in_group(e.account_code,
                                                                  CURRENT_ASSETS_GROUP))),
        cash = _round(sums.total(lambda e, a: e.account_code in CASH_ACCOUNTS)),
        liabilities = _round(liabilities),
        current_liabilities = _round(sums.total(lambda e, a: _in_group(
            e.account_code, CURRENT_LIABILITIES_GROUP))),
        equity = _round(equity), difference = _round(difference)
    )
    # A balance that does not square is said, never corrected (Rafael, 15-oct).
    return sheet, [ReportError.BALANCE_MISMATCH] if abs(difference) > BALANCE_TOLERANCE else []


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
            float | None: The ratio, rounded.
    '''
    if numerator is None or not denominator:
        return None
    return round(numerator / denominator, RATIO_DECIMALS)


def indicators(
    sheet: BalanceSheetSchema,
    monthly_outflow: float | None
) -> IndicatorsSchema:
    '''
        The ratios of a period.

        Args:
            sheet (BalanceSheetSchema): Its balance.
            monthly_outflow (float | None): Average monthly outflow behind it.

        Returns:
            IndicatorsSchema: Liquidity, debt, solvency and months of coverage.
    '''
    return IndicatorsSchema(
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
    sheet, sheet_notices = balance_sheet(period, context.catalog)
    return PeriodReportSchema(
        period = period.key, origin = period.origin.value, income_statement = statement,
        taxes = taxes, balance = sheet, indicators = indicators(sheet, monthly_outflow(outflow)),
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
    months, years = _split_periods(entries)
    outflows: dict[str, float] = {}
    month_reports = []
    for key in sorted(months):
        def recent_average(
            outflow: float,
            key: str = key
        ) -> float:
            outflows[key] = outflow
            recent = [outflows[k] for k in sorted(outflows)[-COVERAGE_MONTHS:]]
            return sum(recent) / len(recent)
        month_reports.append(_period_report(months[key], context, recent_average))
    year_reports = [
        _period_report(years[key], context,
                       lambda outflow, months_in = years[key].months: outflow / max(months_in, 1))
        for key in sorted(years)
    ]
    history = len(months)
    report_notices = []
    if history < MIN_MONTHS_FOR_TRENDS:
        report_notices.append(ReportError.NOT_ENOUGH_HISTORY_FOR_TRENDS)
    if history < MIN_MONTHS_FOR_PROJECTION:
        report_notices.append(ReportError.NOT_ENOUGH_HISTORY_FOR_PROJECTION)
    return FinanceReportSchema(months = month_reports, years = year_reports,
                               notices = report_notices)


def finance_report(
    dynamodb_resource: ServiceResource,
    client: str
) -> FinanceReportSchema:
    '''
        The report of a client, read from its amounts and the parameters.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.

        Returns:
            FinanceReportSchema: The report.
    '''
    context = Context(
        catalog = catalog_by_code(dynamodb_resource),
        rates = law_rates(dynamodb_resource),
        provision_rate = client_value(dynamodb_resource, client, IUE_PROVISION_CODE)
    )
    return build_report(list_entries(dynamodb_resource, client).entries, context)
