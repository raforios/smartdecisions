'''
    Executed routes — business logic, ported from LOCALIZATION onto DynamoDB.

    An executed route is what a seller actually ran: opened at a position,
    fed with the positions and visits reported along the day, closed at a
    position. When it follows a planned route, the start must be near the
    plan's first stop and the end near its last one, within the distance the
    device declares.

    The sort key of the table starts with the start time, so "today's routes",
    "this week's routes" and "where is everybody now" are bounded Queries on
    the owner's partition.
'''
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from boto3.resources.base import ServiceResource

from models.localization import (
    ExecutedPointItem,
    ExecutedRouteItem,
    PlannedPointItem,
    PlannedRouteItem
)
from schemas.localization import (
    ExecutedPointCreateSchema,
    ExecutedPointResponseSchema,
    ExecutedRouteCreateSchema,
    ExecutedRouteDetailSchema,
    ExecutedRouteFilterSchema,
    ExecutedRouteResponseSchema,
    ExecutedRouteUpdateSchema,
    LastKnownLocationResponseSchema,
    LocalizationError,
    PlannedRouteStatusEnum
)
from services.common import calculate_distance, from_dynamo, new_id, to_dynamo
from services.crud import get_item_by_key, put_unique_composite_item, query_by_partition
from services.daily_stock import draw_down_stock
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.localization import get_planned_route
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

_SETTINGS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_OPTIMIZATION_EXECUTED_ROUTES': str,
    'ROUTES_LIVE_LOOKBACK_DAYS': int
})
EXECUTED_ROUTES_TABLE = _SETTINGS['DYNAMODB_TABLE_NAME_OPTIMIZATION_EXECUTED_ROUTES']
LIVE_LOOKBACK_DAYS = _SETTINGS['ROUTES_LIVE_LOOKBACK_DAYS']

# Sort-key prefix: compact timestamp, lexicographically ordered like the dates.
_ID_STAMP = '%Y%m%dT%H%M%S'


# ---------------------------------------------------------------------------
# Keys and conversions
# ---------------------------------------------------------------------------
def parse_timestamp(value: str) -> datetime:
    '''
        The ISO 8601 stamp a device sent, or INVALID_ROW.

        Args:
            value (str): Timestamp as received.

        Returns:
            datetime: Parsed value.

        Raises:
            InvalidInputError: If `value` is not ISO 8601.
    '''
    try:
        return datetime.fromisoformat(value)
    except ValueError as error:
        error_msg = f'Timestamp is not ISO 8601: {value!r}.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = LocalizationError.INVALID_ROW.value) from error


def build_executed_id(start_time: str) -> str:
    '''
        Sort key of an executed route: its start time stamp plus a short random
        suffix, so routes sort by start and two starts in the same second do
        not collide.

        Args:
            start_time (str): ISO 8601 start time as the device sent it.

        Returns:
            str: Key such as "20260920T083000-3f9a1c2b".
    '''
    return f'{parse_timestamp(start_time).strftime(_ID_STAMP)}-{new_id()[:8]}'


def _day_bounds(
    date_from: Optional[str],
    date_to: Optional[str]
) -> Optional[Dict[str, str]]:
    '''
        Sort-key bounds for a date range: "YYYYMMDD" sorts before every key of
        that day and "YYYYMMDD~" after every key of that day.
    '''
    bounds: Dict[str, str] = {}
    if date_from:
        bounds['from'] = date_from.replace('-', '')
    if date_to:
        bounds['to'] = date_to.replace('-', '') + '~'
    return bounds or None


def to_executed_response(route: ExecutedRouteItem) -> ExecutedRouteResponseSchema:
    '''
        Executed route item -> header DTO.

        Args:
            route (ExecutedRouteItem): Stored route.

        Returns:
            ExecutedRouteResponseSchema: The route without its points.
    '''
    fields = {key: value for key, value in route.items() if key not in ('owner_email', 'points')}
    fields.pop('last_latitude', None)
    fields.pop('last_longitude', None)
    fields.pop('last_timestamp', None)
    return ExecutedRouteResponseSchema(points_count = len(route.get('points', [])), **fields)


def to_executed_point_response(
    route_id: str,
    point: ExecutedPointItem
) -> ExecutedPointResponseSchema:
    '''
        Executed point item -> DTO.

        Args:
            route_id (str): Route the point belongs to.
            point (ExecutedPointItem): Stored point.

        Returns:
            ExecutedPointResponseSchema: The point as the API returns it.
    '''
    return ExecutedPointResponseSchema(executed_route_id = route_id, **point)


def to_executed_detail(route: ExecutedRouteItem) -> ExecutedRouteDetailSchema:
    '''
        Executed route item -> DTO with every point.

        Args:
            route (ExecutedRouteItem): Stored route.

        Returns:
            ExecutedRouteDetailSchema: The route and its points.
    '''
    header = to_executed_response(route).model_dump()
    return ExecutedRouteDetailSchema(
        points = [to_executed_point_response(route['id'], point)
                  for point in route.get('points', [])],
        **header
    )


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------
def get_executed_route(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    executed_route_id: str
) -> ExecutedRouteItem:
    '''
        Reads one of the owner's executed routes. Somebody else's is not found.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            executed_route_id (str): Route identifier.

        Returns:
            ExecutedRouteItem: The route item with native numbers.
    '''
    try:
        item = get_item_by_key(
            dynamodb_resource = dynamodb_resource,
            table_name = EXECUTED_ROUTES_TABLE,
            key = {'owner_email': owner_email, 'id': executed_route_id}
        )
    except RegisterNotFoundError as error:
        raise RegisterNotFoundError(detail = LocalizationError.ROUTE_NOT_FOUND.value) from error
    return from_dynamo(item)


def list_executed_routes(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    filters: ExecutedRouteFilterSchema
) -> List[ExecutedRouteItem]:
    '''
        The owner's executed routes in a date range, then narrowed by seller
        and planned route. Oldest first.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            filters (ExecutedRouteFilterSchema): Optional criteria.

        Returns:
            List[ExecutedRouteItem]: Matching route items.
    '''
    items = from_dynamo(query_by_partition(
        dynamodb_resource = dynamodb_resource,
        table_name = EXECUTED_ROUTES_TABLE,
        partition_key = 'owner_email',
        partition_value = owner_email,
        sort_key = 'id',
        sort_between = _day_bounds(filters.date_from, filters.date_to)
    ))
    if filters.seller:
        items = [route for route in items if route['seller'] == filters.seller]
    if filters.planned_route_id:
        items = [route for route in items
                 if route.get('planned_route_id') == filters.planned_route_id]
    return sorted(items, key = lambda route: route['id'])


def _save_executed_route(
    dynamodb_resource: ServiceResource,
    item: ExecutedRouteItem
) -> ExecutedRouteItem:
    '''
        Writes a route back after a change (full replace of the item).
    '''
    table = dynamodb_resource.Table(EXECUTED_ROUTES_TABLE)
    table.put_item(Item = to_dynamo(item))
    return item


def _assert_open(route: ExecutedRouteItem) -> None:
    '''
        Raises if the route was already closed.
    '''
    if route.get('end_time'):
        error_msg = f'Executed route {route["id"]} is already closed.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = LocalizationError.ROUTE_ALREADY_CLOSED.value)


def _active_plan(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    planned_route_id: str
) -> PlannedRouteItem:
    '''
        The planned route a seller wants to run: it must exist for this owner
        and be ACTIVE.
    '''
    plan = get_planned_route(dynamodb_resource, owner_email, planned_route_id)
    if plan['status'] != PlannedRouteStatusEnum.ACTIVE.value:
        error_msg = f'Planned route {planned_route_id} is {plan["status"]}, not ACTIVE.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = LocalizationError.PLANNED_ROUTE_NOT_ACTIVE.value)
    return plan


def _assert_within(
    stop: Optional[PlannedPointItem],
    position: Tuple[float, float],
    limit_m: float,
    code: LocalizationError
) -> None:
    '''
        Raises `code` when `position` is farther than `limit_m` metres from `stop`.
        A plan without stops cannot be geofenced.
    '''
    if stop is None:
        raise RegisterNotFoundError(detail = LocalizationError.START_POINT_NOT_FOUND.value)
    distance = calculate_distance(position[0], position[1], stop['latitude'], stop['longitude'])
    if distance > limit_m:
        error_msg = f'Position is {distance:.0f} m from the stop; limit {limit_m:.0f} m.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = code.value)


def _first_and_last_stop(
    plan: PlannedRouteItem
) -> Tuple[Optional[PlannedPointItem], Optional[PlannedPointItem]]:
    '''
        The plan's stops with the lowest and highest visiting order.
    '''
    stops = sorted(plan.get('points', []), key = lambda stop: stop['secuencial'])
    if not stops:
        return None, None
    return stops[0], stops[-1]


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def create_executed_route(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    route_data: ExecutedRouteCreateSchema
) -> ExecutedRouteItem:
    '''
        A seller starts a route. Against a plan, the plan must be ACTIVE and
        the start within the declared distance of its first stop.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            route_data (ExecutedRouteCreateSchema): Start of the route.

        Returns:
            ExecutedRouteItem: The stored route.
    '''
    if route_data.planned_route_id:
        plan = _active_plan(dynamodb_resource, owner_email, route_data.planned_route_id)
        first_stop, _ = _first_and_last_stop(plan)
        _assert_within(
            first_stop,
            (route_data.start_latitude, route_data.start_longitude),
            route_data.max_distance_start_point,
            LocalizationError.OUTSIDE_START_GEOFENCE
        )
    item: ExecutedRouteItem = {
        'owner_email': owner_email,
        'id': build_executed_id(route_data.start_time),
        **route_data.model_dump(),
        'end_time': None,
        'end_latitude': None,
        'end_longitude': None,
        'max_distance_end_point': None,
        'last_latitude': route_data.start_latitude,
        'last_longitude': route_data.start_longitude,
        'last_timestamp': route_data.start_time,
        'points': []
    }
    put_unique_composite_item(
        dynamodb_resource = dynamodb_resource,
        table_name = EXECUTED_ROUTES_TABLE,
        item_data = item,
        partition_key = 'owner_email',
        sort_key = 'id'
    )
    message = f'Executed route {item["id"]} opened by {route_data.seller}.'
    logger.info(message)
    return item


def register_executed_point(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    point_data: ExecutedPointCreateSchema
) -> Tuple[ExecutedRouteItem, ExecutedPointItem]:
    '''
        The device reports a position — a visit when it names the client and
        what came of it, a sale when it carries lines. The route must still be
        open; its last known position moves here; the lines draw from the
        day's stock first.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            point_data (ExecutedPointCreateSchema): The report.

        Returns:
            Tuple[ExecutedRouteItem, ExecutedPointItem]: Updated route and new point.
    '''
    route = get_executed_route(dynamodb_resource, owner_email, point_data.executed_route_id)
    _assert_open(route)
    # The sale draws from the company's stock of the day the visit happened;
    # if the units are not there the visit is not recorded either, so the
    # seller learns it on the spot and does not promise what cannot ship.
    draw_down_stock(
        dynamodb_resource = dynamodb_resource,
        owner_email = owner_email,
        day = parse_timestamp(point_data.timestamp).date().isoformat(),
        items = point_data.items
    )
    point: ExecutedPointItem = {
        'id': new_id(),
        **point_data.model_dump(exclude = {'executed_route_id'}, mode = 'json')
    }
    route.setdefault('points', []).append(point)
    route['last_latitude'] = point['latitude']
    route['last_longitude'] = point['longitude']
    route['last_timestamp'] = point['timestamp']
    _save_executed_route(dynamodb_resource, route)
    message = f'Point {point["id"]} registered on executed route {route["id"]}.'
    logger.info(message)
    return route, point


def close_executed_route(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    executed_route_id: str,
    update_data: ExecutedRouteUpdateSchema
) -> ExecutedRouteItem:
    '''
        The seller ends the route. Against a plan, the end must be within the
        declared distance of its last stop.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            executed_route_id (str): Route identifier.
            update_data (ExecutedRouteUpdateSchema): End of the route.

        Returns:
            ExecutedRouteItem: The closed route.
    '''
    route = get_executed_route(dynamodb_resource, owner_email, executed_route_id)
    _assert_open(route)
    if route.get('planned_route_id'):
        plan = get_planned_route(dynamodb_resource, owner_email, route['planned_route_id'])
        _, last_stop = _first_and_last_stop(plan)
        _assert_within(
            last_stop,
            (update_data.end_latitude, update_data.end_longitude),
            update_data.max_distance_end_point,
            LocalizationError.OUTSIDE_END_GEOFENCE
        )
    route.update(update_data.model_dump())
    _save_executed_route(dynamodb_resource, route)
    message = f'Executed route {executed_route_id} closed at {update_data.end_time}.'
    logger.info(message)
    return route


def reopen_executed_route(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    executed_route_id: str
) -> ExecutedRouteItem:
    '''
        Undoes a close made by mistake: only the same day it started, only if
        its plan (when any) is still ACTIVE.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            executed_route_id (str): Route identifier.

        Returns:
            ExecutedRouteItem: The reopened route.
    '''
    route = get_executed_route(dynamodb_resource, owner_email, executed_route_id)
    if not route.get('end_time'):
        error_msg = f'Executed route {executed_route_id} is already open.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = LocalizationError.ROUTE_ALREADY_OPEN.value)
    started = datetime.fromisoformat(route['start_time']).date()
    if started != get_current_time_gmt().date():
        error_msg = f'Executed route {executed_route_id} started on {started}; reopen refused.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = LocalizationError.REOPEN_NOT_SAME_DAY.value)
    if route.get('planned_route_id'):
        _active_plan(dynamodb_resource, owner_email, route['planned_route_id'])
    route.update({
        'end_time': None,
        'end_latitude': None,
        'end_longitude': None,
        'max_distance_end_point': None
    })
    _save_executed_route(dynamodb_resource, route)
    message = f'Executed route {executed_route_id} reopened.'
    logger.info(message)
    return route


def link_routes_to_plan(
    dynamodb_resource: ServiceResource,
    routes: List[ExecutedRouteItem],
    planned_route_id: str
) -> int:
    '''
        Points executed routes that ran without a plan at the plan later
        inferred from them, so they can be compared like any other.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            routes (List[ExecutedRouteItem]): Executed route items (already the owner's).
            planned_route_id (str): The inferred plan.

        Returns:
            int: How many routes were linked (those that had no plan).
    '''
    linked = 0
    for route in routes:
        if route.get('planned_route_id'):
            continue
        route['planned_route_id'] = planned_route_id
        _save_executed_route(dynamodb_resource, route)
        linked += 1
    message = f'Linked {linked} executed route(s) to planned route {planned_route_id}.'
    logger.info(message)
    return linked


# ---------------------------------------------------------------------------
# Live view
# ---------------------------------------------------------------------------
def last_known_locations(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    sellers: List[str]
) -> List[LastKnownLocationResponseSchema]:
    '''
        Where each requested seller last reported from, looking back
        `ROUTES_LIVE_LOOKBACK_DAYS` days so a route left open on Friday still
        shows on Monday. Sellers with nothing in the window are omitted.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            sellers (List[str]): Sellers to locate.

        Returns:
            List[LastKnownLocationResponseSchema]: One entry per located seller.
    '''
    today = get_current_time_gmt().date()
    window = ExecutedRouteFilterSchema(
        date_from = (today - timedelta(days = LIVE_LOOKBACK_DAYS)).isoformat(),
        date_to = today.isoformat()
    )
    wanted = set(sellers)
    latest: Dict[str, Dict[str, Any]] = {}
    for route in list_executed_routes(dynamodb_resource, owner_email, window):
        if route['seller'] not in wanted or not route.get('last_timestamp'):
            continue
        current = latest.get(route['seller'])
        if current is None or route['last_timestamp'] > current['last_timestamp']:
            latest[route['seller']] = route
    message = (
        f'Located {len(latest)} of {len(wanted)} sellers in the last {LIVE_LOOKBACK_DAYS} days.'
    )
    logger.info(message)
    return [
        LastKnownLocationResponseSchema(
            seller = seller,
            executed_route_id = route['id'],
            last_latitude = route['last_latitude'],
            last_longitude = route['last_longitude'],
            last_timestamp = route['last_timestamp']
        )
        for seller, route in sorted(latest.items())
    ]
