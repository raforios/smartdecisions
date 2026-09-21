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
import csv
import io
from typing import Any, Dict, List, Optional, Tuple

from boto3.resources.base import ServiceResource
from pydantic import ValidationError

from models.localization import ExecutedRouteItem, PlannedPointItem, PlannedRouteItem

from schemas.localization import (
    BulkUploadPlannedResponseSchema,
    InferPlannedRouteSchema,
    LocalizationError,
    PlannedPointResponseSchema,
    PlannedPointSchema,
    PlannedPointUpdateSchema,
    PlannedRouteBulkRowSchema,
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
    'DYNAMODB_TABLE_NAME_OPTIMIZATION_PLANNED_ROUTES': str
})
PLANNED_ROUTES_TABLE = _SETTINGS['DYNAMODB_TABLE_NAME_OPTIMIZATION_PLANNED_ROUTES']

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
        status = route['status'],
        created_at = route['created_at'],
        points = [to_point_response(route['id'], point) for point in route.get('points', [])]
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
            header (Dict[str, Any]): route_name, route_code, description, seller.
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
        'status': PlannedRouteStatusEnum.IN_CREATION.value,
        'created_at': now_iso(),
        'points': sorted(points, key = lambda point: point['secuencial'])
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
    put_unique_composite_item(
        dynamodb_resource = dynamodb_resource,
        table_name = PLANNED_ROUTES_TABLE,
        item_data = item,
        partition_key = 'owner_email',
        sort_key = 'id'
    )
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
    return routes


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


# ---------------------------------------------------------------------------
# Bulk upload
# ---------------------------------------------------------------------------
# Columns of the CSV another system exports: the route header repeated on
# every stop. Names are the API's own field names, so the file format and the
# JSON contract never diverge.
BULK_REQUIRED_COLUMNS = ('route_code', 'route_name', 'point_name', 'secuencial',
                         'latitude', 'longitude')
BULK_HEADER_FIELDS = ('route_name', 'route_code', 'description', 'seller')


def parse_planned_routes_csv(csv_text: str) -> List[PlannedRouteBulkRowSchema]:
    '''
        Reads the bulk CSV into validated rows. Blank lines are skipped; a
        missing required column or an invalid value refuses the whole file.

        Args:
            csv_text (str): The decoded CSV.

        Returns:
            List[PlannedRouteBulkRowSchema]: One validated row per stop.

        Raises:
            InvalidInputError: MISSING_COLUMNS, EMPTY_UPLOAD or INVALID_ROW.
    '''
    reader = csv.DictReader(io.StringIO(csv_text))
    header = [name.strip() for name in (reader.fieldnames or [])]
    missing = [column for column in BULK_REQUIRED_COLUMNS if column not in header]
    if missing:
        error_msg = f'Bulk CSV lacks columns {missing}; got {header}.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = LocalizationError.MISSING_COLUMNS.value)
    reader.fieldnames = header

    rows: List[PlannedRouteBulkRowSchema] = []
    for line_no, raw in enumerate(reader, start = 2):
        cleaned = {key: (value or '').strip() or None for key, value in raw.items() if key}
        if not any(cleaned.values()):
            continue
        try:
            rows.append(PlannedRouteBulkRowSchema(**cleaned))
        except ValidationError as error:
            error_msg = f'Bulk CSV line {line_no} rejected: {error.error_count()} error(s).'
            logger.warning(error_msg)
            raise InvalidInputError(detail = LocalizationError.INVALID_ROW.value) from error
    if not rows:
        raise InvalidInputError(detail = LocalizationError.EMPTY_UPLOAD.value)
    return rows


def group_rows_into_routes(rows: List[PlannedRouteBulkRowSchema]) -> List[PlannedRouteCreateSchema]:
    '''
        Folds the stop rows into one route per `route_code`, keeping the header
        of the first row of each code and the stops in file order.

        Args:
            rows (List[PlannedRouteBulkRowSchema]): Validated CSV rows.

        Returns:
            List[PlannedRouteCreateSchema]: Routes ready to be created.
    '''
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        bucket = grouped.setdefault(row.route_code, {
            **row.model_dump(include = set(BULK_HEADER_FIELDS)), 'points': []
        })
        bucket['points'].append(PlannedPointSchema(
            **row.model_dump(exclude = set(BULK_HEADER_FIELDS))
        ))
    return [PlannedRouteCreateSchema(**route) for route in grouped.values()]


def bulk_create_planned_routes(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    csv_text: str
) -> BulkUploadPlannedResponseSchema:
    '''
        Imports the plan another system exported. All-or-nothing: every code
        must be new and every route valid before the first write.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            csv_text (str): The decoded CSV.

        Returns:
            BulkUploadPlannedResponseSchema: Counts and the ids created.
    '''
    routes = group_rows_into_routes(parse_planned_routes_csv(csv_text))
    existing = list_planned_routes(dynamodb_resource, owner_email)
    items: List[PlannedRouteItem] = []
    for route in routes:
        _assert_route_code_free(existing, route.route_code)
        points: List[PlannedPointItem] = []
        for point in route.points:
            _assert_sequence_free(points, point.secuencial)
            points.append(build_point_item(point))
        items.append(build_route_item(
            owner_email = owner_email,
            header = route.model_dump(exclude = {'points'}),
            points = points
        ))
    for item in items:
        put_unique_composite_item(
            dynamodb_resource = dynamodb_resource,
            table_name = PLANNED_ROUTES_TABLE,
            item_data = item,
            partition_key = 'owner_email',
            sort_key = 'id'
        )
    points_created = sum(len(item['points']) for item in items)
    message = f'Bulk upload created {len(items)} planned route(s) with {points_created} stops.'
    logger.info(message)
    return BulkUploadPlannedResponseSchema(
        routes_created = len(items),
        points_created = points_created,
        route_ids = [item['id'] for item in items]
    )


# ---------------------------------------------------------------------------
# Plan inferred from the execution
# ---------------------------------------------------------------------------
def visits_as_stops(routes: List[PlannedRouteItem]) -> List[PlannedPointSchema]:
    '''
        The clients a seller visited across `routes`, in the order they were
        reached, each once. Positions that name no client are breadcrumbs, not
        stops.

        Args:
            routes (List[ExecutedRouteItem]): Executed route items of one seller and day.

        Returns:
            List[PlannedPointSchema]: Stops with visiting order.
    '''
    visits = sorted(
        (point for route in routes for point in route.get('points', []) if point.get('client_id')),
        key = lambda point: point['timestamp']
    )
    stops: List[PlannedPointSchema] = []
    seen: set = set()
    for point in visits:
        if point['client_id'] in seen:
            continue
        seen.add(point['client_id'])
        stops.append(PlannedPointSchema(
            point_name = point['client_id'],
            secuencial = len(stops) + 1,
            latitude = point['latitude'],
            longitude = point['longitude'],
            client_id = point['client_id']
        ))
    return stops


def infer_planned_route(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    request: InferPlannedRouteSchema,
    executed_routes: List[ExecutedRouteItem]
) -> PlannedRouteItem:
    '''
        Creates the plan a seller's day implies and links that day's routes to
        it. The caller hands over the executed routes (already scoped to the
        seller and date) so this module does not depend on the executed one.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            request (InferPlannedRouteSchema): Seller, date and optional naming.
            executed_routes (List[ExecutedRouteItem]): That seller's routes that day.

        Returns:
            PlannedRouteItem: The stored plan, IN CREATION.

        Raises:
            InvalidInputError: NO_VISITS_TO_INFER when the day has no visits.
    '''
    stops = visits_as_stops(executed_routes)
    if not stops:
        error_msg = f'{request.seller} has no visits on {request.date}; nothing to infer.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = LocalizationError.NO_VISITS_TO_INFER.value)
    route_code = request.route_code or f'{request.seller}-{request.date}'
    plan = create_planned_route(dynamodb_resource, owner_email, PlannedRouteCreateSchema(
        route_name = request.route_name or route_code,
        route_code = route_code,
        description = None,
        seller = request.seller,
        points = stops
    ))
    message = f'Planned route {plan["id"]} inferred from {len(stops)} visit(s) of {request.seller}.'
    logger.info(message)
    return plan
