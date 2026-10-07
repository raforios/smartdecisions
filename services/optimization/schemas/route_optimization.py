'''
    Pydantic V2 DTOs for optimizing a route that already exists.

    The planner builds a week from the sales file; this answers a different
    question, and the one the client actually asks: **this route I already
    have —the one I walked, the one I imported, the one the seller built on
    the street— in what order was it worth doing, and how much would I have
    saved?**

    It proposes and never writes. A saving nobody can see is not an argument,
    so the answer carries both orders, both figures and both geometries, and
    the screen draws them side by side.
'''
from enum import Enum
from pydantic import BaseModel, Field


class RouteOptimizationError(str, Enum):
    '''
        Why a route could not be optimized.
    '''
    NOT_ENOUGH_STOPS = 'NOT_ENOUGH_STOPS'
    NO_COORDINATES = 'NO_COORDINATES'


class OptimizedStopSchema(BaseModel):
    '''
        One stop in a proposed order.

        `original_order` is what makes the change readable: the third stop of
        the plan showing up first says more than any total.
    '''
    point_name: str
    client_id: str | None = None
    latitude: float
    longitude: float
    order: int = Field(..., gt = 0, description = 'Position in this ordering.')
    original_order: int = Field(..., gt = 0, description = 'Position it had before.')


class RouteShapeSchema(BaseModel):
    '''
        One ordering of the same stops, measured and drawable.
    '''
    stops: list[OptimizedStopSchema]
    distance_metres: float = Field(..., ge = 0)
    duration_seconds: float = Field(..., ge = 0)
    geometry: list[list[float]] = Field(
        default_factory = list,
        description = 'The path along real streets, as [longitude, latitude] '
                      'pairs. Empty when OSRM could not be reached: the order '
                      'is still valid and the map falls back to straight lines.'
    )


class RouteOptimizationSchema(BaseModel):
    '''
        The current route, the proposed one, and what separates them.

        Nothing is written: this is a proposal. Accepting it is a separate,
        explicit act —reordering a plan still in creation, or repeating the
        route on another day with the new order— because changing a route
        somebody is already running is not something a report should do.
    '''
    planned_route_id: str
    route_code: str
    current: RouteShapeSchema
    optimized: RouteShapeSchema
    saved_metres: float = Field(..., description = 'Negative when nothing improves.')
    saved_seconds: float
    saved_percentage: float = Field(
        ..., description = 'Of the current distance. Zero when it was already optimal.'
    )
    already_optimal: bool = Field(
        ..., description = 'True when the order it has is the one proposed. Worth '
                           'saying out loud: it is the answer that defends the '
                           'route somebody already built.'
    )
