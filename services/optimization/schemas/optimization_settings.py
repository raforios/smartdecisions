'''
    Route parameters of a company.

    Only the base point today: where the company's routes may start or end.
    It is an option and not a rule —start and end are open per route— so a
    company that never sets it loses nothing.
'''
from typing import Optional

from pydantic import BaseModel

from schemas.localization import RouteEndpointSchema


class RouteSettingsSchema(BaseModel):
    '''
        What the company configured for its routes.
    '''
    base_point: Optional[RouteEndpointSchema] = None


class RouteSettingsResponseSchema(RouteSettingsSchema):
    '''
        The stored parameters, with when they last changed.
    '''
    updated_at: Optional[str] = None
