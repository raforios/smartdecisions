'''
    Planned routes — business logic, ported from LOCALIZATION onto DynamoDB.

    A planned route is created in the app, uploaded from another system, or
    derived from what the sellers actually visited. Its stops live inside the
    route item, so every operation here is: read the owner's route, check the
    rule, write the route back.

    Rules kept from LOCALIZATION:
      - `route_code` is unique per owner.
      - Stops can only be added, edited or removed while the route is
        IN CREATION; a route is deleted only in that state.
      - Status moves IN CREATION -> ACTIVE, then ACTIVE <-> INACTIVE.
'''
from typing import Any, Dict, List, Optional, Tuple

from boto3.resources.base import ServiceResource

from models.localization import PlannedPointItem, PlannedRouteItem

from schemas.localization import (
    LocalizationError,
    PlannedPointResponseSchema,
    PlannedPointSchema,
    PlannedPointUpdateSchema,
    PlannedRouteCreateSchema,
    PlannedRouteFilterRequestSchema,
    PlannedRouteResponseSchema,
    PlannedRouteStatusEnum,
    PlannedRouteUpdateSchema
)
from services.common import from_dynamo, new_id, now_iso, to_dynamo
from services.crud import get_item_by_key, put_unique_composite_item, query_by_partition
from services.environment import load_and_validate_env_vars
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from services.logger_config import custom_logger as logger

_SETTINGS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_OPTIMIZATION_PLANNED_ROUTES': str,
    'STOP_POSITION_DECIMALS': int
})
PLANNED_ROUTES_TABLE = _SETTINGS['DYNAMODB_TABLE_NAME_OPTIMIZATION_PLANNED_ROUTES']
# How close two readings have to be to count as the same stop when neither
# names a client. A decision —it is the difference between one shop and two—
# so it lives in the environment.
_STOP_POSITION_DECIMALS = _SETTINGS['STOP_POSITION_DECIMALS']

# Where a route may go from each status. IN CREATION only opens; ACTIVE and
# INACTIVE toggle each other.
_ALLOWED_TRANSITIONS: Dict[PlannedRouteStatusEnum, Tuple[PlannedRouteStatusEnum, ...]] = {
    PlannedRouteStatusEnum.IN_CREATION: (PlannedRouteStatusEnum.ACTIVE,),
    PlannedRouteStatusEnum.ACTIVE: (PlannedRouteStatusEnum.INACTIVE,),
    PlannedRouteStatusEnum.INACTIVE: (PlannedRouteStatusEnum.ACTIVE,)
}


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------
def get_planned_route(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    route_id: str
) -> PlannedRouteItem:
    '''
        Reads one of the owner's routes. Somebody else's route is not found.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            route_id (str): Route identifier.

        Returns:
            PlannedRouteItem: The route item with native numbers.
    '''
    try:
        item = get_item_by_key(
            dynamodb_resource = dynamodb_resource,
            table_name = PLANNED_ROUTES_TABLE,
            key = {'owner_email': owner_email, 'id': route_id}
        )
    except RegisterNotFoundError as error:
        # The shared crud names the key and the table in its detail; the
        # client gets the bare code and nothing about how we store things.
        raise RegisterNotFoundError(detail = LocalizationError.ROUTE_NOT_FOUND.value) from error
    return from_dynamo(item)


def list_planned_routes(
    dynamodb_resource: ServiceResource,
    owner_email: str
) -> List[PlannedRouteItem]:
    '''
        Every route of the owner, oldest first (then by code).

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.

        Returns:
            List[PlannedRouteItem]: Route items with native numbers.
    '''
    items = query_by_partition(
        dynamodb_resource = dynamodb_resource,
        table_name = PLANNED_ROUTES_TABLE,
        partition_key = 'owner_email',
        partition_value = owner_email
    )
    # Ties on created_at (same second) fall back to the code so the order is
    # stable between calls.
    return sorted(
        from_dynamo(items),
        key = lambda route: (route.get('created_at', ''), route.get('route_code', ''))
    )


def insert_planned_route(
    dynamodb_resource: ServiceResource,
    item: PlannedRouteItem
) -> None:
    '''
        Writes a NEW planned route, refusing to overwrite one.

        Public and here because the route also arrives from elsewhere —a CSV
        another system exported, a day a seller worked— and those must reach
        the table the same way. Two copies of this call is two chances to
        write a route without its uniqueness check.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            item (PlannedRouteItem): The route to insert.
    '''
    put_unique_composite_item(
        dynamodb_resource = dynamodb_resource,
        table_name = PLANNED_ROUTES_TABLE,
        item_data = item,
        partition_key = 'owner_email',
        sort_key = 'id'
    )


def _save_planned_route(
    dynamodb_resource: ServiceResource,
    item: PlannedRouteItem
) -> PlannedRouteItem:
    '''
        Writes a route back after a change (full replace of the item).
    '''
    table = dynamodb_resource.Table(PLANNED_ROUTES_TABLE)
    table.put_item(Item = to_dynamo(item))
    return item


def to_point_response(
    route_id: str,
    point: PlannedPointItem
) -> PlannedPointResponseSchema:
    '''
        Stop item -> DTO.

        Args:
            route_id (str): Route the stop belongs to.
            point (PlannedPointItem): Stored stop.

        Returns:
            PlannedPointResponseSchema: The stop as the API returns it.
    '''
    return PlannedPointResponseSchema(planned_route_id = route_id, **point)


def to_route_response(route: PlannedRouteItem) -> PlannedRouteResponseSchema:
    '''
        Route item -> DTO, stops included.

        Args:
            route (PlannedRouteItem): Stored route.

        Returns:
            PlannedRouteResponseSchema: The route as the API returns it.
    '''
    return PlannedRouteResponseSchema(
        id = route['id'],
        route_name = route['route_name'],
        route_code = route['route_code'],
        description = route.get('description'),
        seller = route.get('seller'),
        plan_date = route.get('plan_date'),
        status = route['status'],
        created_at = route['created_at'],
        points = [to_point_response(route['id'], point) for point in route.get('points', [])],
        start_point = route.get('start_point'),
        end_point = route.get('end_point')
    )


def _assert_route_code_free(
    routes: List[PlannedRouteItem],
    route_code: str,
    exclude_id: Optional[str] = None
) -> None:
    '''
        Raises if another route of the same owner already carries `route_code`.
    '''
    for route in routes:
        if route['route_code'] == route_code and route['id'] != exclude_id:
            error_msg = f'Route code {route_code} already exists for this owner.'
            logger.warning(error_msg)
            raise RegisterAlreadyExistsError(
                detail = LocalizationError.ROUTE_CODE_ALREADY_EXISTS.value
            )


def _assert_in_creation(route: PlannedRouteItem) -> None:
    '''
        Raises unless the route is still being built.
    '''
    if route['status'] != PlannedRouteStatusEnum.IN_CREATION.value:
        error_msg = f'Route {route["id"]} is {route["status"]}; only IN CREATION allows this.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = LocalizationError.ROUTE_NOT_IN_CREATION.value)


def _assert_sequence_free(
    points: List[PlannedPointItem],
    secuencial: int,
    exclude_id: Optional[str] = None
) -> None:
    '''
        Raises if another stop of the route already has that visiting order.
    '''
    for point in points:
        if point['secuencial'] == secuencial and point['id'] != exclude_id:
            error_msg = f'Sequence {secuencial} already exists on this route.'
            logger.warning(error_msg)
            raise RegisterAlreadyExistsError(
                detail = LocalizationError.SEQUENCE_ALREADY_EXISTS.value
            )


def _find_point(
    route: PlannedRouteItem,
    point_id: str
) -> PlannedPointItem:
    '''
        Returns the stop with `point_id` or raises.
    '''
    for point in route.get('points', []):
        if point['id'] == point_id:
            return point
    error_msg = f'Point {point_id} not found on route {route["id"]}.'
    logger.warning(error_msg)
    raise RegisterNotFoundError(detail = LocalizationError.POINT_NOT_FOUND.value)


def build_point_item(point: PlannedPointSchema) -> PlannedPointItem:
    '''
        Stop item as stored, with its own identifier.

        Args:
            point (PlannedPointSchema): Stop as the client sent it.

        Returns:
            PlannedPointItem: Stop ready to be embedded in a route item.
    '''
    return {'id': new_id(), **point.model_dump()}


def build_route_item(
    owner_email: str,
    header: Dict[str, Any],
    points: List[PlannedPointItem]
) -> PlannedRouteItem:
    '''
        Route item as stored: header fields, the owner, a fresh id, IN CREATION
        status and the stops sorted by visiting order.

        Args:
            owner_email (str): Authenticated account.
            header (Dict[str, Any]): route_name, route_code, description,
                seller and the optional plan_date, start_point and end_point.
            points (List[PlannedPointItem]): Stop items.

        Returns:
            PlannedRouteItem: Route item ready to be written.
    '''
    return {
        'owner_email': owner_email,
        'id': new_id(),
        'route_name': header['route_name'],
        'route_code': header['route_code'],
        'description': header.get('description'),
        'seller': header.get('seller'),
        # ISO text, not a date object: DynamoDB stores strings, and a plain
        # 'YYYY-MM-DD' compares and sorts correctly as one.
        'plan_date': header['plan_date'].isoformat() if header.get('plan_date') else None,
        'status': PlannedRouteStatusEnum.IN_CREATION.value,
        'created_at': now_iso(),
        'points': sorted(points, key = lambda point: point['secuencial']),
        'start_point': header.get('start_point'),
        'end_point': header.get('end_point')
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def create_planned_route(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    route_data: PlannedRouteCreateSchema
) -> PlannedRouteItem:
    '''
        Creates a route with its stops. The code must be new for this owner
        and no two stops may share a visiting order.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            route_data (PlannedRouteCreateSchema): Header and stops.

        Returns:
            PlannedRouteItem: The stored route.
    '''
    _assert_route_code_free(
        list_planned_routes(dynamodb_resource, owner_email), route_data.route_code
    )
    points: List[PlannedPointItem] = []
    for point in route_data.points:
        _assert_sequence_free(points, point.secuencial)
        points.append(build_point_item(point))
    item = build_route_item(
        owner_email = owner_email,
        header = route_data.model_dump(exclude = {'points'}),
        points = points
    )
    insert_planned_route(dynamodb_resource, item)
    message = f'Planned route {item["id"]} ({item["route_code"]}) created with {len(points)} stops.'
    logger.info(message)
    return item


def filter_planned_routes(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    filters: PlannedRouteFilterRequestSchema
) -> List[PlannedRouteItem]:
    '''
        The owner's routes narrowed by every filter given.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            filters (PlannedRouteFilterRequestSchema): Optional criteria.

        Returns:
            List[PlannedRouteItem]: Matching route items.
    '''
    routes = list_planned_routes(dynamodb_resource, owner_email)
    if filters.planned_route_ids:
        wanted = set(filters.planned_route_ids)
        routes = [route for route in routes if route['id'] in wanted]
    if filters.route_code:
        routes = [route for route in routes if route['route_code'] == filters.route_code]
    if filters.route_name:
        needle = filters.route_name.lower()
        routes = [route for route in routes if needle in route['route_name'].lower()]
    if filters.route_status:
        routes = [route for route in routes if route['status'] == filters.route_status.value]
    if filters.seller:
        routes = [route for route in routes if route.get('seller') == filters.seller]
    return _within_window(routes, filters)


def _within_window(
    routes: List[PlannedRouteItem],
    filters: PlannedRouteFilterRequestSchema
) -> List[PlannedRouteItem]:
    '''
        Narrows routes to the window the caller asked about.

        This is what separates the two screens: planning asks from today on,
        history asks backwards. A route with no date is a reusable template,
        so it belongs to no window and only drops out when the caller says it
        should — otherwise a date filter would hide the templates for good.

        Args:
            routes (List[PlannedRouteItem]): Routes already narrowed by the
                other criteria.
            filters (PlannedRouteFilterRequestSchema): The window asked for.

        Returns:
            List[PlannedRouteItem]: Routes inside it.
    '''
    if filters.date_from is None and filters.date_to is None:
        return routes
    since = filters.date_from.isoformat() if filters.date_from else None
    until = filters.date_to.isoformat() if filters.date_to else None
    kept = []
    for route in routes:
        when = route.get('plan_date')
        if not when:
            if filters.undated:
                kept.append(route)
            continue
        if since and when < since:
            continue
        if until and when > until:
            continue
        kept.append(route)
    return kept


def update_planned_route(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    route_id: str,
    route_data: PlannedRouteUpdateSchema
) -> PlannedRouteItem:
    '''
        Changes header fields of a route. A new code must still be unique.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            route_id (str): Route identifier.
            route_data (PlannedRouteUpdateSchema): Fields to change.

        Returns:
            PlannedRouteItem: The updated route.
    '''
    route = get_planned_route(dynamodb_resource, owner_email, route_id)
    changes = route_data.model_dump(exclude_unset = True)
    if not changes:
        return route
    if 'route_code' in changes and changes['route_code'] != route['route_code']:
        _assert_route_code_free(
            list_planned_routes(dynamodb_resource, owner_email),
            changes['route_code'],
            exclude_id = route_id
        )
    route.update(changes)
    _save_planned_route(dynamodb_resource, route)
    message = f'Planned route {route_id} updated: {sorted(changes)}.'
    logger.info(message)
    return route


def update_planned_route_status(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    route_id: str,
    new_status: PlannedRouteStatusEnum
) -> PlannedRouteItem:
    '''
        Moves a route along its lifecycle, refusing transitions that are not
        in `_ALLOWED_TRANSITIONS`.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            route_id (str): Route identifier.
            new_status (PlannedRouteStatusEnum): Requested status.

        Returns:
            PlannedRouteItem: The updated route.
    '''
    route = get_planned_route(dynamodb_resource, owner_email, route_id)
    current = PlannedRouteStatusEnum(route['status'])
    if new_status not in _ALLOWED_TRANSITIONS[current]:
        error_msg = f'Route {route_id}: transition {current.value} -> {new_status.value} refused.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = LocalizationError.INVALID_STATUS_TRANSITION.value)
    route['status'] = new_status.value
    _save_planned_route(dynamodb_resource, route)
    message = f'Planned route {route_id} is now {new_status.value}.'
    logger.info(message)
    return route


def delete_planned_route(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    route_id: str
) -> PlannedRouteItem:
    '''
        Removes a route that is still being built.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            route_id (str): Route identifier.

        Returns:
            PlannedRouteItem: The route as it was before deletion.
    '''
    route = get_planned_route(dynamodb_resource, owner_email, route_id)
    _assert_in_creation(route)
    table = dynamodb_resource.Table(PLANNED_ROUTES_TABLE)
    table.delete_item(Key = {'owner_email': owner_email, 'id': route_id})
    message = f'Planned route {route_id} deleted with {len(route.get("points", []))} stops.'
    logger.info(message)
    return route


# ---------------------------------------------------------------------------
# Stops
# ---------------------------------------------------------------------------
def add_planned_point(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    route_id: str,
    point_data: PlannedPointSchema
) -> Tuple[PlannedRouteItem, PlannedPointItem]:
    '''
        Adds a stop to a route being built.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            route_id (str): Route identifier.
            point_data (PlannedPointSchema): The new stop.

        Returns:
            Tuple[PlannedRouteItem, PlannedPointItem]: The updated route and the new stop.
    '''
    route = get_planned_route(dynamodb_resource, owner_email, route_id)
    _assert_in_creation(route)
    _assert_sequence_free(route.get('points', []), point_data.secuencial)
    point = build_point_item(point_data)
    route['points'] = sorted(
        route.get('points', []) + [point], key = lambda stop: stop['secuencial']
    )
    _save_planned_route(dynamodb_resource, route)
    message = f'Stop {point["id"]} added to planned route {route_id}.'
    logger.info(message)
    return route, point


def update_planned_point(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    route_id: str,
    point_id: str,
    point_data: PlannedPointUpdateSchema
) -> Tuple[PlannedRouteItem, PlannedPointItem]:
    '''
        Edits a stop of a route being built.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            route_id (str): Route identifier.
            point_id (str): Stop identifier.
            point_data (PlannedPointUpdateSchema): Fields to change.

        Returns:
            Tuple[PlannedRouteItem, PlannedPointItem]: The updated route and stop.
    '''
    route = get_planned_route(dynamodb_resource, owner_email, route_id)
    _assert_in_creation(route)
    point = _find_point(route, point_id)
    changes = point_data.model_dump(exclude_unset = True)
    if 'secuencial' in changes and changes['secuencial'] != point['secuencial']:
        _assert_sequence_free(route['points'], changes['secuencial'], exclude_id = point_id)
    point.update(changes)
    route['points'] = sorted(route['points'], key = lambda stop: stop['secuencial'])
    _save_planned_route(dynamodb_resource, route)
    message = f'Stop {point_id} of planned route {route_id} updated: {sorted(changes)}.'
    logger.info(message)
    return route, point


def delete_planned_point(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    route_id: str,
    point_id: str
) -> PlannedRouteItem:
    '''
        Removes a stop from a route being built.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            route_id (str): Route identifier.
            point_id (str): Stop identifier.

        Returns:
            PlannedRouteItem: The updated route.
    '''
    route = get_planned_route(dynamodb_resource, owner_email, route_id)
    _assert_in_creation(route)
    _find_point(route, point_id)
    route['points'] = [point for point in route['points'] if point['id'] != point_id]
    _save_planned_route(dynamodb_resource, route)
    message = f'Stop {point_id} removed from planned route {route_id}.'
    logger.info(message)
    return route
