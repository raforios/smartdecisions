'''
    Institution Schemas (Response / Query) for the Mining Summit service.
'''
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from schemas.enums import AssignmentType, InstitutionCategory, ParticipantRole


class InstitutionResponseSchema(BaseModel):
    '''
        Pydantic schema for a reference institution, enriched with the role and
        seat-assignment type derived from its category.
    '''
    id: str
    number: int
    name: str
    abbreviation: Optional[str] = None
    category: InstitutionCategory
    cupos: int
    role: ParticipantRole
    assignment_type: AssignmentType

    model_config = ConfigDict(extra = 'ignore')


class InstitutionsListResponseSchema(BaseModel):
    '''
        Response wrapper for the institutions catalog, including the summed
        planned cupos across the returned items.
    '''
    items: List[InstitutionResponseSchema]
    total_cupos: int


class InstitutionQuerySchema(BaseModel):
    '''
        Optional filters for the institutions catalog listing.
    '''
    category: Optional[InstitutionCategory] = Field(
        None, description = 'Filter by institutional category.'
    )
    role: Optional[ParticipantRole] = Field(
        None, description = 'Filter by derived participant role.'
    )
