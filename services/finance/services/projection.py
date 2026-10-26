'''
    The projection: how the next months may go in three scenarios, and until
    when the cash lasts in each.

    The realistic scenario is a damped trend (Holt) over the net sales and
    over the outflow, each on its own, asked to ML_FUNCTIONS: the base service
    of calculations every service asks instead of keeping its own copy of the
    formulas (Rafael, 17-oct). The worst and the best
    move the realistic one by the percentages the manager types, starting from
    the defaults in `finance_parameters` (Rafael, 17-oct).

    The cash is an approximation, as realistic as the loaded figures allow
    (Rafael, 17-oct; not an accounting system):
    - each month adds its profit, and gives back the depreciation, an expense
      that never leaves the cash;
    - the IUE provision moves from the cash to a reserve, and in the payment
      month the IUE of the year before is paid from that reserve; only what
      the reserve does not cover comes out of the cash, and what is left over
      returns to it (Rafael, 12-oct: «si queda saldo, pasa a ser parte de la
      utilidad»). Without a provision, the whole payment comes out of the cash.
'''
from dataclasses import dataclass
from datetime import date as date_type
from typing import Any

import requests
from boto3.resources.base import ServiceResource

from schemas.entries import EntrySchema, Periodicity
from schemas.projection import (
    ExchangeTodaySchema,
    ModelSchema,
    ProjectedMonthSchema,
    ProjectionError,
    ProjectionSchema,
    ScenarioInputSchema,
    ScenarioName,
    ScenarioSchema
)
from schemas.report import PeriodReportSchema
from services.entries import list_entries, local_now
from services.exceptions import InvalidInputError, ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.finance import catalog_by_code
from services.parameters import client_value, law_rates, rate_on
from services.rates import period_rates
from services.report import (
    FINANCE_CODES,
    Context,
    build_report,
    finance_parameters,
    report_settings
)
from services.utils import API_URL, REQUEST_TIMEOUT_SECONDS

PROJECTION_CODES = (
    'PROJECTION_HORIZON', 'PROJECTION_MAX_HORIZON', 'WORST_SALES_CHANGE', 'WORST_OUTFLOW_CHANGE',
    'BEST_SALES_CHANGE', 'BEST_OUTFLOW_CHANGE', 'MAX_SCENARIO_CHANGE', 'BACKTEST_MONTHS',
    'NON_CASH_ACCOUNTS', 'IUE_PAYMENT_MONTH',
)
# The series are monthly, so a season is a year: a unit, not a business value.
MONTHS_PER_YEAR = 12


@dataclass(frozen = True)
class ProjectionSettings:  # pylint: disable=too-many-instance-attributes
    '''
        The business values of the projection, as `finance_parameters` holds them.
    '''
    horizon: int
    max_horizon: int
    worst: ScenarioInputSchema
    best: ScenarioInputSchema
    max_change: float
    backtest_months: int
    non_cash_accounts: tuple[str, ...]
    iue_payment_month: int


def projection_settings_from(finance: dict[str, Any]) -> ProjectionSettings:
    '''
        The projection's values, from `finance_parameters`.

        Args:
            finance (dict[str, Any]): The values read from the table.

        Returns:
            ProjectionSettings: The values.
    '''
    return ProjectionSettings(
        horizon = int(finance['PROJECTION_HORIZON']),
        max_horizon = int(finance['PROJECTION_MAX_HORIZON']),
        worst = ScenarioInputSchema(sales_change = finance['WORST_SALES_CHANGE'],
                                    outflow_change = finance['WORST_OUTFLOW_CHANGE']),
        best = ScenarioInputSchema(sales_change = finance['BEST_SALES_CHANGE'],
                                   outflow_change = finance['BEST_OUTFLOW_CHANGE']),
        max_change = float(finance['MAX_SCENARIO_CHANGE']),
        backtest_months = int(finance['BACKTEST_MONTHS']),
        non_cash_accounts = tuple(finance['NON_CASH_ACCOUNTS']),
        iue_payment_month = int(finance['IUE_PAYMENT_MONTH'])
    )


@dataclass(frozen = True)
class History:
    '''
        What the projection reads from the months the client loaded.
    '''
    months: list[PeriodReportSchema]
    non_cash: dict[str, float]
    invoiced_sales: dict[str, float]


@dataclass(frozen = True)
class Forecasts:
    '''
        What ML_FUNCTIONS answered: the realistic net sales and outflow, and
        how good the model was on the client's own net sales.
    '''
    sales: list[float]
    outflow: list[float]
    model: str
    error_percent: float | None
    naive_error_percent: float | None
    tested_points: int


@dataclass(frozen = True)
class Taxes:
    '''
        What the IUE of the projection needs: the law rates, the IUE code and
        the client's provision (None while it has not set one).
    '''
    rates: dict[str, list[tuple[str, float]]]
    iue_code: str
    provision_rate: float | None


def _next_months(
    last: str,
    horizon: int
) -> list[str]:
    '''
        The months after `last`.

        Args:
            last (str): YYYY-MM.
            horizon (int): How many.

        Returns:
            list[str]: YYYY-MM keys.
    '''
    year, month = int(last[:4]), int(last[5:7])
    keys = []
    for _ in range(horizon):
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        keys.append(f'{year:04d}-{month:02d}')
    return keys


def _ratio(
    part: dict[str, float],
    whole: dict[str, float],
    keys: list[str]
) -> float:
    '''
        The share `part` had of `whole` over the given months; 0 without a whole.

        Args:
            part (dict[str, float]): By month.
            whole (dict[str, float]): By month.
            keys (list[str]): The months to take.

        Returns:
            float: The share.
    '''
    total = sum(whole.get(key, 0) for key in keys)
    return sum(part.get(key, 0) for key in keys) / total if total else 0.0


@dataclass
class _Ledger:
    '''
        The cash outside the reserve, the IUE reserve by year it provisions,
        and the profit of each year, while the months run.
    '''
    cash: float
    reserves: dict[int, float]
    profits: dict[int, float]


def _pay_income_tax(
    ledger: _Ledger,
    year: int,
    taxes: Taxes
) -> float:
    '''
        Pays the IUE of `year`: from its reserve first, the rest from the cash;
        what the reserve has left over returns to the cash.

        Args:
            ledger (_Ledger): The running cash, reserves and profits.
            year (int): The year whose IUE is paid.
            taxes (Taxes): The law rates and the IUE code.

        Returns:
            float: The IUE paid.
    '''
    profit = ledger.profits.get(year)
    if profit is None:
        return 0.0
    due = max(profit, 0) * rate_on(taxes.rates, taxes.iue_code, date_type(year, 12, 31))
    reserve = ledger.reserves.pop(year, 0.0)
    ledger.cash += reserve - due
    return due


@dataclass(frozen = True)
class _Base:
    '''
        The realistic projection every scenario starts from.
    '''
    keys: list[str]
    sales: list[float]
    outflow: list[float]
    non_cash_ratio: float
    invoiced_ratio: float
    ledger: _Ledger


def _month(
    ledger: _Ledger,
    point: tuple[str, float, float],
    base: _Base,
    settings: ProjectionSettings,
    taxes: Taxes
) -> ProjectedMonthSchema:
    '''
        One projected month: its profit and depreciation into the cash, its
        provision into the reserve, and in the payment month the IUE of the
        year before.

        Args:
            ledger (_Ledger): The running cash, reserves and profits, updated in place.
            point (tuple[str, float, float]): The month, its sales and its outflow.
            base (_Base): The ratios of the client.
            settings (ProjectionSettings): The business values.
            taxes (Taxes): The law rates, the IUE code and the provision.

        Returns:
            ProjectedMonthSchema: The month.
    '''
    key, sales, outflow = point
    year = int(key[:4])
    profit = sales - outflow
    non_cash = outflow * base.non_cash_ratio
    provision = (sales * base.invoiced_ratio * taxes.provision_rate / 100
                 if taxes.provision_rate is not None else 0.0)
    ledger.cash += profit + non_cash - provision
    ledger.reserves[year] = ledger.reserves.get(year, 0.0) + provision
    ledger.profits[year] = ledger.profits.get(year, 0.0) + profit
    paid = (_pay_income_tax(ledger, year - 1, taxes)
            if int(key[5:7]) == settings.iue_payment_month else 0.0)
    return ProjectedMonthSchema(
        period = key, net_sales = sales, outflow = outflow, profit = profit,
        non_cash = non_cash, provision = provision, income_tax_paid = paid,
        reserve = sum(ledger.reserves.values()), cash = ledger.cash
    )


def _scenario(
    name: ScenarioName,
    change: ScenarioInputSchema,
    base: _Base,
    settings: ProjectionSettings,
    taxes: Taxes
) -> ScenarioSchema:
    '''
        One scenario, month by month, and the first month its cash goes
        below zero.

        Args:
            name (ScenarioName): Which one.
            change (ScenarioInputSchema): Its percentages.
            base (_Base): The realistic projection and the client's ratios.
            settings (ProjectionSettings): The business values.
            taxes (Taxes): The law rates, the IUE code and the provision.

        Returns:
            ScenarioSchema: The scenario.
    '''
    start = base.ledger
    ledger = _Ledger(start.cash, dict(start.reserves), dict(start.profits))
    months = [
        _month(ledger, (key, sales * (1 + change.sales_change / 100),
                        outflow * (1 + change.outflow_change / 100)), base, settings, taxes)
        for key, sales, outflow in zip(base.keys, base.sales, base.outflow)
    ]
    runs_out = next((month.period for month in months if month.cash < 0), None)
    return ScenarioSchema(name = name, sales_change = change.sales_change,
                          outflow_change = change.outflow_change, months = months,
                          cash_runs_out = runs_out)


def _starting_ledger(
    history: History,
    settings: ProjectionSettings
) -> _Ledger:
    '''
        The ledger at the close of the last loaded month: the reserve of each
        year still unpaid, the profit of each year, and the cash outside the
        reserve.

        Args:
            history (History): The loaded months.
            settings (ProjectionSettings): The business values.

        Returns:
            _Ledger: The starting point.
    '''
    reserves: dict[int, float] = {}
    profits: dict[int, float] = {}
    for month in history.months:
        year, number = int(month.period[:4]), int(month.period[5:7])
        provision = month.taxes.income_tax_provision.amount or 0.0
        reserves[year] = reserves.get(year, 0.0) + provision
        profits[year] = profits.get(year, 0.0) + (
            month.income_statement.profit_before_income_tax.amount or 0.0)
        if number == settings.iue_payment_month:
            # The year before was settled this month: its reserve is spent.
            reserves.pop(year - 1, None)
    cash = history.months[-1].balance.cash or 0.0
    return _Ledger(cash - sum(reserves.values()), reserves, profits)


def series_of(history: History) -> tuple[list[float], list[float]]:
    '''
        The two series the realistic scenario projects: net sales and outflow
        (cost of sales, operating expenses and the financial result).

        Args:
            history (History): The loaded months.

        Returns:
            tuple[list[float], list[float]]: Net sales and outflow, oldest first.
    '''
    sales = [month.income_statement.net_sales.amount or 0.0 for month in history.months]
    outflow = [s - (month.income_statement.profit_before_income_tax.amount or 0.0)
               for s, month in zip(sales, history.months)]
    return sales, outflow


def _base(
    history: History,
    settings: ProjectionSettings,
    forecasts: Forecasts
) -> _Base:
    '''
        The realistic projection, with the shares of depreciation and invoiced
        sales of the last twelve months.

        Args:
            history (History): The loaded months.
            settings (ProjectionSettings): The business values.
            forecasts (Forecasts): What ML_FUNCTIONS projected.

        Returns:
            _Base: The base every scenario moves.
    '''
    keys = [month.period for month in history.months]
    sales, outflow = series_of(history)
    recent = keys[-12:]
    return _Base(
        keys = _next_months(keys[-1], len(forecasts.sales)),
        sales = forecasts.sales, outflow = forecasts.outflow,
        non_cash_ratio = _ratio(history.non_cash, dict(zip(keys, outflow)), recent),
        invoiced_ratio = _ratio(history.invoiced_sales, dict(zip(keys, sales)), recent),
        ledger = _starting_ledger(history, settings)
    )


def build_projection(
    history: History,
    settings: ProjectionSettings,
    taxes: Taxes,
    request: tuple[int, ScenarioInputSchema, ScenarioInputSchema],
    forecasts: Forecasts
) -> ProjectionSchema:
    '''
        The projection of a client. Pure: everything it reads arrives here,
        the realistic series already projected by ML_FUNCTIONS.

        Args:
            history (History): The loaded months, their depreciation and
                their invoiced sales.
            settings (ProjectionSettings): The business values.
            taxes (Taxes): The law rates, the IUE code and the provision.
            request (tuple[int, ScenarioInputSchema, ScenarioInputSchema]):
                The horizon and the worst and best changes, already validated.
            forecasts (Forecasts): The realistic net sales and outflow.

        Returns:
            ProjectionSchema: The three scenarios.
    '''
    horizon, worst, best = request
    base = _base(history, settings, forecasts)
    last = history.months[-1]
    notices = [] if last.balance.cash is not None else [ProjectionError.NO_CASH_LOADED]
    if taxes.provision_rate is None:
        notices.append(ProjectionError.IUE_PROVISION_NOT_SET)
    return ProjectionSchema(
        horizon = horizon, last_period = last.period, base_cash = last.balance.cash,
        scenarios = [_scenario(name, change, base, settings, taxes) for name, change in (
            (ScenarioName.WORST, worst),
            (ScenarioName.REALISTIC, ScenarioInputSchema(sales_change = 0, outflow_change = 0)),
            (ScenarioName.BEST, best))],
        model = ModelSchema(name = forecasts.model, error_percent = forecasts.error_percent,
                            naive_error_percent = forecasts.naive_error_percent,
                            tested_points = forecasts.tested_points),
        exchange = None, notices = notices
    )


def _forecast(
    values: list[float],
    horizon: int,
    settings: ProjectionSettings,
    auth_token: str | None
) -> dict[str, Any]:
    '''
        Asks ML_FUNCTIONS to project one series, with the caller's token.

        Args:
            values (list[float]): The history, oldest first.
            horizon (int): Months ahead.
            settings (ProjectionSettings): How many months to test the models on.
            auth_token (str | None): The caller's Authorization header.

        Returns:
            dict[str, Any]: The forecast and its errors.

        Raises:
            ServiceUnavailableError: FORECAST_UNAVAILABLE.
    '''
    # ML_FUNCTIONS chooses the model and fits it to the series (19-oct-2026):
    # FINANCE only says the series is monthly.
    body = {'values': values, 'horizon': horizon, 'season_length': MONTHS_PER_YEAR,
            'backtest_points': settings.backtest_months}
    try:
        response = requests.post(f'{API_URL}/v1/prediction/forecast', json = body,
                                 headers = {'Authorization': auth_token or ''},
                                 timeout = REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as error:
        error_msg = f'Network error asking ML_FUNCTIONS for a forecast: {error}'
        logger.error(error_msg)
        raise ServiceUnavailableError(
            detail = ProjectionError.FORECAST_UNAVAILABLE.value) from error
    if not response.ok:
        error_msg = (f'ML_FUNCTIONS refused the forecast: status={response.status_code} '
                     f'body={response.text[:200]}')
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = ProjectionError.FORECAST_UNAVAILABLE.value)
    return response.json()


def forecasts_for(
    history: History,
    horizon: int,
    settings: ProjectionSettings,
    auth_token: str | None
) -> Forecasts:
    '''
        The realistic net sales and outflow, projected by ML_FUNCTIONS.

        Args:
            history (History): The loaded months.
            horizon (int): Months ahead.
            settings (ProjectionSettings): How many months to test the models on.
            auth_token (str | None): The caller's Authorization header.

        Returns:
            Forecasts: Both series and the error measured on the net sales.
    '''
    sales, outflow = series_of(history)
    sales_answer = _forecast(sales, horizon, settings, auth_token)
    outflow_answer = _forecast(outflow, horizon, settings, auth_token)
    return Forecasts(sales = sales_answer['forecast'], outflow = outflow_answer['forecast'],
                     model = sales_answer['model'],
                     error_percent = sales_answer.get('error_percent'),
                     naive_error_percent = sales_answer.get('naive_error_percent'),
                     tested_points = sales_answer.get('tested_points', 0))


def monthly_sums(
    entries: list[EntrySchema],
    catalog: dict[str, dict],
    accounts: tuple[tuple[str, ...], str]
) -> tuple[dict[str, float], dict[str, float]]:
    '''
        By month, the depreciation (non-cash accounts) and the invoiced sales,
        from the loaded amounts. A year loaded whole has no months.

        Args:
            entries (list[EntrySchema]): Every amount of the client.
            catalog (dict[str, dict]): The accounts, by code.
            accounts (tuple[tuple[str, ...], str]): The non-cash accounts and
                the sales group.

        Returns:
            tuple[dict[str, float], dict[str, float]]: Non-cash and invoiced sales.
    '''
    non_cash_accounts, sales_group = accounts
    non_cash: dict[str, float] = {}
    invoiced: dict[str, float] = {}
    for entry in entries:
        if entry.periodicity is Periodicity.ANNUAL:
            continue
        key = entry.date[:7]
        if entry.account_code in non_cash_accounts:
            non_cash[key] = non_cash.get(key, 0.0) + entry.amount
        account = catalog.get(entry.account_code, {})
        if account.get('invoiced') is True and entry.account_code.startswith(f'{sales_group}.'):
            invoiced[key] = invoiced.get(key, 0.0) + entry.amount
    return non_cash, invoiced


@dataclass(frozen = True)
class ProjectionRequest:
    '''
        What the manager typed on the screen; None keeps the default.
    '''
    horizon: int | None = None
    worst: ScenarioInputSchema | None = None
    best: ScenarioInputSchema | None = None


def validated_request(
    asked: ProjectionRequest,
    settings: ProjectionSettings
) -> tuple[int, ScenarioInputSchema, ScenarioInputSchema]:
    '''
        The horizon and the scenario changes to use: what the manager typed,
        within the ranges `finance_parameters` holds, or the defaults.

        Args:
            asked (ProjectionRequest): What the screen sent.
            settings (ProjectionSettings): The defaults and the ranges.

        Returns:
            tuple[int, ScenarioInputSchema, ScenarioInputSchema]: Horizon, worst, best.

        Raises:
            InvalidInputError: HORIZON_OUT_OF_RANGE or CHANGE_OUT_OF_RANGE.
    '''
    horizon = settings.horizon if asked.horizon is None else asked.horizon
    if not 1 <= horizon <= settings.max_horizon:
        raise InvalidInputError(detail = ProjectionError.HORIZON_OUT_OF_RANGE.value)
    worst, best = asked.worst or settings.worst, asked.best or settings.best
    for change in (worst, best):
        if max(abs(change.sales_change), abs(change.outflow_change)) > settings.max_change:
            raise InvalidInputError(detail = ProjectionError.CHANGE_OUT_OF_RANGE.value)
    return horizon, worst, best


def _rounded(
    projection: ProjectionSchema,
    decimals: int
) -> ProjectionSchema:
    '''
        The projection as it is published: every amount rounded once, at the end.

        Args:
            projection (ProjectionSchema): Unrounded.
            decimals (int): Decimals of an amount, from `finance_parameters`.

        Returns:
            ProjectionSchema: The same projection, rounded.
    '''
    for scenario in projection.scenarios:
        for month in scenario.months:
            for name, value in month:
                if isinstance(value, float):
                    setattr(month, name, round(value, decimals))
    if projection.model is not None:
        for name in ('error_percent', 'naive_error_percent'):
            value = getattr(projection.model, name)
            setattr(projection.model, name, None if value is None else round(value, 1))
    return projection


def finance_projection(
    dynamodb_resource: ServiceResource,
    client: str,
    auth_token: str | None,
    asked: ProjectionRequest
) -> ProjectionSchema:
    '''
        The projection of a client, read from its amounts and the parameters.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.
            auth_token (str | None): The caller's token, for QUOTES.
            asked (ProjectionRequest): What the manager typed.

        Returns:
            ProjectionSchema: The three scenarios, or why there are none.
    '''
    settings = projection_settings_from(finance_parameters(FINANCE_CODES + PROJECTION_CODES))
    request = validated_request(asked, settings)
    report_values = report_settings()
    context = Context(catalog_by_code(dynamodb_resource), law_rates(dynamodb_resource),
                      client_value(dynamodb_resource, client, report_values.iue_provision_code),
                      report_values)
    entries = list_entries(dynamodb_resource, client).entries
    report = build_report(entries, context)
    if len(report.months) < context.settings.min_months_for_projection:
        return ProjectionSchema(horizon = request[0], last_period = None, base_cash = None,
                                scenarios = [], model = None, exchange = None, notices = [
                                    ProjectionError.NOT_ENOUGH_HISTORY_FOR_PROJECTION])
    non_cash, invoiced = monthly_sums(entries, context.catalog, (
        settings.non_cash_accounts, context.settings.sales_group))
    history = History(report.months, non_cash, invoiced)
    projection = build_projection(
        history, settings,
        Taxes(context.rates, context.settings.iue_code, context.provision_rate), request,
        forecasts_for(history, request[0], settings, auth_token))
    _attach_today_rates(projection, auth_token)
    return _rounded(projection, context.settings.amount_decimals)


def _attach_today_rates(
    projection: ProjectionSchema,
    auth_token: str | None
) -> None:
    '''
        A future month has no rate yet: the projection is read at today's.

        Args:
            projection (ProjectionSchema): Completed in place.
            auth_token (str | None): The caller's token, for QUOTES.
    '''
    today = local_now().date()
    found, _ = period_rates([today.strftime('%Y-%m')], today, auth_token)
    current = found.get(today.strftime('%Y-%m'))
    if current is not None:
        projection.exchange = ExchangeTodaySchema(date = current.date, usd = current.usd,
                                                  usdt = current.usdt)
