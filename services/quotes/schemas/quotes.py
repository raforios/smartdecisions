'''
    Pydantic V2 DTOs for the QUOTES service.

    Two things travel over this API: the exchange-rate history we keep, and the
    projection built on it. Failures are reported as stable codes, never as
    sentences — the frontend and the interpretation layer own the wording.
'''
from datetime import date
from enum import Enum

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
    FORECAST_UNAVAILABLE = 'FORECAST_UNAVAILABLE'
    RATES_STORE_UNAVAILABLE = 'RATES_STORE_UNAVAILABLE'


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
    published_on: str | None = Field(
        None, description = 'The day the BCB published it. None under the fixed regime.'
    )
    regime: str = Field(..., description = 'FIXED or FLOAT.')


class ExchangeRateHistory(BaseModel):
    '''
        The stored series for one currency.
    '''
    currency: str
    days: int = Field(..., ge = 0, description = 'Days with a published rate.')
    date_from: date | None = None
    date_to: date | None = None
    rates: list[ExchangeRatePoint] = []


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
    date_from: date | None = None
    date_to: date | None = None


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
    mean_absolute_error: float | None = Field(
        None, description = 'Average miss of the model, in the unit of the series.'
    )
    baseline_method: ForecastMethod = ForecastMethod.NAIVE
    baseline_error: float | None = Field(
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
    change_percent: float | None = None
    final_rate: float | None = None
    mean_absolute_error: float | None = None
    projected: list[ExchangeRatePoint] = Field(default_factory = list)


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
    last_rate: float | None = None
    last_date: date | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    windows: int = Field(0, ge = 0, description = 'Réplicas que promedia el error.')
    history: list[ExchangeRatePoint] = Field(default_factory = list)
    runs: list[ModelRun] = Field(default_factory = list)


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
    change_percent: float | None = None
    last_rate: float | None = None
    last_date: date | None = None
    valid_from: date | None = Field(
        None, description = 'First day the published rate is in force.'
    )
    valid_to: date | None = Field(
        None,
        description = 'Last day it is in force. The rate published for a '
                      'Saturday governs Saturday, Sunday and Monday.'
    )
    final_rate: float | None = Field(
        None, description = 'Projected rate at the end of the horizon.'
    )
    accuracy: ForecastAccuracy | None = Field(
        None, description = 'What the projection has been worth on this series.'
    )
    history: list[ExchangeRatePoint] = []
    projected: list[ExchangeRatePoint] = []
