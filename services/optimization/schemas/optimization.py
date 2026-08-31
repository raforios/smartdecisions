'''
    Pydantic V2 DTOs for the Optimization service.

    Mirrors the legacy contract from the monolith (`api/schemas/optimization.py`)
    so that existing notebook clients and the upcoming SmartDecisions demo
    frontend can swap the base URL with no payload changes.
'''
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class OptimizationError(str, Enum):
    '''
        Why a request could not be served. Travels as the error `detail` so the
        client renders its own wording, same contract as INGEST and ANALYTICS.
    '''
    EMPTY_UPLOAD = 'EMPTY_UPLOAD'
    EMPTY_CSV = 'EMPTY_CSV'
    NO_GEOCODED_CLIENTS = 'NO_GEOCODED_CLIENTS'
    EMPTY_PERIOD = 'EMPTY_PERIOD'
    EMPTY_POINT_LIST = 'EMPTY_POINT_LIST'
    MISSING_COORDINATES = 'MISSING_COORDINATES'
    INVALID_ROW = 'INVALID_ROW'
    INVALID_POINT = 'INVALID_POINT'
    ROUTING_SERVICE_UNAVAILABLE = 'ROUTING_SERVICE_UNAVAILABLE'
    ROUTING_SERVICE_NO_ROUTE = 'ROUTING_SERVICE_NO_ROUTE'


class OptimizationQueryParams(BaseModel):
    '''
        Shared query-string contract for all optimization endpoints.

        `dist` is retained for backward compatibility with the legacy OSM-graph
        radius contract; routing now uses OSRM, which resolves the full street
        geometry regardless of this value. The data-extraction endpoints
        ignore it as well.
    '''
    model_config = ConfigDict(extra = 'forbid')

    route_id: int = Field(..., gt = 0, description = 'Identifier of the planned route.')
    day: int = Field(..., ge = 0, description = 'Day index within the route plan.')
    dist: Optional[int] = Field(
        default = 1500,
        ge = 100,
        le = 50000,
        description = 'Legacy OSM graph radius in meters; kept for compatibility, no longer used.'
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


class BulkUploadResponse(BaseModel):
    '''
        Response for POST /v1/optimization/routes/bulk-upload.
    '''
    route_id: int
    day: int
    points_written: int = Field(..., ge = 0)
    columns_detected: list[str] = Field(
        ..., description = 'Headers parsed from the CSV that were recognized.'
    )


class RouteResponse(BaseModel):
    '''
        Final route segment with road-network projection (OSRM).

        `route` is the street polyline that joins the segment endpoints,
        expressed as a list of `[longitude, latitude]` points (GeoJSON order)
        ready to be drawn on a map. `road_distance` and `road_duration` are the
        real driving distance (meters) and duration (seconds) reported by OSRM.
    '''
    origin: int
    target: int
    y: float
    x: float
    y_next: float
    x_next: float
    distance: float
    time_seg: float
    road_distance: float
    road_duration: float
    route: list[list[float]]


# --- Route plan derived from a sales dataset ---

class PlanQueryParams(BaseModel):
    '''
        Filters for GET /v1/optimization/plan/{dataset_id}.

        There is deliberately no route_id or day here: both are derived from the
        clients' own geography, so the module works with any sales export.
    '''
    seller: Optional[str] = Field(
        default = None, max_length = 120,
        description = 'Restrict the plan to one salesperson\'s clients.'
    )
    days: int = Field(
        default = 5, ge = 1, le = 12,
        description = 'How many visit days to spread the clients over.'
    )
    date_from: Optional[str] = Field(
        default = None, pattern = r'^\d{4}-\d{2}-\d{2}$',
        description = 'Inclusive start of the period, YYYY-MM-DD.'
    )
    date_to: Optional[str] = Field(
        default = None, pattern = r'^\d{4}-\d{2}-\d{2}$',
        description = 'Inclusive end of the period, YYYY-MM-DD.'
    )


class RouteStop(BaseModel):
    '''
        One visit. Carries what the rest of the platform knows about the client
        so the rep sees who they are calling on, not just a pin.
    '''
    stop_order: int = Field(..., ge = 1, description = 'Position within the day.')
    client_id: str
    client: str
    latitude: float
    longitude: float
    amount: float = Field(..., description = 'What the client bought in the period (Bs).')
    segment: str = Field(..., description = "'HIGH', 'MEDIUM' or 'LOW'.")
    last_purchase: Optional[str] = None


class DayRoute(BaseModel):
    '''
        A single day of the plan: its ordered stops and the street geometry that
        joins them.
    '''
    day: int = Field(..., ge = 1)
    paradas: list[RouteStop] = []
    distancia_km: float = Field(default = 0.0, description = 'Real driving distance.')
    duracion_min: float = Field(default = 0.0, description = 'Estimated driving time.')
    total_amount: float = Field(default = 0.0, description = 'Value of the day (Bs).')
    geometria: list[list[float]] = Field(
        default_factory = list,
        description = 'Street polyline as [longitude, latitude] pairs; empty when '
                      'the road service could not be reached (the map then draws '
                      'straight lines between stops).'
    )


class RoutePlanResponse(BaseModel):
    '''
        Full visit plan for GET /v1/optimization/plan/{dataset_id}.
    '''
    dataset_id: str
    sellers: list[str] = Field(
        default_factory = list,
        description = 'Salespeople present in the dataset, for the UI selector.'
    )
    seller: Optional[str] = None
    total_clients: int = 0
    days: list[DayRoute] = []
