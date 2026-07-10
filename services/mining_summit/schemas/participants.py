'''
    Participant Schemas (Request / Response / Query) for the Mining Summit service.
'''
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

from schemas.common import OptionalContactSchema
from schemas.enums import AssignmentType, ParticipantRole, ThematicAxis


class ParticipantCreateSchema(OptionalContactSchema):
    '''
        Pydantic schema for registering a new summit participant.
        First name, last name and CI are mandatory; remaining fields are optional.
    '''
    first_name: str = Field(..., min_length = 1, max_length = 80)
    last_name: str = Field(..., min_length = 1, max_length = 80)
    ci: str = Field(..., min_length = 4, max_length = 20,
                    description = 'Carnet de Identidad. Unique identifier per participant.')
    institution_id: Optional[str] = Field(
        None, max_length = 120,
        description = 'Reference institution slug; drives role and seat assignment.'
    )


class ParticipantResponseSchema(BaseModel):
    '''
        Pydantic schema for participant responses, including the resolved role
        and stable eje/mesa seat when the participant belongs to an institution.
    '''
    ci: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    company: Optional[str] = None
    institution_id: Optional[str] = None
    institution_name: Optional[str] = None
    role: Optional[ParticipantRole] = None
    assignment_type: Optional[AssignmentType] = None
    axis: Optional[ThematicAxis] = None
    axis_label: Optional[str] = None
    mesa_code: Optional[str] = None
    registered_date: str
    registered_at: str

    model_config = ConfigDict(extra = 'ignore')


class ParticipantQuerySchema(BaseModel):
    '''
        Pydantic schema for filtering and paginating the participants list.
    '''
    department: Optional[str] = Field(None, max_length = 60)
    company: Optional[str] = Field(None, max_length = 120)
    registered_from: Optional[str] = Field(
        None, description = 'Inclusive lower bound (YYYY-MM-DD) for registered_date.'
    )
    registered_to: Optional[str] = Field(
        None, description = 'Inclusive upper bound (YYYY-MM-DD) for registered_date.'
    )
    limit: int = Field(50, ge = 1, le = 100)
    last_evaluated_key: Optional[str] = Field(
        None, description = 'Pagination token returned by the previous page.'
    )


class ParticipantsListResponseSchema(BaseModel):
    '''
        Paginated response wrapper for participants.
    '''
    items: List[ParticipantResponseSchema]
    last_evaluated_key: Optional[str] = None
