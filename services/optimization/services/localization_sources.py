'''
    Plans that came from somewhere else.

    Two of them, and they share one idea: the client already decided the
    route, so the service reads it instead of proposing it.

      - **A CSV another system exported.** All-or-nothing, because half an
        imported route is worse than none.
      - **A day a seller already worked.** The visits become the stops in the
        order they happened, and the day's executions are linked to the new
        plan. A stop that names no client is kept: those are the addresses
        the sales file never mentioned, which is to say the new clients.

      - **A seller's portfolio in the sales file.** One plan per seller, each
        from the clients that seller sold to, so nobody is measured against a
        route that belonged to the whole team.

    The CRUD of a plan lives in `localization.py`; this is how one arrives.
'''
import csv
import io
import unicodedata
import re
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from boto3.resources.base import ServiceResource
from pydantic import ValidationError

from models.localization import (
    ExecutedRouteItem,
    PlannedPointItem,
    PlannedRouteItem
)
from schemas.optimization import (
    OptimizationError,
    PlansBySellerResponse,
    PlansBySellerSchema,
    SellerPlanSchema
)
from schemas.localization import (
    BulkUploadPlannedResponseSchema,
    InferPlannedRouteSchema,
    LocalizationError,
    PlannedPointSchema,
    PlannedRouteBulkRowSchema,
    PlannedRouteCreateSchema,
    RepeatPlannedRouteSchema,
    RouteEndpointSchema
)
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError, RegisterAlreadyExistsError
from services.localization import (
    _assert_route_code_free,
    _assert_sequence_free,
    build_point_item,
    build_route_item,
    create_planned_route,
    get_planned_route,
    insert_planned_route,
    list_planned_routes
)
from services.logger_config import custom_logger as logger
from services.optimization_settings import get_route_settings
from services.optimization import (
    assign_days,
    available_sellers,
    build_client_points,
    plan_day
)
from services.route_optimization import (
    apply_optimized_order,
    optimize_planned_route
)

_SETTINGS = load_and_validate_env_vars({'STOP_POSITION_DECIMALS': int})
# How close two readings have to be to count as the same stop when neither
# names a client. A decision —it is the difference between one shop and two—
# so it lives in the environment.
_STOP_POSITION_DECIMALS = _SETTINGS['STOP_POSITION_DECIMALS']

# Columns of the CSV another system exports: the route header repeated on
# every stop. Names are the API's own field names, so the file format and the
# JSON contract never diverge.
BULK_REQUIRED_COLUMNS = ('route_code', 'route_name', 'point_name', 'secuencial',
                         'latitude', 'longitude')
BULK_HEADER_FIELDS = ('route_name', 'route_code', 'plan_date', 'description', 'seller')

# The file the client fills in is written in Spanish, like every other
# template of the product: `CLAUDE.md` §1. Inside, the contract keeps its
# English names, and this is the mapper between the two — the same shape
# INGEST uses for its own headers. The canonical names are accepted too, so
# a system already exporting them keeps working.
BULK_HEADER_LOOKUP: Dict[str, str] = {
    'codigo ruta': 'route_code',
    'nombre ruta': 'route_name',
    'fecha': 'plan_date',
    'vendedor': 'seller',
    'descripcion': 'description',
    'cliente': 'point_name',
    'secuencia': 'secuencial',
    'latitud': 'latitude',
    'longitud': 'longitude',
    'referencia': 'reference_data',
    'cliente id': 'client_id',
}


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
    header = [_canonical_header(name) for name in (reader.fieldnames or [])]
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


def _canonical_header(name: str) -> str:
    '''
        The contract name of a column, whichever language it came in.

        Args:
            name (str): Header as the file writes it.

        Returns:
            str: Canonical field name.
    '''
    cleaned = unicodedata.normalize('NFKD', (name or '').strip().lower())
    cleaned = ''.join(char for char in cleaned if not unicodedata.combining(char))
    return BULK_HEADER_LOOKUP.get(cleaned, cleaned.replace(' ', '_'))


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
        insert_planned_route(dynamodb_resource, item)
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
        (point for route in routes for point in route.get('points', [])),
        key = lambda point: point['timestamp']
    )
    stops: List[PlannedPointSchema] = []
    seen: set = set()
    for point in visits:
        # A stop names a client when the seller knew it; when it does not, the
        # position itself is the identity. Dropping those was how a day spent
        # at addresses the sales file never mentioned answered
        # NO_VISITS_TO_INFER — and that is precisely the day worth keeping,
        # because those stops are the new clients.
        key = point.get('client_id') or _position_key(point)
        if key in seen:
            continue
        seen.add(key)
        stops.append(PlannedPointSchema(
            point_name = point.get('client_id') or point.get('reference_data') or key,
            secuencial = len(stops) + 1,
            latitude = point['latitude'],
            longitude = point['longitude'],
            client_id = point.get('client_id')
        ))
    return stops


def _position_key(point: Dict[str, Any]) -> str:
    '''
        The identity of a stop that names no client: where it was.

        Args:
            point (Dict[str, Any]): A reported position.

        Returns:
            str: A stable key built from the coordinates.
    '''
    latitude = round(float(point['latitude']), _STOP_POSITION_DECIMALS)
    longitude = round(float(point['longitude']), _STOP_POSITION_DECIMALS)
    return f'{latitude},{longitude}'


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
        plan_date = request.date,
        points = stops
    ))
    message = f'Planned route {plan["id"]} inferred from {len(stops)} visit(s) of {request.seller}.'
    logger.info(message)
    return plan


def repeat_planned_route(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    route_id: str,
    repeat: RepeatPlannedRouteSchema
) -> PlannedRouteItem:
    '''
        Runs an existing route again on another day.

        The third way a plan arrives, and the most common one: yesterday
        worked, do it again. The stops are copied whole —they are what the
        route is— and only the day, and optionally the seller, change. The
        new route starts IN CREATION like any other, so it is reviewed before
        anyone runs it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            route_id (str): The route to repeat.
            repeat (RepeatPlannedRouteSchema): New day, seller and code.

        Returns:
            PlannedRouteItem: The new plan, IN CREATION.
    '''
    original = get_planned_route(dynamodb_resource, owner_email, route_id)
    # Reordering happens here, against the same study the screen showed, so
    # what gets created cannot drift from what was proposed.
    points = original.get('points', [])
    if repeat.optimized:
        points = apply_optimized_order(
            points, optimize_planned_route(dynamodb_resource, owner_email, route_id)
        )
    stops = [
        PlannedPointSchema(
            point_name = point['point_name'],
            secuencial = point['secuencial'],
            latitude = point['latitude'],
            longitude = point['longitude'],
            reference_data = point.get('reference_data'),
            client_id = point.get('client_id')
        )
        for point in sorted(points, key = lambda point: point['secuencial'])
    ]
    if not stops:
        error_msg = f'Planned route {route_id} has no stops to repeat.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = LocalizationError.NO_VISITS_TO_INFER.value)

    plan = create_planned_route(dynamodb_resource, owner_email, PlannedRouteCreateSchema(
        route_name = original['route_name'],
        route_code = repeat.route_code or f'{original["route_code"]}-{repeat.plan_date}',
        description = original.get('description'),
        seller = repeat.seller or original.get('seller'),
        plan_date = repeat.plan_date,
        points = stops
    ))
    message = (f'Planned route {route_id} repeated as {plan["id"]} '
               f'for {repeat.plan_date} with {len(stops)} stop(s).')
    logger.info(message)
    return plan


# A route code is unique per owner and goes in URLs and file names, so the
# seller part is reduced to safe characters and kept short.
_CODE_UNSAFE = re.compile(r'[^A-Za-z0-9@._-]')
_CODE_SELLER_LENGTH = 20


def _seller_stops(
    dataframe: pd.DataFrame,
    seller: str,
    request: PlansBySellerSchema
) -> List[PlannedPointSchema]:
    '''
        The stops of one day of one seller's portfolio, in visiting order.

        The order is the local nearest-neighbour + 2-opt tour, not OSRM: the
        street geometry is drawn when someone opens the plan, and asking the
        public router once per seller on every split is what its rate limit
        punishes.

        Args:
            dataframe (pd.DataFrame): Sales rows of the period.
            seller (str): The seller as the file writes it.
            request (PlansBySellerSchema): Days, day and period.

        Returns:
            List[PlannedPointSchema]: The day's stops; empty when that day of
                the seller's split has no placeable client.
    '''
    try:
        clients = build_client_points(dataframe, seller = seller)
    except InvalidInputError:
        return []
    clients = assign_days(clients, request.days)
    return [
        PlannedPointSchema(
            point_name = stop.client[:100],
            secuencial = stop.stop_order,
            latitude = stop.latitude,
            longitude = stop.longitude,
            client_id = stop.client_id[:64]
        )
        for stop in plan_day(clients, request.day)
    ]


def _create_seller_plan(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    seller_stops: Tuple[str, List[PlannedPointSchema]],
    request: PlansBySellerSchema,
    endpoints: Tuple[Optional[RouteEndpointSchema], Optional[RouteEndpointSchema]]
) -> SellerPlanSchema | None:
    '''
        Saves one seller's day as their plan.

        The code is seller + date + day, so saving the same split twice finds
        the plan already there and leaves it alone instead of duplicating it.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            seller_stops (Tuple[str, List[PlannedPointSchema]]): The seller as
                the file writes it, and the day's stops in order.
            request (PlansBySellerSchema): Day and date.
            endpoints (Tuple): Fixed start and end point, or None when open.

        Returns:
            SellerPlanSchema | None: The plan created, or None when a plan with
                that code already existed.
    '''
    seller, stops = seller_stops
    code_seller = _CODE_UNSAFE.sub('_', seller)[:_CODE_SELLER_LENGTH]
    day_label = f'{request.plan_date.isoformat()}-D{request.day}'
    try:
        plan = create_planned_route(dynamodb_resource, owner_email, PlannedRouteCreateSchema(
            route_name = f'{seller} · {day_label}'[:150],
            route_code = f'{code_seller}-{day_label}',
            seller = seller[:128],
            plan_date = request.plan_date,
            points = stops,
            start_point = endpoints[0],
            end_point = endpoints[1]
        ))
    except RegisterAlreadyExistsError:
        return None
    return SellerPlanSchema(
        seller = seller, id = plan['id'], route_code = plan['route_code'], stops = len(stops)
    )


def _base_endpoints(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    request: PlansBySellerSchema
) -> Tuple[Optional[RouteEndpointSchema], Optional[RouteEndpointSchema]]:
    '''
        The start and end the plans get: the company base point where the
        request asks for it, nothing where it does not.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            request (PlansBySellerSchema): Whether to start and end at the base.

        Returns:
            Tuple: Start and end point, each None when open.

        Raises:
            InvalidInputError: BASE_POINT_NOT_SET when asked for a base point
                the company never configured.
    '''
    if not (request.start_at_base or request.end_at_base):
        return None, None
    base = get_route_settings(dynamodb_resource, owner_email).base_point
    if base is None:
        raise InvalidInputError(detail = OptimizationError.BASE_POINT_NOT_SET.value)
    return (base if request.start_at_base else None,
            base if request.end_at_base else None)


def plans_by_seller(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    dataset_id: str,
    dataframe: pd.DataFrame,
    request: PlansBySellerSchema
) -> PlansBySellerResponse:
    '''
        One plan per seller, each from that seller's own portfolio.

        A plan for "everybody" put every client of the team on one route, and
        then each seller who ran it was measured against all of it. Here each
        seller gets the clients the file says they sold to, split into days by
        proximity, and the requested day of that split becomes their plan.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            dataset_id (str): The sales dataset the portfolios come from.
            dataframe (pd.DataFrame): Sales rows of the period.
            request (PlansBySellerSchema): Days, day, date and sellers.

        Returns:
            PlansBySellerResponse: The plans created and the sellers skipped.

        Raises:
            InvalidInputError: NO_SELLERS_IN_FILE when the file names nobody.
    '''
    sellers = available_sellers(dataframe)
    if request.sellers:
        wanted = set(request.sellers)
        sellers = [seller for seller in sellers if seller in wanted]
    if not sellers:
        raise InvalidInputError(detail = OptimizationError.NO_SELLERS_IN_FILE.value)

    endpoints = _base_endpoints(dynamodb_resource, owner_email, request)
    created: List[SellerPlanSchema] = []
    without_stops: List[str] = []
    already_planned: List[str] = []
    for seller in sellers:
        stops = _seller_stops(dataframe, seller, request)
        if not stops:
            without_stops.append(seller)
            continue
        plan = _create_seller_plan(dynamodb_resource, owner_email, (seller, stops),
                                   request, endpoints)
        if plan is None:
            already_planned.append(seller)
            continue
        created.append(plan)

    message = (f'Plans by seller for {owner_email}: {len(created)} created, '
               f'{len(without_stops)} without stops, {len(already_planned)} already planned.')
    logger.info(message)
    return PlansBySellerResponse(
        dataset_id = dataset_id,
        day = request.day,
        plan_date = request.plan_date,
        created = created,
        without_stops = without_stops,
        already_planned = already_planned
    )
