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


class ExchangeRatePoint(BaseModel):
    '''The official rate on one date, observed or projected.'''
    date: date
    rate: float


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
    final_rate: Optional[float] = Field(
        None, description = 'Projected rate at the end of the horizon.'
    )
    history: List[ExchangeRatePoint] = []
    projected: List[ExchangeRatePoint] = []
