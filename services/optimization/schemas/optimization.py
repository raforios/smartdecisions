'''
    Pydantic V2 DTOs for the Optimization service.

    Mirrors the legacy contract from the monolith (`api/schemas/optimization.py`)
    so that existing notebook clients and the upcoming SmartDecisions demo
    frontend can swap the base URL with no payload changes.
'''
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class OptimizationQueryParams(BaseModel):
    '''
        Shared query-string contract for all optimization endpoints.

        `dist` is only consumed by the optimization-algorithm endpoints
        (`/optimal_route`, `/route`) where the road-network radius matters;
        the data-extraction endpoints ignore it.
    '''
    model_config = ConfigDict(extra = 'forbid')

    route_id: int = Field(..., gt = 0, description = 'Identifier of the planned route.')
    day: int = Field(..., ge = 0, description = 'Day index within the route plan.')
    dist: Optional[int] = Field(
        default = 1500,
        ge = 100,
        le = 50000,
        description = 'OSM graph radius in meters (only used by optimal_route and route).'
    )


class DataMapResponse(BaseModel):
    '''
        Raw geolocated client point for the base data map.

        Fields mirror the legacy `api/schemas/optimization.py:DataMapResponse`
        to preserve the notebook contract.
    '''
    day: int
    client_id: int
    y: float = Field(..., description = 'Latitude.')
    x: float = Field(..., description = 'Longitude.')
    color: str = Field(..., description = "'red' for start, 'green' for end, 'black' otherwise.")


class OptimizationResponse(BaseModel):
    '''
        Pair (origin, target) of clients with the linear distance and the
        target coordinates. Used by `/distances` and `/optimal_route`.
    '''
    origin: int
    target: int
    distance: float
    y: float
    x: float


class RouteResponse(BaseModel):
    '''
        Final route segment with road-network projection.

        `route` is the list of OSM node ids that compose the shortest path
        between origin_node and destination_node.
    '''
    origin: int
    target: int
    y: float
    x: float
    y_next: float
    x_next: float
    distance: float
    time_seg: float
    origin_node: int
    destination_node: int
    route: list[int]
