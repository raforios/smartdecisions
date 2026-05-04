'''
    Report Schemas for the Mining Summit service (statistics endpoint).
'''
from enum import Enum
from typing import List
from pydantic import BaseModel, ConfigDict, Field


class StatsGroupBy(str, Enum):
    '''
        Allowed group-by dimensions for the statistical report.
    '''
    DEPARTMENT = 'department'
    COMPANY = 'company'


class StatsItemSchema(BaseModel):
    '''
        Single bucket of the statistical report.
    '''
    label: str = Field(..., description = 'Group label (e.g., "La Paz" or "ABC Corp").')
    count: int = Field(..., ge = 0)
    percentage: float = Field(..., ge = 0, le = 100,
                              description = 'Share of the total, expressed as 0-100.')

    model_config = ConfigDict(extra = 'ignore')


class StatsResponseSchema(BaseModel):
    '''
        Statistical report response shape.
    '''
    group_by: StatsGroupBy
    total: int = Field(..., ge = 0)
    items: List[StatsItemSchema]
