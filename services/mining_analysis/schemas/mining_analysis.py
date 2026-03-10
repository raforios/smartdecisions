'''
    Mining Analysis Schemas (Request/Response)
'''
from datetime import datetime, date
from typing import List, Optional
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
    ''' Item schema for royalty summary. '''
    year: int
    month: int
    department: str
    municipality: str
    total_recaudado: float
    subtotal: float
    gov_dept: float
    gov_muni: float

class RoyaltySummaryResponse(BaseModel):
    ''' Response schema for royalty summary. '''
    status: str
    data: List[RoyaltySummaryItem]
