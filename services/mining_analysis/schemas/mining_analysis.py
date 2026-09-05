'''
    Mining Analysis Schemas (Request/Response)
'''
from datetime import datetime, date
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

class MiningStatus(str, Enum):
    '''
        Whether a request could be served.

        Typed instead of a loose string so the value cannot drift between
        endpoints; the wire value is the same one the API already returned.
    '''
    SUCCESS = 'success'


class MiningResult(str, Enum):
    '''
        What the endpoint did, as a stable code.

        These used to be English sentences ('Daily report generated.'). The
        backend returns data and codes; the wording belongs to the frontend or
        to the interpretation layer, which is how the other services already
        work. The facts that the sentences carried — how many records the ETL
        processed, how many it skipped — travel in their own fields, where they
        can be read without parsing prose.
    '''
    PRICES_ETL_COMPLETED = 'PRICES_ETL_COMPLETED'
    ROYALTIES_ETL_COMPLETED = 'ROYALTIES_ETL_COMPLETED'
    ROYALTY_SUMMARY_RETRIEVED = 'ROYALTY_SUMMARY_RETRIEVED'
    TRANSACTIONS_RETRIEVED = 'TRANSACTIONS_RETRIEVED'
    DAILY_REPORT_GENERATED = 'DAILY_REPORT_GENERATED'
    BIWEEKLY_REPORT_GENERATED = 'BIWEEKLY_REPORT_GENERATED'
    BIWEEKLY_HISTORY_GENERATED = 'BIWEEKLY_HISTORY_GENERATED'
    PRICE_FORECAST_GENERATED = 'PRICE_FORECAST_GENERATED'


class MiningAnalysisBaseSchema(BaseModel):
    '''
        Base schema with from_attributes enabled for ORM compatibility.
    '''
    model_config = ConfigDict(from_attributes=True)

class MineralBase(BaseModel):
    ''' Base schema for a mineral. '''
    name: str = Field(..., max_length = 100, description = 'Mineral name.')
    unit: str = Field(..., max_length = 20, description = 'Measurement unit (e.g., LF, OT).')

    # New metadata fields
    chemical_symbol: Optional[str] = Field(None, max_length = 10,
                                    description = 'Chemical symbol (e.g., Sn, Pb).')
    quoted_in: Optional[str] = Field(None, max_length = 50,
                                    description = 'Reference market (e.g., LME, AM).')
    method: Optional[str] = Field(None, max_length = 255, description = 'Calculation method.')

class MineralResponseSchema(MineralBase, MiningAnalysisBaseSchema):
    '''
        Response schema for a mineral.

        `id` and `created_at` are optional because DynamoDB has neither: the
        partition key is the identifier and there is no row to time-stamp. The
        payload the consumers actually read — name, unit, symbol, market — is
        the same on both backends.
    '''
    id: Optional[int] = None
    created_at: Optional[datetime] = None

class MiningPriceCreateSchema(BaseModel):
    ''' Schema for creating a price entry. '''
    mineral_id: int
    date: date
    price_low: Optional[float] = None
    price_high: Optional[float] = None

class MiningPriceResponseSchema(MiningAnalysisBaseSchema):
    '''
        Response schema for mineral prices with nested mineral info.

        `id` is optional: on DynamoDB a quotation is identified by mineral and
        date, which is its key, and there is no surrogate row number to report.
    '''
    id: Optional[int] = None
    date: date
    price_low: float
    price_high: Optional[float]
    mineral: MineralResponseSchema

class BulkUploadMiningResponseSchema(BaseModel):
    ''' Response schema for the ETL process. '''
    result: MiningResult = MiningResult.PRICES_ETL_COMPLETED
    processed_records: int
    status: MiningStatus = MiningStatus.SUCCESS
    skipped_records: int = 0

class RoyaltySummaryItem(BaseModel):
    ''' Item schema for royalty summary extracting all BOB and USD metrics. '''
    year: int
    month: int
    department: str
    municipality: str

    # Métricas BOB
    total_recaudado_bob: float
    comision_bob: float
    subtotal_bob: float
    distribucion_dept_bob: float
    distribucion_muni_bob: float

    # Métricas USD
    total_recaudado_usd: float
    comision_usd: float
    subtotal_usd: float
    distribucion_dept_usd: float
    distribucion_muni_usd: float

    # KPIs analíticos
    variacion_monto_bob: Optional[float] = 0.0
    variacion_porcentaje: Optional[float] = 0.0

class MiningAnalyticsKPIs(BaseModel):
    ''' Schema for summary strategic insights. '''
    total_recaudado_periodo: float = 0.0
    municipios_destacados: List[Dict[str, Any]] = []
    alerta_caida_critica: List[Dict[str, Any]] = []

class RoyaltySummaryData(BaseModel):
    ''' Internal data structure for the response. '''
    detailed_records: List[RoyaltySummaryItem]
    summary_kpis: MiningAnalyticsKPIs

class RoyaltySummaryResponse(BaseModel):
    ''' Main response schema for ministerial reporting. '''
    status: MiningStatus
    result: MiningResult
    data: RoyaltySummaryData

class CompanyTransactionItem(BaseModel):
    ''' Item schema for company transaction summary. '''
    company_name: str
    nit: str
    amount_paid_bob: float
    amount_paid_usd: float
    month: int
    year: int
    municipality: str

class TransactionSummaryResponse(BaseModel):
    ''' Main response schema for transactions. '''
    status: MiningStatus
    result: MiningResult
    data: List[CompanyTransactionItem]


class DailyMineralPriceRow(BaseModel):
    '''
    One row of the daily mineral report (latest available cotización per mineral).

    `is_fallback` is True when no record existed on `ref_date` itself and the
    most-recent prior row was returned instead. `previous_price_low` and
    `change_pct` describe the variation against the immediately preceding day
    with data; both are 0.0 when no prior record exists.
    '''
    mineral: str
    chemical_symbol: Optional[str] = None
    unit: Optional[str] = None
    quoted_in: Optional[str] = None
    price_low: float
    price_high: float
    price_date: date
    previous_price_low: float = 0.0
    previous_price_date: Optional[date] = None
    change_pct: float = 0.0
    is_fallback: bool = False


class DailyReportResponse(BaseModel):
    ''' Response schema for the daily mineral report. '''
    status: MiningStatus = MiningStatus.SUCCESS
    result: MiningResult = MiningResult.DAILY_REPORT_GENERATED
    ref_date: date
    rows: List[DailyMineralPriceRow]


class BiweeklyMineralPriceRow(BaseModel):
    '''
    One row of the biweekly official report.

    `sample_size` is the number of distinct days with a price within the period;
    `avg_price_low` is the simple mean over those days only.
    '''
    mineral: str
    chemical_symbol: Optional[str] = None
    unit: Optional[str] = None
    quoted_in: Optional[str] = None
    avg_price_low: float
    sample_size: int
    period_start: date
    period_end: date
    is_fallback: bool = False


class BiweeklyReportResponse(BaseModel):
    ''' Response schema for the biweekly official mineral report. '''
    status: MiningStatus = MiningStatus.SUCCESS
    result: MiningResult = MiningResult.BIWEEKLY_REPORT_GENERATED
    year: int
    month: int
    half: int = Field(..., ge = 1, le = 2,
                      description = 'Half of the month: 1 for days 1-15, 2 for 16-end.')
    period_start: date
    period_end: date
    rows: List[BiweeklyMineralPriceRow]


class BiweeklyPeriodSummary(BaseModel):
    '''
    One element of the biweekly history series: identifies the period and
    carries the per-mineral averages computed for it.
    '''
    year: int
    month: int
    half: int
    period_start: date
    period_end: date
    rows: List[BiweeklyMineralPriceRow]


class BiweeklyHistoryResponse(BaseModel):
    '''
    Aggregated response listing every biweekly period that has at least one
    cotización in the requested range. Ordered chronologically (oldest first)
    so the front-end can plot the line chart without sorting.
    '''
    status: MiningStatus = MiningStatus.SUCCESS
    result: MiningResult = MiningResult.BIWEEKLY_HISTORY_GENERATED
    period_from: date
    period_to: date
    periods: List[BiweeklyPeriodSummary]


# --- Price forecasting ---

class ForecastMethod(str, Enum):
    '''
        How a projection was produced.

        A stable code, not a sentence: the frontend and the interpretation layer
        word it, and a caller can request one explicitly.
    '''
    DAMPED_TREND = 'DAMPED_TREND'
    LINEAR = 'LINEAR'
    MOVING_AVERAGE = 'MOVING_AVERAGE'
    NAIVE = 'NAIVE'


class ForecastConfidence(str, Enum):
    '''
        How much history backs a projection.

        Reported so a thin series is never presented with the same weight as a
        full one. A quotation with three weeks of history can be projected, but
        the reader has to know that is what they are looking at.
    '''
    HIGH = 'HIGH'
    MEDIUM = 'MEDIUM'
    LOW = 'LOW'
    INSUFFICIENT = 'INSUFFICIENT'


class PricePoint(BaseModel):
    '''One quotation on one date, historical or projected.'''
    date: date
    price: float


class OfficialQuotation(BaseModel):
    '''
        The official biweekly quotation of one mineral.

        In Bolivia the price mining companies settle on is not the last
        quotation of the day: it is the **average of the previous fortnight**.
        The mean of 1-15 September is what rules from 16 to 30 September, so the
        window that was averaged and the window it governs are never the same —
        `period_*` says what was averaged, `valid_*` says when it applies.
    '''
    period_start: date
    period_end: date
    valid_from: date
    valid_to: date
    avg_price_low: float
    sample_size: int = Field(..., ge = 0, description = 'Days that fed the mean.')
    observed_days: int = Field(
        0, ge = 0, description = 'Of those, days already published.'
    )
    projected_days: int = Field(
        0, ge = 0, description = 'Of those, days still to happen.'
    )
    is_complete: bool = Field(
        True,
        description = 'False when the horizon does not cover the whole window, '
                      'so the mean is missing working days.'
    )


class MineralForecast(BaseModel):
    '''
        The projection for a single mineral.

        `history` carries the observed quotations the projection was fitted on,
        so the UI can draw both series on the same axis and the reader can judge
        the trend rather than take the number on faith.
    '''
    mineral: str
    chemical_symbol: Optional[str] = None
    unit: Optional[str] = None
    method: ForecastMethod
    confidence: ForecastConfidence
    sample_size: int = Field(..., ge = 0, description = 'Days of history used.')
    last_price: Optional[float] = Field(
        None, description = 'Most recent observed quotation.'
    )
    change_percent: Optional[float] = Field(
        None, description = 'Projected change against the last observed price.'
    )
    mean_absolute_error: Optional[float] = Field(
        None,
        description = 'Average miss of this method on this mineral, measured by '
                      'replaying the series. Not an assumed interval.'
    )
    baseline_method: ForecastMethod = ForecastMethod.NAIVE
    baseline_error: Optional[float] = Field(
        None, description = 'Same measurement for repeating the last quotation.'
    )
    history: List[PricePoint] = []
    forecast: List[PricePoint] = []
    official_current: Optional[OfficialQuotation] = Field(
        None, description = 'The price in force today, from the closed fortnight.'
    )
    official_history: List[OfficialQuotation] = Field(
        default_factory = list,
        description = 'Official prices already published, newest first, so the '
                      'projection can be checked against what happened.'
    )
    official_forecast: List[OfficialQuotation] = Field(
        default_factory = list,
        description = 'Upcoming official prices the horizon reaches. The first '
                      'one mixes days already quoted with projected ones.'
    )
    official_change_percent: Optional[float] = Field(
        None, description = 'Next official price against the one in force.'
    )


class PriceForecastResponse(BaseModel):
    '''
        Payload for GET /v1/mining-analysis/forecast/prices.
    '''
    status: MiningStatus = MiningStatus.SUCCESS
    result: MiningResult = MiningResult.PRICE_FORECAST_GENERATED
    days_ahead: int
    history_from: Optional[date] = None
    history_to: Optional[date] = None
    minerals: List[MineralForecast] = []
