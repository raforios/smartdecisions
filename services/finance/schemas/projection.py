'''
    Pydantic V2 DTOs for the projection: how the next months may go in three
    scenarios, and until when the cash lasts in each.

    Nothing is stored: the projection is computed when asked for, from the
    months the client loaded and the values the manager types on the screen
    (Rafael, 17-oct: the scenario percentages and the horizon start from the
    defaults in PARAMETERS and can be changed by keyboard, validated).
'''
from enum import Enum
from pydantic import BaseModel, Field


class ProjectionError(str, Enum):
    '''
        Why a projection could not be given, or was given with a caveat.
    '''
    NOT_ENOUGH_HISTORY_FOR_PROJECTION = 'NOT_ENOUGH_HISTORY_FOR_PROJECTION'
    HORIZON_OUT_OF_RANGE = 'HORIZON_OUT_OF_RANGE'
    CHANGE_OUT_OF_RANGE = 'CHANGE_OUT_OF_RANGE'
    NO_CASH_LOADED = 'NO_CASH_LOADED'
    IUE_PROVISION_NOT_SET = 'IUE_PROVISION_NOT_SET'
    FORECAST_UNAVAILABLE = 'FORECAST_UNAVAILABLE'


class ScenarioName(str, Enum):
    '''
        The three scenarios of the plan.
    '''
    WORST = 'WORST'
    REALISTIC = 'REALISTIC'
    BEST = 'BEST'


class ScenarioInputSchema(BaseModel):
    '''
        The changes a scenario applies to the realistic projection, in
        percent: -15 means 15 % less.
    '''
    sales_change: float
    outflow_change: float


class ProjectedMonthSchema(BaseModel):
    '''
        One projected month of one scenario, in bolivianos.
    '''
    period: str = Field(..., description = 'YYYY-MM.')
    net_sales: float
    outflow: float = Field(..., description = 'Cost of sales, operating expenses and the '
                                              'financial result, as in the income statement.')
    profit: float
    non_cash: float = Field(..., description = 'Depreciation inside the outflow: an expense '
                                               'that never leaves the cash.')
    provision: float = Field(..., description = 'What moves from the cash to the IUE reserve.')
    income_tax_paid: float = Field(..., description = 'IUE paid this month from the reserve '
                                                      'and, for what it does not cover, the cash.')
    reserve: float = Field(..., description = 'The IUE reserve at the end of the month.')
    cash: float = Field(..., description = 'The cash at the end of the month.')


class ScenarioSchema(BaseModel):
    '''
        One scenario, month by month, and the month its cash runs out.
    '''
    name: ScenarioName
    sales_change: float
    outflow_change: float
    months: list[ProjectedMonthSchema]
    cash_runs_out: str | None = Field(
        None, description = 'The first month the cash goes below zero; None if it lasts '
                            'the whole horizon.'
    )


class ModelSchema(BaseModel):
    '''
        How good the realistic projection has been on the client's own history:
        its mean error next to that of "the next month is the same as this one".
    '''
    name: str = Field(..., description = 'NAIVE, DAMPED_TREND or HOLT_WINTERS, '
                                         'as ML_FUNCTIONS chose it for the net sales.')
    error_percent: float | None
    naive_error_percent: float | None
    tested_points: int = Field(..., ge = 0, description = 'Months the errors were measured on.')


class ExchangeTodaySchema(BaseModel):
    '''
        A future month has no rate yet: its bolivianos are read at today's.
    '''
    date: str
    usd: float | None
    usdt: float | None


class ProjectionSchema(BaseModel):
    '''
        The projection of a client.
    '''
    horizon: int
    last_period: str | None
    base_cash: float | None
    scenarios: list[ScenarioSchema]
    model: ModelSchema | None
    exchange: ExchangeTodaySchema | None
    notices: list[ProjectionError] = Field(default_factory = list)
