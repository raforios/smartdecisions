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
    axis: ThematicAxis
    axis_number: int
    axis_label: str

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
