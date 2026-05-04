'''
    Participant Schemas (Request / Response / Query) for the Mining Summit service.
'''
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ParticipantCreateSchema(BaseModel):
    '''
        Pydantic schema for registering a new summit participant.
        First name, last name and CI are mandatory; remaining fields are optional.
    '''
    first_name: str = Field(..., min_length = 1, max_length = 80)
    last_name: str = Field(..., min_length = 1, max_length = 80)
    ci: str = Field(..., min_length = 4, max_length = 20,
                    description = 'Carnet de Identidad. Unique identifier per participant.')
    email: Optional[EmailStr] = Field(None, max_length = 120)
    phone: Optional[str] = Field(None, max_length = 30)
    department: Optional[str] = Field(None, max_length = 60)
    company: Optional[str] = Field(None, max_length = 120)

    model_config = ConfigDict(extra = 'ignore')


class ParticipantResponseSchema(BaseModel):
    '''
        Pydantic schema for participant responses.
    '''
    ci: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    company: Optional[str] = None
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
