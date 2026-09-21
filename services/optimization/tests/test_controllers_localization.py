'''
    Endpoint-level tests for the route-tracking endpoints (planned and executed).
    They go through the FastAPI app with the security and DynamoDB dependencies
    overridden, so what is asserted is exactly what the frontend will get:
    status codes, DTO shapes and error codes — including the path parameters
    that arrive grouped in `PlannedPointRef`.
'''
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from main import app
from schemas.localization import LocalizationError, PlannedRouteStatusEnum
from services import daily_stock, localization, localization_executed as executed
from services.utils import get_current_time_gmt
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_payload
from tests.dynamo_helpers import build_resource

OWNER = 'yo@miempresa.com'
BASE = '/v1/optimization/routes/planned'
# Token claims of the callers the tests impersonate. OWNER signed up before
# roles existed (REQUESTER, no client); the others belong to one client.
CALLERS = {
    'owner': {'email': OWNER, 'role': 'REQUESTER', 'client': None},
    'manager': {'email': 'gerente@acme.com', 'role': 'MANAGER', 'client': 'acme'},
    'seller': {'email': 'ana@acme.com', 'role': 'SELLER', 'client': 'acme'}
}
EXECUTED = '/v1/optimization/routes/executed'

ROUTE_BODY = {
    'route_name': 'Zona sur',
    'route_code': 'R-001',
    'seller': 'Ana',
    'points': [
        {'point_name': 'Tienda 1', 'secuencial': 1, 'latitude': -16.50, 'longitude': -68.10},
        {'point_name': 'Tienda 2', 'secuencial': 2, 'latitude': -16.51, 'longitude': -68.11}
    ]
}


def act_as(who: str) -> None:
    '''
        Makes every request carry the claims of CALLERS[who].
    '''
    app.dependency_overrides[get_current_payload] = lambda: dict(CALLERS[who])


@pytest.fixture(name = 'client')
def client_fixture():
    '''A test client whose caller is OWNER and whose Dynamo is moto's.'''
    with mock_aws():
        resource = build_resource([
            (localization.PLANNED_ROUTES_TABLE, 'owner_email', 'id'),
            (executed.EXECUTED_ROUTES_TABLE, 'owner_email', 'id'),
            (daily_stock.DAILY_STOCK_TABLE, 'owner_email', 'stock_key')
        ])
        app.dependency_overrides[GET_DB_DEPENDENCY] = lambda: resource
        act_as('owner')
        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()


def _create(client: TestClient) -> dict:
    '''
        Creates ROUTE_BODY and returns the response body.
    '''
    response = client.post(BASE, json = ROUTE_BODY)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_get_planned_route_return_the_dto(client):
    '''POST then GET give the same route: id, status, ordered stops with ids.'''
    created = _create(client)
    assert created['status'] == PlannedRouteStatusEnum.IN_CREATION.value
    assert [stop['secuencial'] for stop in created['points']] == [1, 2]
    assert created['points'][0]['planned_route_id'] == created['id']

    fetched = client.get(f'{BASE}/{created["id"]}')
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_duplicate_code_answers_409_with_the_bare_code(client):
    '''The frontend renders the wording; the API only names the reason.'''
    _create(client)
    response = client.post(BASE, json = ROUTE_BODY)
    assert response.status_code == 409
    assert response.json()['detail'] == LocalizationError.ROUTE_CODE_ALREADY_EXISTS.value


def test_list_and_filter_planned_routes(client):
    '''GET lists; POST /filter narrows, with an empty body meaning "all".'''
    created = _create(client)
    assert [route['id'] for route in client.get(BASE).json()] == [created['id']]

    everything = client.post(f'{BASE}/filter', json = {})
    by_seller = client.post(f'{BASE}/filter', json = {'seller': 'Juan'})
    assert everything.status_code == 200 and len(everything.json()) == 1
    assert by_seller.status_code == 200 and by_seller.json() == []


def test_update_header_and_status(client):
    '''PATCH header keeps the stops; PATCH status refuses illegal moves with facts.'''
    created = _create(client)
    patched = client.patch(f'{BASE}/{created["id"]}', json = {'seller': 'Juan'})
    assert patched.status_code == 200
    assert patched.json()['seller'] == 'Juan'
    assert len(patched.json()['points']) == 2

    refused = client.patch(f'{BASE}/{created["id"]}/status', json = {'status': 'INACTIVE'})
    assert refused.status_code == 400
    assert refused.json()['detail'] == LocalizationError.INVALID_STATUS_TRANSITION.value

    activated = client.patch(f'{BASE}/{created["id"]}/status', json = {'status': 'ACTIVE'})
    assert activated.status_code == 200
    assert activated.json()['status'] == 'ACTIVE'


def test_stop_endpoints_take_both_ids_from_the_path(client):
    '''
        `PlannedPointRef` is filled from the URL, not from the query string:
        add, edit and remove a stop by path alone.
    '''
    created = _create(client)
    added = client.post(
        f'{BASE}/{created["id"]}/points',
        json = {'point_name': 'Tienda 3', 'secuencial': 3, 'latitude': -16.52, 'longitude': -68.12}
    )
    assert added.status_code == 201, added.text
    point_id = added.json()['id']
    assert added.json()['planned_route_id'] == created['id']

    edited = client.patch(
        f'{BASE}/{created["id"]}/points/{point_id}', json = {'point_name': 'Tienda 3 bis'}
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()['point_name'] == 'Tienda 3 bis'

    removed = client.delete(f'{BASE}/{created["id"]}/points/{point_id}')
    assert removed.status_code == 200, removed.text
    assert [stop['secuencial'] for stop in removed.json()['points']] == [1, 2]


def test_delete_planned_route_and_missing_route_is_404(client):
    '''DELETE returns the route as it was; afterwards it is not found.'''
    created = _create(client)
    deleted = client.delete(f'{BASE}/{created["id"]}')
    assert deleted.status_code == 200
    assert deleted.json()['id'] == created['id']
    gone = client.get(f'{BASE}/{created["id"]}')
    assert gone.status_code == 404
    assert gone.json()['detail'] == LocalizationError.ROUTE_NOT_FOUND.value


def test_bulk_upload_planned_routes_from_a_csv_file(client):
    '''A multipart CSV creates the routes; a non-CSV is refused with a code.'''
    csv_body = (
        'route_code,route_name,point_name,secuencial,latitude,longitude\n'
        'R-020,Zona oeste,Tienda X,1,-16.50,-68.20\n'
        'R-020,Zona oeste,Tienda Y,2,-16.51,-68.21\n'
    ).encode('utf-8')
    uploaded = client.post(
        f'{BASE}/bulk-upload', files = {'file': ('plan.csv', csv_body, 'text/csv')}
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()['routes_created'] == 1
    assert uploaded.json()['points_created'] == 2
    assert client.get(f'{BASE}/{uploaded.json()["route_ids"][0]}').status_code == 200

    refused = client.post(
        f'{BASE}/bulk-upload', files = {'file': ('plan.xlsx', b'PK...', 'application/zip')}
    )
    assert refused.status_code == 400
    assert refused.json()['detail'] == 'UNSUPPORTED_FILE_TYPE'


# ---------------------------------------------------------------------------
# Executed routes
# ---------------------------------------------------------------------------
def _now_iso(hour: int) -> str:
    '''
        Today at `hour` in the service timezone, ISO 8601.
    '''
    return get_current_time_gmt().replace(
        hour = hour, minute = 0, second = 0, microsecond = 0
    ).isoformat()


def _activate(
    client: TestClient,
    route: dict
) -> None:
    '''
        Moves a fresh route to ACTIVE.
    '''
    response = client.patch(f'{BASE}/{route["id"]}/status', json = {'status': 'ACTIVE'})
    assert response.status_code == 200


def test_executed_route_full_day_through_the_api(client):
    '''
        Start against the plan, report a visit, locate the seller, close,
        reopen, read the detail — the day of a seller, end to end.
    '''
    plan = _create(client)
    _activate(client, plan)
    started = client.post(EXECUTED, json = {
        'seller': 'Ana', 'start_time': _now_iso(8), 'planned_route_id': plan['id'],
        'start_latitude': -16.50, 'start_longitude': -68.10, 'max_distance_start_point': 100
    })
    assert started.status_code == 201, started.text
    route_id = started.json()['id']
    assert started.json()['points_count'] == 0

    visit = client.post(f'{EXECUTED}/points', json = {
        'executed_route_id': route_id, 'timestamp': _now_iso(9),
        'latitude': -16.51, 'longitude': -68.11,
        'client_id': 'PDV-2', 'outcome': 'VENTA', 'order_id': 'F-0001'
    })
    assert visit.status_code == 201, visit.text
    assert visit.json()['executed_route_id'] == route_id

    located = client.get(f'{EXECUTED}/last-location', params = {'sellers': ['Ana', 'Juan']})
    assert located.status_code == 200, located.text
    assert located.json()['locations'] == [{
        'seller': 'Ana', 'executed_route_id': route_id,
        'last_latitude': -16.51, 'last_longitude': -68.11, 'last_timestamp': _now_iso(9)
    }]

    closed = client.patch(f'{EXECUTED}/{route_id}', json = {
        'end_time': _now_iso(17), 'end_latitude': -16.51, 'end_longitude': -68.11,
        'max_distance_end_point': 100
    })
    assert closed.status_code == 200, closed.text
    assert closed.json()['end_time'] == _now_iso(17)

    reopened = client.patch(f'{EXECUTED}/{route_id}/reopen')
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()['end_time'] is None

    detail = client.get(f'{EXECUTED}/{route_id}')
    assert detail.status_code == 200
    assert detail.json()['points_count'] == 1
    assert detail.json()['points'][0]['outcome'] == 'VENTA'

    listed = client.get(EXECUTED, params = {'seller': 'Ana'})
    assert listed.status_code == 200
    assert [route['id'] for route in listed.json()] == [route_id]


def test_executed_route_errors_carry_their_codes(client):
    '''Geofence, inactive plan and unknown route each answer with a bare code.'''
    plan = _create(client)
    body = {
        'seller': 'Ana', 'start_time': _now_iso(8), 'planned_route_id': plan['id'],
        'start_latitude': -16.50, 'start_longitude': -68.10, 'max_distance_start_point': 100
    }
    inactive = client.post(EXECUTED, json = body)
    assert inactive.status_code == 400
    assert inactive.json()['detail'] == LocalizationError.PLANNED_ROUTE_NOT_ACTIVE.value

    _activate(client, plan)
    far = client.post(EXECUTED, json = {**body, 'start_latitude': -16.9})
    assert far.status_code == 400
    assert far.json()['detail'] == LocalizationError.OUTSIDE_START_GEOFENCE.value

    missing = client.get(f'{EXECUTED}/20260101T080000-deadbeef')
    assert missing.status_code == 404


# ---------------------------------------------------------------------------
# Comparison and statistics
# ---------------------------------------------------------------------------
def test_comparison_and_statistics_endpoints(client):
    '''
        After one execution with one matched stop: the score, the two point
        lists and the seller's points all come back built, and the path
        parameters shared with the filter model resolve from the URL.
    '''
    plan = _create(client)
    _activate(client, plan)
    started = client.post(EXECUTED, json = {
        'seller': 'Ana', 'start_time': _now_iso(8), 'planned_route_id': plan['id'],
        'start_latitude': -16.50, 'start_longitude': -68.10, 'max_distance_start_point': 100
    }).json()
    client.post(f'{EXECUTED}/points', json = {
        'executed_route_id': started['id'], 'timestamp': _now_iso(9),
        'latitude': -16.51, 'longitude': -68.11, 'client_id': 'PDV-2', 'outcome': 'VENTA'
    })

    scored = client.get(f'/v1/optimization/statistics/route-comparisons/{plan["id"]}')
    assert scored.status_code == 200, scored.text
    comparison = scored.json()['comparisons'][0]
    assert comparison['executed_route_id'] == started['id']
    assert comparison['matched_points_count'] == 1
    assert comparison['match_percentage'] == 50.0

    full = client.get(f'/v1/optimization/routes/comparison/{plan["id"]}',
                      params = {'seller': 'Ana'})
    assert full.status_code == 200, full.text
    assert len(full.json()['planned_route']['points']) == 2
    assert full.json()['executed_routes'][0]['points'][0]['client_id'] == 'PDV-2'

    other_seller = client.get(f'/v1/optimization/routes/comparison/{plan["id"]}',
                              params = {'seller': 'Juan'})
    assert other_seller.json()['executed_routes'] == []

    visited = client.get('/v1/optimization/statistics/sellers/Ana/points-visited')
    assert visited.status_code == 200, visited.text
    assert visited.json()['total_points_visited'] == 1
    assert visited.json()['points_details'][0]['outcome'] == 'VENTA'


def test_infer_planned_route_from_a_day_without_plan(client):
    '''A free day becomes a plan and its route gets linked; an empty day is refused.'''
    started = client.post(EXECUTED, json = {
        'seller': 'Juan', 'start_time': _now_iso(8),
        'start_latitude': -17.0, 'start_longitude': -65.0, 'max_distance_start_point': 100
    }).json()
    for hour, client_id in ((9, 'PDV-7'), (10, 'PDV-8')):
        client.post(f'{EXECUTED}/points', json = {
            'executed_route_id': started['id'], 'timestamp': _now_iso(hour),
            'latitude': -17.0 - hour / 1000, 'longitude': -65.0, 'client_id': client_id
        })
    today = get_current_time_gmt().date().isoformat()

    inferred = client.post(f'{BASE}/infer', json = {'seller': 'Juan', 'date': today})
    assert inferred.status_code == 201, inferred.text
    assert [stop['client_id'] for stop in inferred.json()['points']] == ['PDV-7', 'PDV-8']
    relinked = client.get(f'{EXECUTED}/{started["id"]}').json()
    assert relinked['planned_route_id'] == inferred.json()['id']

    empty = client.post(f'{BASE}/infer', json = {'seller': 'Nadie', 'date': today})
    assert empty.status_code == 400
    assert empty.json()['detail'] == LocalizationError.NO_VISITS_TO_INFER.value


# ---------------------------------------------------------------------------
# Daily stock
# ---------------------------------------------------------------------------
def test_daily_stock_load_sale_on_visit_and_remaining(client):
    '''
        Load the day, sell two on a visit, read what is left; a sale beyond the
        stock is refused with its code and the visit is not recorded.
    '''
    today = get_current_time_gmt().date().isoformat()
    loaded = client.put('/v1/optimization/stock/day', json = {
        'date': today,
        'items': [{'sku': 'A', 'quantity': 3, 'product_name': 'Agua 2L'},
                  {'sku': 'B', 'quantity': 1}]
    })
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()['skus_loaded'] == 2 and loaded.json()['skus_out_of_stock'] == 0

    started = client.post(EXECUTED, json = {
        'seller': 'Ana', 'start_time': _now_iso(8),
        'start_latitude': -16.5, 'start_longitude': -68.1, 'max_distance_start_point': 100
    }).json()
    sold = client.post(f'{EXECUTED}/points', json = {
        'executed_route_id': started['id'], 'timestamp': _now_iso(10),
        'latitude': -16.5, 'longitude': -68.1, 'client_id': 'PDV-1', 'outcome': 'VENTA',
        'order_id': 'F-0001', 'items': [{'sku': 'A', 'quantity': 2}, {'sku': 'B', 'quantity': 1}]
    })
    assert sold.status_code == 201, sold.text

    remaining = client.get(f'/v1/optimization/stock/day/{today}')
    assert remaining.status_code == 200
    by_sku = {row['sku']: row for row in remaining.json()['items']}
    assert (by_sku['A']['available_quantity'], by_sku['B']['available_quantity']) == (1, 0)
    assert remaining.json()['skus_out_of_stock'] == 1

    refused = client.post(f'{EXECUTED}/points', json = {
        'executed_route_id': started['id'], 'timestamp': _now_iso(11),
        'latitude': -16.5, 'longitude': -68.1, 'client_id': 'PDV-2', 'outcome': 'VENTA',
        'items': [{'sku': 'A', 'quantity': 2}]
    })
    assert refused.status_code == 400
    assert refused.json()['detail'] == 'INSUFFICIENT_STOCK'
    assert client.get(f'{EXECUTED}/{started["id"]}').json()['points_count'] == 1


# ---------------------------------------------------------------------------
# Roles and the client grouping
# ---------------------------------------------------------------------------
def test_manager_and_seller_of_one_client_share_the_data(client):
    '''
        The manager plans; the seller sees that plan, because both are keyed by
        the client and not by their emails. The lone REQUESTER account sees
        nothing of it: its key is its own email.
    '''
    act_as('manager')
    plan = _create(client)
    _activate(client, plan)

    act_as('seller')
    seen = client.get(BASE)
    assert seen.status_code == 200
    assert [route['id'] for route in seen.json()] == [plan['id']]

    act_as('owner')
    assert client.get(BASE).json() == []


def test_seller_is_kept_to_field_work(client):
    '''
        A seller cannot plan, load stock or read the live view (403 with a
        code); can run a route, but only as themselves.
    '''
    act_as('seller')
    for refused in (
        client.post(BASE, json = ROUTE_BODY),
        client.put('/v1/optimization/stock/day',
                   json = {'date': '2026-09-21', 'items': [{'sku': 'A', 'quantity': 1}]}),
        client.get(f'{EXECUTED}/last-location', params = {'sellers': ['ana@acme.com']})
    ):
        assert refused.status_code == 403, refused.text
        assert refused.json()['detail'] == 'ROLE_NOT_ALLOWED'

    started = client.post(EXECUTED, json = {
        'seller': 'Otro Vendedor', 'start_time': _now_iso(8),
        'start_latitude': -16.5, 'start_longitude': -68.1, 'max_distance_start_point': 100
    })
    assert started.status_code == 201, started.text
    assert started.json()['seller'] == 'ana@acme.com'

    act_as('manager')
    other = client.post(EXECUTED, json = {
        'seller': 'juan@acme.com', 'start_time': _now_iso(8),
        'start_latitude': -16.5, 'start_longitude': -68.1, 'max_distance_start_point': 100
    })
    assert other.status_code == 201

    act_as('seller')
    mine = client.get(EXECUTED, params = {'seller': 'juan@acme.com'})
    assert [route['seller'] for route in mine.json()] == ['ana@acme.com']
