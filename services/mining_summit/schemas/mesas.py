'''
    Mesa / Thematic Axis Schemas (Response / Query) for the Mining Summit.
'''
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from schemas.enums import ThematicAxis


class MesaResponseSchema(BaseModel):
    '''
        Pydantic schema for a working table (mesa ≡ aula), including the campus
        location and the thematic axis it was allocated to.
    '''
    code: str
    block: str
    location: str
    capacity: int
    # A pivot aula (free disposition) carries no axis until it is allocated.
    axis: Optional[ThematicAxis] = None
    axis_number: Optional[int] = None
    axis_label: Optional[str] = None

    model_config = ConfigDict(extra = 'ignore')


class MesasListResponseSchema(BaseModel):
    '''
        Response wrapper for the mesas listing, including the total seat capacity.
    '''
    items: List[MesaResponseSchema]
    total_capacity: int


class MesaQuerySchema(BaseModel):
    '''
        Optional filters for the mesas listing.
    '''
    axis: Optional[ThematicAxis] = Field(
        None, description = 'Filter mesas by thematic axis.'
    )


class MesaUpdateSchema(BaseModel):
    '''
        Parametric update for an aula: change its descriptive location fields
        (block/location), its seat capacity and/or the thematic axis it is
        allocated to. At least one field must be provided.
    '''
    block: Optional[str] = Field(
        None, min_length = 1, max_length = 40,
        description = 'New campus block the aula belongs to.'
    )
    location: Optional[str] = Field(
        None, min_length = 1, max_length = 60,
        description = 'New human-readable location (floor/wing).'
    )
    capacity: Optional[int] = Field(
        None, gt = 0, description = 'New seat capacity for the aula.'
    )
    axis: Optional[ThematicAxis] = Field(
        None, description = 'New thematic axis the aula is allocated to.'
    )


class MesaCreateSchema(BaseModel):
    '''
        Registers a new aula (extra classroom) with its capacity and axis.
    '''
    code: str = Field(..., min_length = 1, max_length = 20,
                      description = 'Unique aula code (e.g. "A18").')
    block: str = Field(..., min_length = 1, max_length = 40,
                       description = 'Campus block the aula belongs to.')
    location: str = Field(..., min_length = 1, max_length = 60,
                          description = 'Human-readable location (floor/wing).')
    capacity: int = Field(..., gt = 0, description = 'Seat capacity of the aula.')
    axis: Optional[ThematicAxis] = Field(
        None,
        description = ('Thematic axis the aula is allocated to. Omit for a pivot '
                       '(free disposition) aula that can be assigned to any axis later.')
    )


class AxisResponseSchema(BaseModel):
    '''
        Pydantic schema for a thematic axis with its allocated mesa count and
        aggregated seat capacity.
    '''
    axis: ThematicAxis
    number: int
    label: str
    mesas: int
    capacity: int


class AxesListResponseSchema(BaseModel):
    '''
        Response wrapper for the thematic axes, with the summit-wide totals.
    '''
    items: List[AxisResponseSchema]
    total_mesas: int
    total_capacity: int


class AulaAvailabilitySchema(BaseModel):
    '''
        Free-seat breakdown for a single aula.
    '''
    mesa_code: str
    capacity: int
    occupied: int
    free: int

    model_config = ConfigDict(extra = 'ignore')


class AxisAvailabilitySchema(BaseModel):
    '''
        Free-seat availability for a thematic axis, broken down by its aulas.
    '''
    axis: ThematicAxis
    number: int
    label: str
    capacity: int
    occupied: int
    free: int
    aulas: List[AulaAvailabilitySchema]

    model_config = ConfigDict(extra = 'ignore')


class AvailabilityResponseSchema(BaseModel):
    '''
        Response wrapper for the seat availability across all thematic axes.
    '''
    items: List[AxisAvailabilitySchema]
    total_free: int
