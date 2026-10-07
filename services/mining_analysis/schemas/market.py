'''
    Pydantic V2 DTOs for the market side of the quotations: the daily prices
    read from public sources, the Art. 227 royalty scales, and the anticipated
    official quotation they produce for the fortnight in progress.
'''
from datetime import date
from enum import Enum
from pydantic import BaseModel, Field


class MarketError(str, Enum):
    '''
        Why a market request could not be served.
    '''
    SOURCE_UNAVAILABLE = 'SOURCE_UNAVAILABLE'
    SOURCE_UNREADABLE = 'SOURCE_UNREADABLE'
    UNKNOWN_MINERAL = 'UNKNOWN_MINERAL'
    MINERAL_NOT_MARKET_QUOTED = 'MINERAL_NOT_MARKET_QUOTED'
    RULE_NOT_FOUND = 'RULE_NOT_FOUND'
    INVALID_DATE_RANGE = 'INVALID_DATE_RANGE'


class MarketSource(str, Enum):
    '''
        Where a daily market price came from. The Ministry's own series:
        the LBMA AM fix for gold, the LBMA fix for silver, the LME cash price
        (settlement as published by Westmetall) for the base metals.
    '''
    LBMA_GOLD_AM = 'LBMA_GOLD_AM'
    LBMA_SILVER = 'LBMA_SILVER'
    LME_CASH_WESTMETALL = 'LME_CASH_WESTMETALL'


class RateBasis(str, Enum):
    '''
        Which part of the Art. 227 scale decided the rate.
    '''
    FORMULA = 'FORMULA'
    CAP = 'CAP'
    FLOOR = 'FLOOR'
    FIXED = 'FIXED'


class EstimateConfidence(str, Enum):
    '''
        How much of the fortnight is already quoted.
    '''
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'
    NONE = 'NONE'


class MarketSyncResult(BaseModel):
    '''
        What a sync run did.
    '''
    requested_days: int
    date_from: date
    date_to: date
    stored: int
    already_present: int
    without_publication: int
    failed_sources: list[MarketSource] = Field(
        default_factory = list,
        description = 'Sources that could not be read this run; the others were stored.'
    )


class MarketPriceRow(BaseModel):
    '''
        One daily market price.
    '''
    date: date
    price: float
    source: MarketSource


class MarketPricesResponse(BaseModel):
    '''
        The market series of one mineral in a window.
    '''
    mineral_id: str
    name: str
    unit: str
    items: list[MarketPriceRow]


class RoyaltyRuleSchema(BaseModel):
    '''
        The Art. 227 scale of one mineral, as stored and as edited.
        rate = clamp(slope * CO + intercept, min_rate, max_rate); domestic sales
        pay `internal_factor` of that.
    '''
    mineral_id: str = Field(..., min_length = 1, max_length = 16)
    slope: float
    intercept: float
    min_rate: float = Field(..., ge = 0, le = 100)
    max_rate: float = Field(..., ge = 0, le = 100)
    internal_factor: float = Field(..., gt = 0, le = 1)
    legal_basis: str = Field(..., max_length = 120)
    updated_at: str | None = None


class RoyaltyRulesResponse(BaseModel):
    '''
        Every scale.
    '''
    rules: list[RoyaltyRuleSchema]


class EstimateRow(BaseModel):
    '''
        The official quotation a mineral is heading to, from the days already
        quoted in the fortnight in progress.
    '''
    mineral_id: str
    name: str
    chemical_symbol: str
    unit: str
    source: MarketSource | None = Field(
        None, description = 'None when the mineral has no free daily source (Asian Metal).'
    )
    days_quoted: int
    calendar_days_elapsed: int
    running_average: float | None = None
    latest_price: float | None = None
    latest_date: date | None = None
    previous_official: float | None = Field(
        None, description = 'The quotation in force now: the average of the fortnight before.'
    )
    change_percent: float | None = Field(
        None, description = 'Running average against the quotation in force.'
    )
    export_rate: float | None = Field(None, description = 'Art. 227 rate, percent.')
    internal_rate: float | None = None
    rate_basis: RateBasis | None = None
    confidence: EstimateConfidence


class EstimateResponse(BaseModel):
    '''
        The anticipated official quotation for every mineral of the catalogue.
    '''
    as_of: date
    period_year: int
    period_month: int
    period_half: int
    period_start: date
    period_end: date
    valid_from: date = Field(..., description = 'First day the averaged fortnight will rule.')
    valid_to: date
    rows: list[EstimateRow]


class MarketWindow(BaseModel):
    '''
        The date range a market series covers.

        The two bounds travel together and are validated together, so they go
        as one argument: the controller stays within the argument budget and
        neither bound can be passed without the other.
    '''
    date_from: date | None = Field(None, description = 'First day; open when absent.')
    date_to: date | None = Field(None, description = 'Last day; open when absent.')
