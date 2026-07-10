'''
    Attendance Schemas (Request / Response / Query) for the Mining Summit service.
'''
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from schemas.common import OptionalContactSchema


class AttendanceCreateSchema(OptionalContactSchema):
    '''
        Pydantic schema for registering a daily attendance.

        If the CI does not exist yet, the service auto-creates the participant
        on-the-fly. In that case first_name and last_name become required.
    '''
    ci: str = Field(..., min_length = 4, max_length = 20)
    first_name: Optional[str] = Field(None, min_length = 1, max_length = 80)
    last_name: Optional[str] = Field(None, min_length = 1, max_length = 80)


class AttendanceResponseSchema(BaseModel):
    '''
        Pydantic schema for attendance responses.
    '''
    ci: str
    attendance_date: str = Field(..., description = 'YYYY-MM-DD in America/La_Paz.')
    attendance_at: str = Field(..., description = 'ISO 8601 datetime in America/La_Paz.')
    marked_by: str = Field(..., description = 'Email of the user who registered the entry.')
    participant_created: bool = Field(
        False,
        description = 'True if the participant was created during this attendance call.'
    )

    model_config = ConfigDict(extra = 'ignore')


class AttendanceQuerySchema(BaseModel):
    '''
        Pydantic schema for filtering and paginating the attendances list.
    '''
    ci: Optional[str] = Field(None, max_length = 20)
    date_from: Optional[str] = Field(
        None, description = 'Inclusive lower bound (YYYY-MM-DD) for attendance_date.'
    )
    date_to: Optional[str] = Field(
        None, description = 'Inclusive upper bound (YYYY-MM-DD) for attendance_date.'
    )
    limit: int = Field(50, ge = 1, le = 100)
    last_evaluated_key: Optional[str] = Field(None)


class AttendancesListResponseSchema(BaseModel):
    '''
        Paginated response wrapper for attendances.
    '''
    items: List[AttendanceResponseSchema]
    last_evaluated_key: Optional[str] = None
