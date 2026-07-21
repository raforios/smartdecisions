'''
    Institution Schemas (Response / Query) for the Mining Summit service.
'''
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from schemas.enums import InstitutionCategory


class InstitutionResponseSchema(BaseModel):
    '''
        Pydantic schema for a reference institution.
    '''
    id: str
    number: Optional[int] = None
    name: str
    abbreviation: Optional[str] = None
    category: InstitutionCategory
    cupos: int
    # Live occupancy, populated on the single-institution detail endpoint.
    accredited_count: Optional[int] = Field(
        None, description = 'ACTIVE participants already accredited for this institution.'
    )
    available_cupos: Optional[int] = Field(
        None, description = 'Remaining cupo (cupos - accredited_count).'
    )

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


class InstitutionCuposUpdateSchema(BaseModel):
    '''
        Parametric update of an institution's participant quota (cupos).
    '''
    cupos: int = Field(..., ge = 0, description = 'New non-negative participant quota.')


class InstitutionCreateSchema(BaseModel):
    '''
        Payload to register a new institution. The id is optional; when omitted
        it is derived from the name (slug).
    '''
    name: str = Field(..., min_length = 2, max_length = 160)
    category: InstitutionCategory = Field(..., description = 'Institutional category.')
    cupos: int = Field(..., ge = 0, description = 'Participant quota.')
    abbreviation: Optional[str] = Field(None, max_length = 40)
    id: Optional[str] = Field(None, min_length = 1, max_length = 120,
                              description = 'Optional explicit slug id.')


class InstitutionUpdateSchema(BaseModel):
    '''
        Partial update of an institution. Only the supplied fields change.
    '''
    name: Optional[str] = Field(None, min_length = 2, max_length = 160)
    category: Optional[InstitutionCategory] = None
    cupos: Optional[int] = Field(None, ge = 0)
    abbreviation: Optional[str] = Field(None, max_length = 40)
