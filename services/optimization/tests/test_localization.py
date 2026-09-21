'''
    Tests for the planned-routes logic ported from LOCALIZATION onto DynamoDB.
    One test per service function, plus the rules the port had to keep: code
    unique per owner, stops only editable IN CREATION, legal status moves, and
    a foreign route reading as a missing one.
'''
import pytest
from moto import mock_aws

from schemas.localization import (
    InferPlannedRouteSchema,
    LocalizationError,
    PlannedPointSchema,
    PlannedPointUpdateSchema,
    PlannedRouteCreateSchema,
    PlannedRouteFilterRequestSchema,
    PlannedRouteStatusEnum,
    PlannedRouteUpdateSchema
)
from services import localization
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from tests.dynamo_helpers import build_resource

OWNER = 'yo@miempresa.com'
OTHER = 'otra@empresa.com'


def _route_payload(
    code: str = 'R-001',
    seller: str = 'Ana'
) -> PlannedRouteCreateSchema:
    '''
        A three-stop route as the frontend would send it.
    '''
    return PlannedRouteCreateSchema(
        route_name = f'Ruta {code}',
        route_code = code,
        description = 'Zona sur',
        seller = seller,
        points = [
            PlannedPointSchema(point_name = 'Tienda 1', secuencial = 1,
                               latitude = -16.50, longitude = -68.10, client_id = 'PDV-1'),
            PlannedPointSchema(point_name = 'Tienda 2', secuencial = 2,
                               latitude = -16.51, longitude = -68.11),
            PlannedPointSchema(point_name = 'Tienda 3', secuencial = 3,
                               latitude = -16.52, longitude = -68.12)
        ]
    )


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Provides a moto-mocked DynamoDB resource with the planned-routes table.'''
    with mock_aws():
        yield build_resource([(localization.PLANNED_ROUTES_TABLE, 'owner_email', 'id')])


@pytest.fixture(name = 'route')
def route_fixture(dynamodb):
    '''A freshly created route of OWNER.'''
    return localization.create_planned_route(dynamodb, OWNER, _route_payload())


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
def test_create_planned_route_stores_header_and_sorted_stops(dynamodb):
    '''The item carries the owner, IN CREATION status and its stops in order.'''
    payload = _route_payload()
    payload.points = list(reversed(payload.points))
    created = localization.create_planned_route(dynamodb, OWNER, payload)

    stored = localization.get_planned_route(dynamodb, OWNER, created['id'])
    assert stored['owner_email'] == OWNER
    assert stored['status'] == PlannedRouteStatusEnum.IN_CREATION.value
    assert stored['seller'] == 'Ana'
    assert [point['secuencial'] for point in stored['points']] == [1, 2, 3]
    assert all(point['id'] for point in stored['points'])


def test_create_planned_route_refuses_duplicate_code_for_same_owner(
    dynamodb,
    route
):
    '''`route_code` is unique per owner, as in LOCALIZATION.'''
    with pytest.raises(RegisterAlreadyExistsError) as failure:
        localization.create_planned_route(dynamodb, OWNER, _route_payload())
    assert failure.value.detail == LocalizationError.ROUTE_CODE_ALREADY_EXISTS.value
    assert route['route_code'] == 'R-001'


def test_create_planned_route_allows_same_code_for_another_owner(
    dynamodb,
    route
):
    '''Two clients may both have an "R-001": the owner is part of the key.'''
    theirs = localization.create_planned_route(dynamodb, OTHER, _route_payload())
    assert theirs['id'] != route['id']
    assert theirs['owner_email'] == OTHER


def test_create_planned_route_refuses_repeated_sequence(dynamodb):
    '''Two stops cannot share a visiting order.'''
    payload = _route_payload()
    payload.points[1].secuencial = 1
    with pytest.raises(RegisterAlreadyExistsError) as failure:
        localization.create_planned_route(dynamodb, OWNER, payload)
    assert failure.value.detail == LocalizationError.SEQUENCE_ALREADY_EXISTS.value


def test_get_planned_route_of_another_owner_is_not_found(
    dynamodb,
    route
):
    '''A foreign route answers exactly like a missing one.'''
    with pytest.raises(RegisterNotFoundError):
        localization.get_planned_route(dynamodb, OTHER, route['id'])


def test_list_planned_routes_returns_only_the_owners(
    dynamodb,
    route
):
    '''The partition is the boundary: the other client's routes never show.'''
    localization.create_planned_route(dynamodb, OTHER, _route_payload('R-777'))
    localization.create_planned_route(dynamodb, OWNER, _route_payload('R-002', 'Juan'))

    codes = [item['route_code'] for item in localization.list_planned_routes(dynamodb, OWNER)]
    assert codes == ['R-001', 'R-002']
    assert route['route_code'] in codes


def test_filter_planned_routes_combines_criteria(
    dynamodb,
    route
):
    '''Name fragment, seller, status and ids narrow the same list together.'''
    juan = localization.create_planned_route(dynamodb, OWNER, _route_payload('R-002', 'Juan'))
    localization.update_planned_route_status(
        dynamodb, OWNER, juan['id'], PlannedRouteStatusEnum.ACTIVE
    )

    by_seller = localization.filter_planned_routes(
        dynamodb, OWNER, PlannedRouteFilterRequestSchema(seller = 'Juan')
    )
    by_status = localization.filter_planned_routes(
        dynamodb, OWNER,
        PlannedRouteFilterRequestSchema(route_status = PlannedRouteStatusEnum.IN_CREATION)
    )
    by_name_and_id = localization.filter_planned_routes(
        dynamodb, OWNER,
        PlannedRouteFilterRequestSchema(route_name = 'ruta r-0', planned_route_ids = [route['id']])
    )
    assert [item['id'] for item in by_seller] == [juan['id']]
    assert [item['id'] for item in by_status] == [route['id']]
    assert [item['id'] for item in by_name_and_id] == [route['id']]


def test_update_planned_route_changes_header_and_keeps_code_unique(
    dynamodb,
    route
):
    '''Header fields change; a code taken by a sibling route is refused.'''
    localization.create_planned_route(dynamodb, OWNER, _route_payload('R-002'))

    updated = localization.update_planned_route(
        dynamodb, OWNER, route['id'],
        PlannedRouteUpdateSchema(route_name = 'Zona sur — lunes', seller = 'Juan')
    )
    assert updated['route_name'] == 'Zona sur — lunes'
    assert updated['seller'] == 'Juan'
    assert len(updated['points']) == 3

    with pytest.raises(RegisterAlreadyExistsError):
        localization.update_planned_route(
            dynamodb, OWNER, route['id'], PlannedRouteUpdateSchema(route_code = 'R-002')
        )


def test_update_planned_route_status_follows_the_lifecycle(
    dynamodb,
    route
):
    '''IN CREATION -> ACTIVE -> INACTIVE -> ACTIVE; anything else is refused.'''
    with pytest.raises(InvalidInputError) as failure:
        localization.update_planned_route_status(
            dynamodb, OWNER, route['id'], PlannedRouteStatusEnum.INACTIVE
        )
    assert failure.value.detail == LocalizationError.INVALID_STATUS_TRANSITION.value

    for step in (PlannedRouteStatusEnum.ACTIVE, PlannedRouteStatusEnum.INACTIVE,
                 PlannedRouteStatusEnum.ACTIVE):
        assert localization.update_planned_route_status(
            dynamodb, OWNER, route['id'], step
        )['status'] == step.value

    with pytest.raises(InvalidInputError):
        localization.update_planned_route_status(
            dynamodb, OWNER, route['id'], PlannedRouteStatusEnum.IN_CREATION
        )


def test_delete_planned_route_only_while_in_creation(
    dynamodb,
    route
):
    '''An active route is history for the sellers who ran it; it cannot vanish.'''
    other = localization.create_planned_route(dynamodb, OWNER, _route_payload('R-002'))
    localization.update_planned_route_status(
        dynamodb, OWNER, other['id'], PlannedRouteStatusEnum.ACTIVE
    )
    with pytest.raises(InvalidInputError) as failure:
        localization.delete_planned_route(dynamodb, OWNER, other['id'])
    assert failure.value.detail == LocalizationError.ROUTE_NOT_IN_CREATION.value

    deleted = localization.delete_planned_route(dynamodb, OWNER, route['id'])
    assert deleted['id'] == route['id']
    with pytest.raises(RegisterNotFoundError):
        localization.get_planned_route(dynamodb, OWNER, route['id'])


# ---------------------------------------------------------------------------
# Stops
# ---------------------------------------------------------------------------
def test_add_planned_point_keeps_order_and_refuses_taken_sequence(
    dynamodb,
    route
):
    '''A new stop lands in visiting order; its sequence must be free.'''
    updated, point = localization.add_planned_point(
        dynamodb, OWNER, route['id'],
        PlannedPointSchema(point_name = 'Tienda 0', secuencial = 0 + 4,
                           latitude = -16.53, longitude = -68.13)
    )
    assert point['secuencial'] == 4
    assert [stop['secuencial'] for stop in updated['points']] == [1, 2, 3, 4]

    with pytest.raises(RegisterAlreadyExistsError):
        localization.add_planned_point(
            dynamodb, OWNER, route['id'],
            PlannedPointSchema(point_name = 'Repetida', secuencial = 2,
                               latitude = -16.5, longitude = -68.1)
        )


def test_update_planned_point_changes_fields_and_resorts(
    dynamodb,
    route
):
    '''Moving a stop to another sequence reorders the route.'''
    first = route['points'][0]
    updated, point = localization.update_planned_point(
        dynamodb, OWNER, route['id'], first['id'],
        PlannedPointUpdateSchema(secuencial = 9, point_name = 'Tienda 1 (tarde)')
    )
    assert point['point_name'] == 'Tienda 1 (tarde)'
    assert [stop['secuencial'] for stop in updated['points']] == [2, 3, 9]

    with pytest.raises(RegisterNotFoundError) as failure:
        localization.update_planned_point(
            dynamodb, OWNER, route['id'], 'no-such-point', PlannedPointUpdateSchema(secuencial = 5)
        )
    assert failure.value.detail == LocalizationError.POINT_NOT_FOUND.value


def test_delete_planned_point_removes_only_that_stop(
    dynamodb,
    route
):
    '''The other stops stay, in order.'''
    victim = route['points'][1]
    updated = localization.delete_planned_point(dynamodb, OWNER, route['id'], victim['id'])
    assert [stop['secuencial'] for stop in updated['points']] == [1, 3]


def test_stops_are_frozen_once_the_route_is_active(
    dynamodb,
    route
):
    '''Add, edit and delete of stops are refused outside IN CREATION.'''
    localization.update_planned_route_status(
        dynamodb, OWNER, route['id'], PlannedRouteStatusEnum.ACTIVE
    )
    point = route['points'][0]
    new_stop = PlannedPointSchema(point_name = 'X', secuencial = 7,
                                  latitude = -16.5, longitude = -68.1)
    for attempt in (
        lambda: localization.add_planned_point(dynamodb, OWNER, route['id'], new_stop),
        lambda: localization.update_planned_point(
            dynamodb, OWNER, route['id'], point['id'], PlannedPointUpdateSchema(secuencial = 8)
        ),
        lambda: localization.delete_planned_point(dynamodb, OWNER, route['id'], point['id'])
    ):
        with pytest.raises(InvalidInputError) as failure:
            attempt()
        assert failure.value.detail == LocalizationError.ROUTE_NOT_IN_CREATION.value


def test_to_route_response_builds_the_dto_with_native_numbers(
    dynamodb,
    route
):
    '''What Dynamo returns (Decimals) becomes a validated DTO with floats.'''
    stored = localization.get_planned_route(dynamodb, OWNER, route['id'])
    dto = localization.to_route_response(stored)
    assert dto.id == route['id']
    assert dto.status is PlannedRouteStatusEnum.IN_CREATION
    assert dto.points[0].planned_route_id == route['id']
    assert isinstance(dto.points[0].latitude, float)
    assert dto.points[0].client_id == 'PDV-1'


# ---------------------------------------------------------------------------
# Bulk upload
# ---------------------------------------------------------------------------
BULK_CSV = (
    'route_code,route_name,seller,point_name,secuencial,latitude,longitude,client_id\n'
    'R-010,Zona norte,Ana,Tienda A,1,-16.48,-68.12,PDV-A\n'
    'R-010,Zona norte,Ana,Tienda B,2,-16.47,-68.13,\n'
    '\n'
    'R-011,Zona este,Juan,Tienda C,1,-16.50,-68.05,PDV-C\n'
)


def test_parse_planned_routes_csv_validates_rows_and_columns():
    '''Blank lines vanish; a missing column or a bad value refuses the file.'''
    rows = localization.parse_planned_routes_csv(BULK_CSV)
    assert [row.route_code for row in rows] == ['R-010', 'R-010', 'R-011']
    assert rows[1].client_id is None and rows[0].client_id == 'PDV-A'

    with pytest.raises(InvalidInputError) as failure:
        localization.parse_planned_routes_csv('route_code,point_name\nR-1,X\n')
    assert failure.value.detail == LocalizationError.MISSING_COLUMNS.value

    with pytest.raises(InvalidInputError) as failure:
        localization.parse_planned_routes_csv(BULK_CSV.replace('-16.48', 'norte'))
    assert failure.value.detail == LocalizationError.INVALID_ROW.value

    with pytest.raises(InvalidInputError) as failure:
        localization.parse_planned_routes_csv(BULK_CSV.splitlines()[0] + '\n\n')
    assert failure.value.detail == LocalizationError.EMPTY_UPLOAD.value


def test_group_rows_into_routes_folds_stops_under_their_code():
    '''One route per code, header from its first row, stops in file order.'''
    routes = localization.group_rows_into_routes(localization.parse_planned_routes_csv(BULK_CSV))
    assert [(route.route_code, route.seller, len(route.points)) for route in routes] == [
        ('R-010', 'Ana', 2), ('R-011', 'Juan', 1)
    ]
    assert [stop.point_name for stop in routes[0].points] == ['Tienda A', 'Tienda B']


def test_bulk_create_planned_routes_is_all_or_nothing(
    dynamodb,
    route
):
    '''A single taken code refuses the whole file; a clean file creates every route.'''
    clashing = BULK_CSV.replace('R-011', route['route_code'])
    with pytest.raises(RegisterAlreadyExistsError):
        localization.bulk_create_planned_routes(dynamodb, OWNER, clashing)
    assert len(localization.list_planned_routes(dynamodb, OWNER)) == 1

    result = localization.bulk_create_planned_routes(dynamodb, OWNER, BULK_CSV)
    assert (result.routes_created, result.points_created) == (2, 3)
    stored = {item['route_code']: item
              for item in localization.list_planned_routes(dynamodb, OWNER)}
    assert set(stored) == {'R-001', 'R-010', 'R-011'}
    assert stored['R-010']['status'] == PlannedRouteStatusEnum.IN_CREATION.value
    assert set(result.route_ids) == {stored['R-010']['id'], stored['R-011']['id']}


# ---------------------------------------------------------------------------
# Plan inferred from the execution
# ---------------------------------------------------------------------------
def _executed_day() -> list:
    '''
        Two routes of one seller on one day: a repeated client, a breadcrumb
        without client, visits out of file order.
    '''
    return [
        {'id': 'r1', 'seller': 'Ana', 'planned_route_id': None, 'points': [
            {'id': 'p2', 'timestamp': '2026-09-21T10:00:00-04:00',
             'latitude': -16.51, 'longitude': -68.11, 'client_id': 'PDV-2'},
            {'id': 'p1', 'timestamp': '2026-09-21T09:00:00-04:00',
             'latitude': -16.50, 'longitude': -68.10, 'client_id': 'PDV-1'},
            {'id': 'p0', 'timestamp': '2026-09-21T08:30:00-04:00',
             'latitude': -16.49, 'longitude': -68.09, 'client_id': None}
        ]},
        {'id': 'r2', 'seller': 'Ana', 'planned_route_id': None, 'points': [
            {'id': 'p3', 'timestamp': '2026-09-21T15:00:00-04:00',
             'latitude': -16.52, 'longitude': -68.12, 'client_id': 'PDV-3'},
            {'id': 'p4', 'timestamp': '2026-09-21T16:00:00-04:00',
             'latitude': -16.50, 'longitude': -68.10, 'client_id': 'PDV-1'}
        ]}
    ]


def test_visits_as_stops_orders_by_time_and_dedupes_clients():
    '''PDV-1, PDV-2, PDV-3 in the order first reached; the breadcrumb is dropped.'''
    stops = localization.visits_as_stops(_executed_day())
    assert [(stop.secuencial, stop.client_id) for stop in stops] == [
        (1, 'PDV-1'), (2, 'PDV-2'), (3, 'PDV-3')
    ]
    assert stops[0].point_name == 'PDV-1'


def test_infer_planned_route_creates_the_plan_or_refuses_an_empty_day(dynamodb):
    '''The day's visits become an IN CREATION plan named after seller and date.'''
    request = InferPlannedRouteSchema(seller = 'Ana', date = '2026-09-21')
    plan = localization.infer_planned_route(dynamodb, OWNER, request, _executed_day())
    assert plan['route_code'] == 'Ana-2026-09-21'
    assert plan['route_name'] == 'Ana-2026-09-21'
    assert plan['seller'] == 'Ana'
    assert plan['status'] == PlannedRouteStatusEnum.IN_CREATION.value
    assert [stop['client_id'] for stop in plan['points']] == ['PDV-1', 'PDV-2', 'PDV-3']

    with pytest.raises(InvalidInputError) as failure:
        localization.infer_planned_route(dynamodb, OWNER, request, [])
    assert failure.value.detail == LocalizationError.NO_VISITS_TO_INFER.value
