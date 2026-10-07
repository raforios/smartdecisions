'''
    Pydantic V2 DTOs for planned and executed routes.

    Ported from LOCALIZATION. Identifiers are strings (DynamoDB UUIDs instead
    of MySQL integers) and the Binaria tenancy fields (company_id, app_id,
    city_id) are gone: the owner is the authenticated account and the seller is
    the name the sales file uses. Failure reasons travel as codes in
    `LocalizationError`, never as sentences.
'''
from datetime import date
from enum import Enum
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
    OUTSIDE_STOP_GEOFENCE = 'OUTSIDE_STOP_GEOFENCE'
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
    role: str | None = None
    client: str | None = None


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
    reference_data: str | None = Field(None, max_length = 255)
    client_id: str | None = Field(
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
    secuencial: int | None = Field(None, gt = 0)
    point_name: str | None = Field(None, max_length = 100)
    reference_data: str | None = Field(None, max_length = 255)
    client_id: str | None = Field(None, max_length = 64)


class RouteEndpointSchema(BaseModel):
    '''
        Where a route starts or ends, when the plan fixes it. Optional on
        purpose: start and end are open per route, and a plan without them
        starts and ends wherever the seller is.
    '''
    name: str = Field(..., min_length = 1, max_length = 100)
    latitude: float = Field(..., ge = -90.0, le = 90.0)
    longitude: float = Field(..., ge = -180.0, le = 180.0)


class PlannedRouteCreateSchema(BaseModel):
    '''
        A route with its stops, created in one call.
    '''
    route_name: str = Field(..., max_length = 150)
    route_code: str = Field(..., max_length = 50, description = 'Unique per owner.')
    description: str | None = Field(None, max_length = 500)
    seller: str | None = Field(
        None, max_length = 128,
        description = 'Salesperson the route is assigned to, by name.'
    )
    plan_date: date | None = Field(
        None,
        description = 'The day the route is meant to be run. Optional, because a '
                      'route can also be a reusable template with no date; what '
                      'carries one is a plan for a given day.'
    )
    points: list[PlannedPointSchema] = Field(..., min_length = 1)
    start_point: RouteEndpointSchema | None = None
    end_point: RouteEndpointSchema | None = None


class PlannedRouteResponseSchema(BaseModel):
    '''
        A stored route with its stops.
    '''
    id: str
    route_name: str
    route_code: str
    description: str | None = None
    seller: str | None = None
    plan_date: str | None = None
    status: PlannedRouteStatusEnum
    created_at: str
    points: list[PlannedPointResponseSchema]
    start_point: RouteEndpointSchema | None = None
    end_point: RouteEndpointSchema | None = None


class PlannedRouteUpdateSchema(BaseModel):
    '''
        Partial update of a route's header.
    '''
    route_name: str | None = Field(None, max_length = 150)
    route_code: str | None = Field(None, max_length = 50)
    description: str | None = Field(None, max_length = 500)
    seller: str | None = Field(None, max_length = 128)
    plan_date: date | None = None


class RepeatPlannedRouteSchema(BaseModel):
    """
        What to change when a route is run again.

        The stops are what a route IS, so repeating one copies them whole and
        asks only for what changes: the day and, when it is somebody else's
        turn, the seller. It answers the "duplicar o repetir ruta" the history
        screen needs, instead of making somebody retype thirty stops.
    """
    plan_date: date
    seller: str | None = Field(None, max_length = 128)
    route_code: str | None = Field(
        None, max_length = 50,
        description = 'Code of the new route. Left out, the original code is '
                      'suffixed with the date, which is unique per owner.'
    )
    optimized: bool = Field(
        False,
        description = 'Whether the stops are reordered into the shortest route '
                      'before the new plan is created. The reordering happens '
                      'here and not on the screen, so what is accepted cannot '
                      'drift from what was proposed.'
    )


class PlannedRouteUpdateStatusSchema(BaseModel):
    '''
        Status change request.
    '''
    status: PlannedRouteStatusEnum


class PlannedRouteFilterRequestSchema(BaseModel):
    '''
        Filters for POST /routes/planned/filter. All optional, all combined.
    '''
    planned_route_ids: list[str] | None = None
    route_code: str | None = None
    route_name: str | None = Field(None, description = 'Case-insensitive substring.')
    route_status: PlannedRouteStatusEnum | None = None
    seller: str | None = None
    # The window the caller is asking about. What separates "what is coming"
    # from "what already happened": the planning screen asks from today on,
    # the history screen asks backwards. Without a date on the plan there was
    # no way to tell one from the other, and the past was shown as a plan.
    date_from: date | None = None
    date_to: date | None = None
    undated: bool = Field(
        True,
        description = 'Whether routes with no date —the reusable templates— come '
                      'back too. They belong to no window, so a date filter would '
                      'otherwise hide them for good.'
    )


class PlannedRouteBulkRowSchema(PointBase):
    '''
        One CSV row of a bulk upload: route header repeated on every stop.
    '''
    route_name: str = Field(..., max_length = 150)
    route_code: str = Field(..., max_length = 50)
    plan_date: date | None = None
    description: str | None = Field(None, max_length = 500)
    seller: str | None = Field(None, max_length = 128)
    point_name: str = Field(..., max_length = 100)
    secuencial: int = Field(..., gt = 0)
    reference_data: str | None = Field(None, max_length = 255)
    client_id: str | None = Field(None, max_length = 64)


class InferPlannedRouteSchema(BaseModel):
    '''
        Build the plan from what a seller actually visited on a day, when no
        plan was loaded or created beforehand. The visits become the stops, in
        the order they happened, and the day's executions get linked to the
        new plan so they can be compared.
    '''
    seller: str = Field(..., max_length = 128)
    date: str = Field(..., pattern = r'^\d{4}-\d{2}-\d{2}$', description = 'YYYY-MM-DD.')
    route_code: str | None = Field(
        None, max_length = 50, description = 'Defaults to "{seller}-{date}".'
    )
    route_name: str | None = Field(
        None, max_length = 150, description = 'Defaults to the route code.'
    )


class BulkUploadPlannedResponseSchema(BaseModel):
    '''
        What a bulk upload created.
    '''
    routes_created: int
    points_created: int
    route_ids: list[str] = []


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
    planned_route_id: str | None = None
    start_latitude: float = Field(..., ge = -90.0, le = 90.0)
    start_longitude: float = Field(..., ge = -180.0, le = 180.0)
    max_distance_start_point: float = Field(..., gt = 0, description = 'Metres.')


class ExecutedRouteResponseSchema(ExecutedRouteCreateSchema):
    '''
        A stored executed route.
    '''
    id: str
    end_time: str | None = None
    end_latitude: float | None = None
    end_longitude: float | None = None
    max_distance_end_point: float | None = None
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
    client_id: str | None = Field(None, max_length = 64)
    outcome: VisitOutcome | None = None
    order_id: str | None = Field(None, max_length = 64)
    items: list[SaleItemSchema] = Field(
        default_factory = list,
        description = 'Lines sold on this visit; each draws from the day\'s stock, '
                      'all or none.'
    )
    max_distance_stop_point: float | None = Field(
        None, gt = 0,
        description = 'Metres accepted between this reading and the planned stop '
                      'it claims to be at. Optional: a device that knows how good '
                      'its own fix is may tighten or loosen it, and everything '
                      'already deployed keeps working. Left out, the radius the '
                      'operation configured applies.'
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
    seller: str | None = Field(None, max_length = 128)
    planned_route_id: str | None = None
    date_from: str | None = Field(None, pattern = r'^\d{4}-\d{2}-\d{2}$')
    date_to: str | None = Field(None, pattern = r'^\d{4}-\d{2}-\d{2}$')


class ExecutedRouteDetailSchema(ExecutedRouteResponseSchema):
    '''
        An executed route with every position it reported.
    '''
    points: list[ExecutedPointResponseSchema] = []


# ---------------------------------------------------------------------------
# Comparison and statistics
# ---------------------------------------------------------------------------
class PlannedRouteComparisonSchema(BaseModel):
    '''
        The planned side of a comparison.
    '''
    id: str
    route_name: str
    seller: str | None = None
    points: list[PlannedPointResponseSchema]


class RouteComparisonFullResponseSchema(BaseModel):
    '''
        A planned route and every execution of it, points included, for the map.
    '''
    planned_route: PlannedRouteComparisonSchema
    executed_routes: list[ExecutedRouteDetailSchema]


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
    comparisons: list[RouteComparisonSchema]


class PointsVisitedResponseSchema(BaseModel):
    '''
        Positions a seller reported in a period.
    '''
    seller: str
    total_points_visited: int
    points_details: list[ExecutedPointResponseSchema]


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
    locations: list[LastKnownLocationResponseSchema]
