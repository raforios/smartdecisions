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
    name: str = Field(..., max_length=100, description='Nombre del mineral.')
    unit: str = Field(..., max_length=20, description='Unidad de medida (ej. LF, OT).')

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
