'''
    Pydantic V2 DTOs for the QUOTES service.

    Two things travel over this API: the exchange-rate history we keep, and the
    projection built on it. Failures are reported as stable codes, never as
    sentences — the frontend and the interpretation layer own the wording.
'''
from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class QuotesError(str, Enum):
    '''
        Why a request could not be served.

        Travels as the error `detail`, same contract as the other services.
    '''
    SOURCE_UNAVAILABLE = 'SOURCE_UNAVAILABLE'
    SOURCE_UNREADABLE = 'SOURCE_UNREADABLE'
    NO_RATE_PUBLISHED = 'NO_RATE_PUBLISHED'
    EMPTY_PERIOD = 'EMPTY_PERIOD'
    INVALID_DATE_RANGE = 'INVALID_DATE_RANGE'
    UNKNOWN_MODEL = 'UNKNOWN_MODEL'
    NO_RATE_FOR_DATE = 'NO_RATE_FOR_DATE'


class ExchangeRatePoint(BaseModel):
    '''The official rate on one date, observed or projected.'''
    date: date
    rate: float


class RateOnDate(BaseModel):
    """
        The rate in force on one day, and where it comes from.

        `regime` matters as much as the figure: a day before the float carries
        the fixed rate, and saying so stops a reader from taking 6.86 for a
        market quote that never existed.
    """
    date: str
    currency: str
    rate: float
    published_on: Optional[str] = Field(
        None, description = 'The day the BCB published it. None under the fixed regime.'
    )
    regime: str = Field(..., description = 'FIXED or FLOAT.')


class ExchangeRateHistory(BaseModel):
    '''
        The stored series for one currency.
    '''
    currency: str
    days: int = Field(..., ge = 0, description = 'Days with a published rate.')
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    rates: List[ExchangeRatePoint] = []


class SyncResult(BaseModel):
    '''
        Outcome of pulling rates from the source into our own history.
    '''
    currency: str
    requested_days: int
    stored: int = Field(..., ge = 0, description = 'Dates written.')
    already_present: int = Field(..., ge = 0, description = 'Dates already stored.')
    without_publication: int = Field(
        ..., ge = 0,
        description = 'Dates the source publishes nothing for, weekends included.'
    )
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class RateConfidence(str, Enum):
    '''
        How much history backs a rate projection.

        Reported so a thin series is never presented with the same weight as a
        full one.
    '''
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'
    INSUFFICIENT = 'INSUFFICIENT'


class ForecastMethod(str, Enum):
    '''
        How a projection was produced.

        A code, not a sentence: the frontend words it. It travels with every
        projection because a reader judging a number is entitled to know what
        produced it.
    '''
    DAMPED_TREND = 'DAMPED_TREND'
    NAIVE = 'NAIVE'


class ForecastAccuracy(BaseModel):
    '''
        How far a model has missed on this very series.

        Measured, not assumed: the series is replayed from every starting point
        that leaves room for the horizon and the errors are averaged. The
        baseline is the naive forecast — "tomorrow is the same as today" — which
        for an exchange rate is the hardest short-horizon benchmark there is.
        Publishing both is what lets a reader judge whether the projection earns
        its place.
    '''
    method: ForecastMethod
    mean_absolute_error: Optional[float] = Field(
        None, description = 'Average miss of the model, in the unit of the series.'
    )
    baseline_method: ForecastMethod = ForecastMethod.NAIVE
    baseline_error: Optional[float] = Field(
        None, description = 'Average miss of the baseline, same measurement.'
    )
    windows: int = Field(0, ge = 0, description = 'Replays the average is over.')


class ModelRun(BaseModel):
    '''
        One model run over the series, with what it has actually got wrong.

        `mean_absolute_error` comes from re-running the series from every
        starting point, not from an assumed interval. It is None when the
        history leaves too few windows to measure it: better no number than one
        that looks measured and is not.
    '''
    model: str
    change_percent: Optional[float] = None
    final_rate: Optional[float] = None
    mean_absolute_error: Optional[float] = None
    projected: List[ExchangeRatePoint] = Field(default_factory = list)


class ModelBench(BaseModel):
    '''
        Several models over the same series, ordered by their error.

        Seeing them together answers something none of them answers alone: HOW
        MUCH THE ANSWER DEPENDS ON THE MODEL. Where the projections agree the
        figure belongs to the business; where they separate, to the model.
    '''
    currency: str
    days_ahead: int = Field(..., ge = 1)
    confidence: RateConfidence
    last_rate: Optional[float] = None
    last_date: Optional[date] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    windows: int = Field(0, ge = 0, description = 'Réplicas que promedia el error.')
    history: List[ExchangeRatePoint] = Field(default_factory = list)
    runs: List[ModelRun] = Field(default_factory = list)


class SaleOutcome(BaseModel):
    '''
        What a sale is worth under one set of conditions.
    '''
    exchange_rate: float = Field(..., description = 'Bolivianos per dollar applied.')
    mineral_price: Optional[float] = Field(
        None, description = 'Unit price applied, when the caller supplied one.'
    )
    amount_usd: float = Field(..., ge = 0, description = 'Value of the sale in dollars.')
    amount_bob: float = Field(..., ge = 0, description = 'Value of the sale in bolivianos.')


class SaleScenario(BaseModel):
    '''
        Selling today against waiting, with what each path is worth.

        The comparison exists because both variables move: the mineral is
        quoted in dollars and the dollar is quoted in bolivianos, so waiting can
        gain on one side and lose on the other. `difference_bob` is what the
        decision is actually worth.
    '''
    days_ahead: int = Field(..., ge = 1)
    rate_confidence: RateConfidence
    rate_change_percent: Optional[float] = None
    mineral_change_percent: Optional[float] = Field(
        None, description = 'Expected change of the mineral price, as supplied.'
    )
    today: SaleOutcome
    projected: Optional[SaleOutcome] = Field(
        None, description = 'Absent when the history cannot support a projection.'
    )
    difference_bob: Optional[float] = Field(
        None, description = 'Projected minus today, in bolivianos.'
    )
    difference_percent: Optional[float] = None


class SaleScenarioRequest(BaseModel):
    '''
        What the seller is weighing: how much, at what price, for how long.
    '''
    quantity: float = Field(..., gt = 0, description = 'Units being sold.')
    unit_price_usd: float = Field(
        ..., gt = 0, description = 'Price per unit today, in dollars.'
    )
    days_ahead: int = Field(30, ge = 1, le = 90, description = 'Days to wait.')
    mineral_change_percent: Optional[float] = Field(
        None,
        description = 'Expected change of the unit price over the horizon, from '
                      'the MINING_ANALYSIS projection. Omit to price the '
                      'currency move alone.'
    )


class RateForecast(BaseModel):
    '''
        The exchange rate projected forward on its own.

        Exists because the dollar is a question by itself, not only an input to
        a sale: `projected` is empty when the history cannot support a
        projection, and `confidence` says why.
    '''
    currency: str
    days_ahead: int = Field(..., ge = 1)
    confidence: RateConfidence
    change_percent: Optional[float] = None
    last_rate: Optional[float] = None
    last_date: Optional[date] = None
    valid_from: Optional[date] = Field(
        None, description = 'First day the published rate is in force.'
    )
    valid_to: Optional[date] = Field(
        None,
        description = 'Last day it is in force. The rate published for a '
                      'Saturday governs Saturday, Sunday and Monday.'
    )
    final_rate: Optional[float] = Field(
        None, description = 'Projected rate at the end of the horizon.'
    )
    accuracy: Optional[ForecastAccuracy] = Field(
        None, description = 'What the projection has been worth on this series.'
    )
    history: List[ExchangeRatePoint] = []
    projected: List[ExchangeRatePoint] = []
