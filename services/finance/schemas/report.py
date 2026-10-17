'''
    Pydantic V2 DTOs for what the financial analysis calculates: the income
    statement, the taxes of the period, the balance sheet and the indicators.

    Nothing here is stored. Every figure is computed when the report is asked
    for, from the amounts loaded and the rates in force in each period, so a
    corrected figure or a new law rate never leaves a stale report behind.
    Each line says whether it was loaded or calculated (Rafael).
'''
from enum import Enum
from pydantic import BaseModel, Field


class ReportError(str, Enum):
    '''
        Why a figure, or a whole report, could not be given.
    '''
    PARAMETER_NOT_FOUND = 'PARAMETER_NOT_FOUND'
    NO_RATE_FOR_DATE = 'NO_RATE_FOR_DATE'
    IUE_PROVISION_NOT_SET = 'IUE_PROVISION_NOT_SET'
    IT_NOT_LOADED = 'IT_NOT_LOADED'
    NO_BALANCE = 'NO_BALANCE'
    BALANCE_MISMATCH = 'BALANCE_MISMATCH'
    NOT_ENOUGH_HISTORY_FOR_TRENDS = 'NOT_ENOUGH_HISTORY_FOR_TRENDS'
    NOT_ENOUGH_HISTORY_FOR_PROJECTION = 'NOT_ENOUGH_HISTORY_FOR_PROJECTION'


class FigureOrigin(str, Enum):
    '''
        Where a figure comes from: typed by the client, or computed here.
    '''
    LOADED = 'LOADED'
    CALCULATED = 'CALCULATED'


class LineSchema(BaseModel):
    '''
        One line of a report.
    '''
    amount: float | None
    origin: FigureOrigin


class IncomeStatementSchema(BaseModel):
    '''
        The income statement, as approved by Rafael on 16-oct.
    '''
    sales: LineSchema
    sales_vat: LineSchema
    transactions_tax: LineSchema
    net_sales: LineSchema
    cost_of_sales: LineSchema
    gross_profit: LineSchema
    operating_expenses: LineSchema
    operating_profit: LineSchema
    financial_result: LineSchema
    profit_before_income_tax: LineSchema
    income_tax_estimated: LineSchema | None = Field(
        None, description = 'Annual reports only: 25 % of the profit, when there is profit.'
    )
    net_profit_estimated: LineSchema | None = None


class PeriodTaxesSchema(BaseModel):
    '''
        What is paid every month, apart from the income statement. The IUE
        provision is a cash reserve, not an expense.
    '''
    vat_payable: LineSchema
    transactions_tax: LineSchema
    income_tax_provision: LineSchema


class BalanceSheetSchema(BaseModel):
    '''
        The balances at the end of the period, with what the client loaded.
    '''
    assets: float | None
    current_assets: float | None
    cash: float | None
    liabilities: float | None
    current_liabilities: float | None
    equity: float | None
    difference: float | None = Field(
        None, description = 'Assets minus liabilities and equity; 0 when it balances.'
    )


class IndicatorsSchema(BaseModel):
    '''
        The ratios that answer the owner's questions. None when the data that
        feeds one is missing: nothing is invented.
    '''
    liquidity: float | None = Field(None, description = 'Current assets / current liabilities.')
    debt_ratio: float | None = Field(None, description = 'Liabilities / assets.')
    solvency: float | None = Field(None, description = 'Assets / liabilities.')
    coverage_months: float | None = Field(
        None, description = 'Cash / average monthly outflow of the last months: '
                            'how long the business lasts without selling.'
    )


class PeriodReportSchema(BaseModel):
    '''
        The report of one month or one year.
    '''
    period: str = Field(..., description = 'YYYY-MM for a month, YYYY for a year.')
    origin: str = Field(..., description = 'DAILY, MONTHLY or ANNUAL: how its figures were loaded.')
    income_statement: IncomeStatementSchema
    taxes: PeriodTaxesSchema
    balance: BalanceSheetSchema
    indicators: IndicatorsSchema
    notices: list[ReportError] = Field(default_factory = list)


class FinanceReportSchema(BaseModel):
    '''
        Every month and every year the client has, oldest first.
    '''
    months: list[PeriodReportSchema]
    years: list[PeriodReportSchema]
    notices: list[ReportError] = Field(default_factory = list)


class SuggestedParameterSchema(BaseModel):
    '''
        A value BearSoft suggests to every client, set by the ADMIN.
    '''
    parameter_code: str = Field(..., min_length = 1, max_length = 40)
    name: str = Field(..., min_length = 1, max_length = 150)
    value: float = Field(..., ge = 0, le = 100, description = 'Percentage.')


class ClientParameterSchema(BaseModel):
    '''
        The value one client chose for a parameter.
    '''
    value: float = Field(..., ge = 0, le = 100, description = 'Percentage.')


class ClientParameterResponseSchema(BaseModel):
    '''
        A parameter as the client sees it: its own value, if it set one, next
        to the suggestion.
    '''
    parameter_code: str
    name: str
    suggested: float
    value: float | None
    updated_at: str | None = None


class ClientParameterListResponseSchema(BaseModel):
    '''
        Every parameter a client can set.
    '''
    parameters: list[ClientParameterResponseSchema]
    total: int


class SuggestedParameterListResponseSchema(BaseModel):
    '''
        Every suggestion BearSoft keeps.
    '''
    parameters: list[SuggestedParameterSchema]
    total: int
