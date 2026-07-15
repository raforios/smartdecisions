'''
    Report Schemas for the Mining Summit service (statistics endpoint).
'''
from enum import Enum
from typing import List, Optional
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


class StatsBasis(str, Enum):
    '''
        Basis for the seat distribution report: people physically PRESENT on a
        given date (from attendances) or all currently REGISTERED participants.
    '''
    PRESENT = 'present'
    REGISTERED = 'registered'


class AulaDistributionSchema(BaseModel):
    '''
        Head-count for a single aula (mesa) within a thematic axis.
    '''
    mesa_code: str = Field(..., description = 'Aula/mesa code, e.g. "A3".')
    capacity: int = Field(..., ge = 0)
    count: int = Field(..., ge = 0, description = 'People counted in this aula.')

    model_config = ConfigDict(extra = 'ignore')


class AxisDistributionSchema(BaseModel):
    '''
        Head-count for a thematic axis, broken down by its allocated aulas.
    '''
    axis: str = Field(..., description = 'Thematic axis value.')
    number: int = Field(..., ge = 1, le = 6, description = 'Official axis number.')
    label: str = Field(..., description = 'Human-readable axis label.')
    capacity: int = Field(..., ge = 0, description = 'Sum of the aula capacities.')
    count: int = Field(..., ge = 0, description = 'People counted in this axis.')
    aulas: List[AulaDistributionSchema]

    model_config = ConfigDict(extra = 'ignore')


class SeatDistributionResponseSchema(BaseModel):
    '''
        Distribution of people across thematic axes and their aulas, either for
        those present on a date or for all registered participants.
    '''
    basis: StatsBasis
    date: Optional[str] = Field(None,
                                description = 'Attendance date (present basis only).')
    total: int = Field(..., ge = 0, description = 'Total people counted.')
    unassigned: int = Field(..., ge = 0,
                            description = 'Counted people without an axis/aula seat.')
    axes: List[AxisDistributionSchema]


class NotAccreditedItemSchema(BaseModel):
    '''
        A single not-accredited spreadsheet row across the ETL load batches.
    '''
    institution_id: Optional[str] = None
    institution_name: Optional[str] = None
    batch_id: Optional[str] = None
    row: Optional[int] = None
    ci: Optional[str] = None
    reason: str

    model_config = ConfigDict(extra = 'ignore')


class NotAccreditedReportSchema(BaseModel):
    '''
        Not-accredited report (constancia) aggregating every rejected row.
    '''
    total: int = Field(..., ge = 0)
    items: List[NotAccreditedItemSchema]
