'''
    Mining Analysis Schemas (Request/Response)
'''
from typing import Optional
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict

class MiningAnalysisBaseSchema(BaseModel):
    '''
        Base schema with from_attributes enabled for ORM compatibility.
    '''
    model_config = ConfigDict(from_attributes=True)

class MineralBase(BaseModel):
    ''' Base schema for a mineral. '''
    name: str = Field(..., max_length=100, description="Nombre del mineral.")
    unit: str = Field(..., max_length=20, description="Unidad de medida (ej. LF, OT).")

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
    status: str = "success"
    skipped_records: int = 0
