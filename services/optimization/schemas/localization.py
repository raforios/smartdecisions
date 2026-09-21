'''
    Pydantic V2 DTOs for planned and executed routes.

    Ported from LOCALIZATION. Identifiers are strings (DynamoDB UUIDs instead
    of MySQL integers) and the Binaria tenancy fields (company_id, app_id,
    city_id) are gone: the owner is the authenticated account and the seller is
    the name the sales file uses. Failure reasons travel as codes in
    `LocalizationError`, never as sentences.
'''
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from schemas.daily_stock import SaleItemSchema


class LocalizationError(str, Enum):
    '''
        Why a request could not be served. Goes out as the error `detail` —
        alone, or as the `code` of a dict that also carries the facts (a
        distance and its limit, for instance).
    '''
    ROUTE_NOT_FOUND = 'ROUTE_NOT_FOUND'
    ROUTE_CODE_ALREADY_EXISTS = 'ROUTE_CODE_ALREADY_EXISTS'
    ROUTE_NOT_IN_CREATION = 'ROUTE_NOT_IN_CREATION'
    INVALID_STATUS_TRANSITION = 'INVALID_STATUS_TRANSITION'
    SEQUENCE_ALREADY_EXISTS = 'SEQUENCE_ALREADY_EXISTS'
    POINT_NOT_FOUND = 'POINT_NOT_FOUND'
    START_POINT_NOT_FOUND = 'START_POINT_NOT_FOUND'
    PLANNED_ROUTE_NOT_ACTIVE = 'PLANNED_ROUTE_NOT_ACTIVE'
    OUTSIDE_START_GEOFENCE = 'OUTSIDE_START_GEOFENCE'
    OUTSIDE_END_GEOFENCE = 'OUTSIDE_END_GEOFENCE'
    ROUTE_ALREADY_OPEN = 'ROUTE_ALREADY_OPEN'
    ROUTE_ALREADY_CLOSED = 'ROUTE_ALREADY_CLOSED'
    REOPEN_NOT_SAME_DAY = 'REOPEN_NOT_SAME_DAY'
    EMPTY_UPLOAD = 'EMPTY_UPLOAD'
    INVALID_ROW = 'INVALID_ROW'
    MISSING_COLUMNS = 'MISSING_COLUMNS'
    NO_VISITS_TO_INFER = 'NO_VISITS_TO_INFER'


class TrackingRole(str, Enum):
    '''
        Roles AUTH issues that matter here. ADMIN and MANAGER run the account;
        REQUESTER is what every account signed up with before roles existed, so
        it keeps full rights over its own data; SELLER works the street.
    '''
    ADMIN = 'ADMIN'
    MANAGER = 'MANAGER'
    REQUESTER = 'REQUESTER'
    SELLER = 'SELLER'


class CallerClaims(BaseModel):
    '''
        What the token says about the caller, as the routes need it.
    '''
    email: str
    role: Optional[str] = None
    client: Optional[str] = None


# Who may do what. Management builds plans, loads stock and reads everything;
# the field additionally runs routes, reports visits and reads its plan and
# the stock it can sell from.
MANAGEMENT_ROLES: tuple[str, ...] = (
    TrackingRole.ADMIN.value, TrackingRole.MANAGER.value, TrackingRole.REQUESTER.value
)
FIELD_ROLES: tuple[str, ...] = MANAGEMENT_ROLES + (TrackingRole.SELLER.value,)


class PlannedRouteStatusEnum(str, Enum):
    '''
        Lifecycle of a planned route. Points can only change while the route is
        being built; sellers can only run routes that are active.
    '''
    ACTIVE = 'ACTIVE'
    INACTIVE = 'INACTIVE'
    IN_CREATION = 'IN CREATION'


class VisitOutcome(str, Enum):
    '''
        What came of a visit. Same vocabulary as the `Resultado` column of the
        Visitas sheet INGEST validates, so history and live data agree.
    '''
    SALE = 'VENTA'
    NO_SALE = 'SIN_VENTA'
    CLOSED = 'CERRADO'
    NOT_FOUND = 'NO_ENCONTRADO'


class PointBase(BaseModel):
    '''
        A geographical point.
    '''
    latitude: float = Field(..., ge = -90.0, le = 90.0)
    longitude: float = Field(..., ge = -180.0, le = 180.0)


# ---------------------------------------------------------------------------
# Planned routes
# ---------------------------------------------------------------------------
class PlannedPointSchema(PointBase):
    '''
        A stop of a planned route, as the client describes it.
    '''
    point_name: str = Field(..., max_length = 100)
    secuencial: int = Field(..., gt = 0, description = 'Visiting order within the route.')
    reference_data: Optional[str] = Field(None, max_length = 255)
    client_id: Optional[str] = Field(
        None, max_length = 64,
        description = 'Client identifier as it appears in the sales file, when the '
                      'stop is a known client.'
    )


class PlannedPointResponseSchema(PlannedPointSchema):
    '''
        A stored stop.
    '''
    id: str
    planned_route_id: str


class PlannedPointRef(BaseModel):
    '''
        Addresses one stop of one route (path parameters, grouped so the
        controllers stay within five arguments).
    '''
    planned_route_id: str
    planned_point_id: str


class PlannedPointUpdateSchema(BaseModel):
    '''
        Partial update of a stop.
    '''
    secuencial: Optional[int] = Field(None, gt = 0)
    point_name: Optional[str] = Field(None, max_length = 100)
    reference_data: Optional[str] = Field(None, max_length = 255)
    client_id: Optional[str] = Field(None, max_length = 64)


class PlannedRouteCreateSchema(BaseModel):
    '''
        A route with its stops, created in one call.
    '''
    route_name: str = Field(..., max_length = 150)
    route_code: str = Field(..., max_length = 50, description = 'Unique per owner.')
    description: Optional[str] = Field(None, max_length = 500)
    seller: Optional[str] = Field(
        None, max_length = 128,
        description = 'Salesperson the route is assigned to, by name.'
    )
    points: List[PlannedPointSchema] = Field(..., min_length = 1)


class PlannedRouteResponseSchema(BaseModel):
    '''
        A stored route with its stops.
    '''
    id: str
    route_name: str
    route_code: str
    description: Optional[str] = None
    seller: Optional[str] = None
    status: PlannedRouteStatusEnum
    created_at: str
    points: List[PlannedPointResponseSchema]


class PlannedRouteUpdateSchema(BaseModel):
    '''
        Partial update of a route's header.
    '''
    route_name: Optional[str] = Field(None, max_length = 150)
    route_code: Optional[str] = Field(None, max_length = 50)
    description: Optional[str] = Field(None, max_length = 500)
    seller: Optional[str] = Field(None, max_length = 128)


class PlannedRouteUpdateStatusSchema(BaseModel):
    '''
        Status change request.
    '''
    status: PlannedRouteStatusEnum


class PlannedRouteFilterRequestSchema(BaseModel):
    '''
        Filters for POST /routes/planned/filter. All optional, all combined.
    '''
    planned_route_ids: Optional[List[str]] = None
    route_code: Optional[str] = None
    route_name: Optional[str] = Field(None, description = 'Case-insensitive substring.')
    route_status: Optional[PlannedRouteStatusEnum] = None
    seller: Optional[str] = None


class PlannedRouteBulkRowSchema(PointBase):
    '''
        One CSV row of a bulk upload: route header repeated on every stop.
    '''
    route_name: str = Field(..., max_length = 150)
    route_code: str = Field(..., max_length = 50)
    description: Optional[str] = Field(None, max_length = 500)
    seller: Optional[str] = Field(None, max_length = 128)
    point_name: str = Field(..., max_length = 100)
    secuencial: int = Field(..., gt = 0)
    reference_data: Optional[str] = Field(None, max_length = 255)
    client_id: Optional[str] = Field(None, max_length = 64)


class InferPlannedRouteSchema(BaseModel):
    '''
        Build the plan from what a seller actually visited on a day, when no
        plan was loaded or created beforehand. The visits become the stops, in
        the order they happened, and the day's executions get linked to the
        new plan so they can be compared.
    '''
    seller: str = Field(..., max_length = 128)
    date: str = Field(..., pattern = r'^\d{4}-\d{2}-\d{2}$', description = 'YYYY-MM-DD.')
    route_code: Optional[str] = Field(
        None, max_length = 50, description = 'Defaults to "{seller}-{date}".'
    )
    route_name: Optional[str] = Field(
        None, max_length = 150, description = 'Defaults to the route code.'
    )


class BulkUploadPlannedResponseSchema(BaseModel):
    '''
        What a bulk upload created.
    '''
    routes_created: int
    points_created: int
    route_ids: List[str] = []


# ---------------------------------------------------------------------------
# Executed routes
# ---------------------------------------------------------------------------
class ExecutedRouteCreateSchema(BaseModel):
    '''
        A seller starts running a route. If it follows a planned one, the start
        must be within `max_distance_start_point` metres of its first stop.
    '''
    seller: str = Field(..., max_length = 128)
    start_time: str = Field(..., description = 'ISO 8601 as sent by the device.')
    planned_route_id: Optional[str] = None
    start_latitude: float = Field(..., ge = -90.0, le = 90.0)
    start_longitude: float = Field(..., ge = -180.0, le = 180.0)
    max_distance_start_point: float = Field(..., gt = 0, description = 'Metres.')


class ExecutedRouteResponseSchema(ExecutedRouteCreateSchema):
    '''
        A stored executed route.
    '''
    id: str
    end_time: Optional[str] = None
    end_latitude: Optional[float] = None
    end_longitude: Optional[float] = None
    max_distance_end_point: Optional[float] = None
    points_count: int = 0


class ExecutedRouteUpdateSchema(BaseModel):
    '''
        The seller closes the route. If it follows a planned one, the end must be
        within `max_distance_end_point` metres of its last stop.
    '''
    end_time: str
    end_latitude: float = Field(..., ge = -90.0, le = 90.0)
    end_longitude: float = Field(..., ge = -180.0, le = 180.0)
    max_distance_end_point: float = Field(..., gt = 0, description = 'Metres.')


class ExecutedPointCreateSchema(PointBase):
    '''
        A position reported from the device — and, when it is a visit, who was
        visited and what came of it.
    '''
    executed_route_id: str
    timestamp: str = Field(..., description = 'ISO 8601 as sent by the device.')
    client_id: Optional[str] = Field(None, max_length = 64)
    outcome: Optional[VisitOutcome] = None
    order_id: Optional[str] = Field(None, max_length = 64)
    items: List[SaleItemSchema] = Field(
        default_factory = list,
        description = 'Lines sold on this visit; each draws from the day\'s stock, '
                      'all or none.'
    )


class ExecutedPointResponseSchema(ExecutedPointCreateSchema):
    '''
        A stored position.
    '''
    id: str


class ExecutedRouteFilterSchema(BaseModel):
    '''
        Filters for listing executed routes. Dates bound the start of the
        route, inclusive, YYYY-MM-DD.
    '''
    seller: Optional[str] = Field(None, max_length = 128)
    planned_route_id: Optional[str] = None
    date_from: Optional[str] = Field(None, pattern = r'^\d{4}-\d{2}-\d{2}$')
    date_to: Optional[str] = Field(None, pattern = r'^\d{4}-\d{2}-\d{2}$')


class ExecutedRouteDetailSchema(ExecutedRouteResponseSchema):
    '''
        An executed route with every position it reported.
    '''
    points: List[ExecutedPointResponseSchema] = []


# ---------------------------------------------------------------------------
# Comparison and statistics
# ---------------------------------------------------------------------------
class PlannedRouteComparisonSchema(BaseModel):
    '''
        The planned side of a comparison.
    '''
    id: str
    route_name: str
    seller: Optional[str] = None
    points: List[PlannedPointResponseSchema]


class RouteComparisonFullResponseSchema(BaseModel):
    '''
        A planned route and every execution of it, points included, for the map.
    '''
    planned_route: PlannedRouteComparisonSchema
    executed_routes: List[ExecutedRouteDetailSchema]


class RouteComparisonSchema(BaseModel):
    '''
        How one execution measured up against its plan.
    '''
    planned_route_id: str
    planned_route_name: str
    executed_route_id: str
    seller: str
    match_percentage: float = Field(
        ..., ge = 0.0, le = 100.0,
        description = 'Share of planned stops that got a visit within the geofence.'
    )
    planned_points_count: int
    points_visited_count: int
    matched_points_count: int


class RouteComparisonsResponseSchema(BaseModel):
    '''
        Every execution of a planned route, scored.
    '''
    comparisons: List[RouteComparisonSchema]


class PointsVisitedResponseSchema(BaseModel):
    '''
        Positions a seller reported in a period.
    '''
    seller: str
    total_points_visited: int
    points_details: List[ExecutedPointResponseSchema]


class LastKnownLocationResponseSchema(BaseModel):
    '''
        Where a seller last reported from.
    '''
    seller: str
    executed_route_id: str
    last_latitude: float
    last_longitude: float
    last_timestamp: str


class GroupLastKnownLocationsResponseSchema(BaseModel):
    '''
        Last position of each requested seller.
    '''
    locations: List[LastKnownLocationResponseSchema]
