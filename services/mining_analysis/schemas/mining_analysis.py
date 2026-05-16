'''
    Mining Analysis Schemas (Request/Response)
'''
from datetime import datetime, date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

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
    ''' Response schema for a mineral including ID. '''
    id: int
    created_at: datetime

class MiningPriceCreateSchema(BaseModel):
    ''' Schema for creating a price entry. '''
    mineral_id: int
    date: date
    price_low: Optional[float] = None
    price_high: Optional[float] = None

class MiningPriceResponseSchema(MiningAnalysisBaseSchema):
    ''' Response schema for mineral prices with nested mineral info. '''
    id: int
    date: date
    price_low: float
    price_high: Optional[float]
    mineral: MineralResponseSchema

class BulkUploadMiningResponseSchema(BaseModel):
    ''' Response schema for the ETL process. '''
    message: str
    processed_records: int
    status: str = 'success'
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
    status: str
    message: str
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
    status: str
    message: str
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
    status: str = 'success'
    message: str = 'Daily report generated.'
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
    status: str = 'success'
    message: str = 'Biweekly report generated.'
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
    status: str = 'success'
    message: str = 'Biweekly history generated.'
    period_from: date
    period_to: date
    periods: List[BiweeklyPeriodSummary]
