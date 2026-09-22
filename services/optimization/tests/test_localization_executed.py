'''
    Tests for the executed-routes logic ported from LOCALIZATION onto DynamoDB.
    One test per service function, plus the rules the port kept: start and end
    geofenced against the plan, only ACTIVE plans can be run, a closed route
    takes no more points, reopen only the same day, and the live view answers
    the latest position per seller within the lookback window.
'''
from datetime import timedelta
from unittest.mock import patch

import pytest
from moto import mock_aws

from schemas.localization import (
    ExecutedPointCreateSchema,
    ExecutedRouteCreateSchema,
    ExecutedRouteFilterSchema,
    ExecutedRouteUpdateSchema,
    LocalizationError,
    PlannedPointSchema,
    PlannedRouteCreateSchema,
    PlannedRouteStatusEnum,
    VisitOutcome
)
from services import localization, localization_executed as executed
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.utils import get_current_time_gmt
from tests.dynamo_helpers import build_resource

OWNER = 'yo@miempresa.com'
OTHER = 'otra@empresa.com'
FIRST_STOP = (-16.5000, -68.1000)
LAST_STOP = (-16.5200, -68.1200)


def _today_at(hour: int) -> str:
    '''
        ISO timestamp for today at `hour`, in the service timezone.
    '''
    now = get_current_time_gmt()
    return now.replace(hour = hour, minute = 0, second = 0, microsecond = 0).isoformat()


def _start_payload(
    planned_route_id: str | None = None,
    seller: str = 'Ana',
    start: tuple = FIRST_STOP
) -> ExecutedRouteCreateSchema:
    '''
        A route start at `start`, 150 m of tolerance.
    '''
    return ExecutedRouteCreateSchema(
        seller = seller,
        start_time = _today_at(8),
        planned_route_id = planned_route_id,
        start_latitude = start[0],
        start_longitude = start[1],
        max_distance_start_point = 150
    )


def _end_payload(end: tuple = LAST_STOP) -> ExecutedRouteUpdateSchema:
    '''
        A route end at `end`, 150 m of tolerance.
    '''
    return ExecutedRouteUpdateSchema(
        end_time = _today_at(17),
        end_latitude = end[0],
        end_longitude = end[1],
        max_distance_end_point = 150
    )


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Both tracking tables, mocked.'''
    with mock_aws():
        yield build_resource([
            (localization.PLANNED_ROUTES_TABLE, 'owner_email', 'id'),
            (executed.EXECUTED_ROUTES_TABLE, 'owner_email', 'id')
        ])


@pytest.fixture(name = 'active_plan')
def active_plan_fixture(dynamodb):
    '''An ACTIVE plan of OWNER whose first stop is FIRST_STOP and last is LAST_STOP.'''
    plan = localization.create_planned_route(dynamodb, OWNER, PlannedRouteCreateSchema(
        route_name = 'Zona sur', route_code = 'R-001', seller = 'Ana',
        points = [
            PlannedPointSchema(point_name = 'Tienda 1', secuencial = 1,
                               latitude = FIRST_STOP[0], longitude = FIRST_STOP[1],
                               client_id = 'PDV-1'),
            PlannedPointSchema(point_name = 'Tienda 2', secuencial = 2,
                               latitude = -16.51, longitude = -68.11, client_id = 'PDV-2'),
            PlannedPointSchema(point_name = 'Tienda 3', secuencial = 3,
                               latitude = LAST_STOP[0], longitude = LAST_STOP[1],
                               client_id = 'PDV-3')
        ]
    ))
    return localization.update_planned_route_status(
        dynamodb, OWNER, plan['id'], PlannedRouteStatusEnum.ACTIVE
    )


@pytest.fixture(name = 'open_route')
def open_route_fixture(
    dynamodb,
    active_plan
):
    '''A route Ana just started against the active plan.'''
    return executed.create_executed_route(
        dynamodb, OWNER, _start_payload(planned_route_id = active_plan['id'])
    )


# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------
def test_build_executed_id_sorts_by_start_and_rejects_garbage():
    '''The key starts with the stamp, so later starts sort later.'''
    earlier = executed.build_executed_id('2026-09-20T08:00:00-04:00')
    later = executed.build_executed_id('2026-09-20T09:30:00-04:00')
    assert earlier.startswith('20260920T080000-') and later.startswith('20260920T093000-')
    assert earlier < later
    with pytest.raises(InvalidInputError) as failure:
        executed.build_executed_id('ayer a la mañana')
    assert failure.value.detail == LocalizationError.INVALID_ROW.value


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
def test_create_executed_route_without_plan_stores_the_start(dynamodb):
    '''A free route (no plan) opens anywhere and starts with no points.'''
    route = executed.create_executed_route(dynamodb, OWNER, _start_payload(start = (-17.0, -65.0)))
    stored = executed.get_executed_route(dynamodb, OWNER, route['id'])
    assert stored['seller'] == 'Ana'
    assert stored['end_time'] is None
    assert stored['points'] == []
    assert (stored['last_latitude'], stored['last_longitude']) == (-17.0, -65.0)


def test_create_executed_route_against_plan_checks_status_and_geofence(
    dynamodb,
    active_plan
):
    '''Only an ACTIVE plan, and only from within reach of its first stop.'''
    far_away = _start_payload(planned_route_id = active_plan['id'], start = (-16.60, -68.10))
    with pytest.raises(InvalidInputError) as failure:
        executed.create_executed_route(dynamodb, OWNER, far_away)
    assert failure.value.detail == LocalizationError.OUTSIDE_START_GEOFENCE.value

    localization.update_planned_route_status(
        dynamodb, OWNER, active_plan['id'], PlannedRouteStatusEnum.INACTIVE
    )
    with pytest.raises(InvalidInputError) as failure:
        executed.create_executed_route(
            dynamodb, OWNER, _start_payload(planned_route_id = active_plan['id'])
        )
    assert failure.value.detail == LocalizationError.PLANNED_ROUTE_NOT_ACTIVE.value


def test_create_executed_route_against_a_foreign_plan_is_not_found(
    dynamodb,
    active_plan
):
    '''Another owner cannot run my plan: it does not exist for them.'''
    with pytest.raises(RegisterNotFoundError):
        executed.create_executed_route(
            dynamodb, OTHER, _start_payload(planned_route_id = active_plan['id'])
        )


def test_register_executed_point_appends_and_moves_last_position(
    dynamodb,
    open_route
):
    '''A visit lands on the route with its outcome; the live position follows it.'''
    route, point = executed.register_executed_point(dynamodb, OWNER, ExecutedPointCreateSchema(
        executed_route_id = open_route['id'], timestamp = _today_at(9),
        latitude = -16.51, longitude = -68.11,
        client_id = 'PDV-2', outcome = VisitOutcome.SALE, order_id = 'F-0001'
    ))
    assert point['outcome'] == 'VENTA'
    assert route['points'][-1]['id'] == point['id']
    assert (route['last_latitude'], route['last_longitude']) == (-16.51, -68.11)
    assert route['last_timestamp'] == _today_at(9)


def test_close_executed_route_checks_end_geofence_and_refuses_twice(
    dynamodb,
    open_route
):
    '''The end must be near the last stop; a closed route cannot be closed or fed again.'''
    with pytest.raises(InvalidInputError) as failure:
        executed.close_executed_route(
            dynamodb, OWNER, open_route['id'], _end_payload(end = (-16.60, -68.20))
        )
    assert failure.value.detail == LocalizationError.OUTSIDE_END_GEOFENCE.value

    closed = executed.close_executed_route(dynamodb, OWNER, open_route['id'], _end_payload())
    assert closed['end_time'] == _today_at(17)
    assert closed['max_distance_end_point'] == 150

    with pytest.raises(InvalidInputError) as failure:
        executed.close_executed_route(dynamodb, OWNER, open_route['id'], _end_payload())
    assert failure.value.detail == LocalizationError.ROUTE_ALREADY_CLOSED.value
    with pytest.raises(InvalidInputError):
        executed.register_executed_point(dynamodb, OWNER, ExecutedPointCreateSchema(
            executed_route_id = open_route['id'], timestamp = _today_at(18),
            latitude = -16.5, longitude = -68.1
        ))


def test_reopen_executed_route_same_day_only(
    dynamodb,
    open_route
):
    '''Reopen clears the end; refused when already open or started another day.'''
    with pytest.raises(InvalidInputError) as failure:
        executed.reopen_executed_route(dynamodb, OWNER, open_route['id'])
    assert failure.value.detail == LocalizationError.ROUTE_ALREADY_OPEN.value

    executed.close_executed_route(dynamodb, OWNER, open_route['id'], _end_payload())
    reopened = executed.reopen_executed_route(dynamodb, OWNER, open_route['id'])
    assert reopened['end_time'] is None and reopened['end_latitude'] is None

    executed.close_executed_route(dynamodb, OWNER, open_route['id'], _end_payload())
    tomorrow = get_current_time_gmt() + timedelta(days = 1)
    with patch.object(executed, 'get_current_time_gmt', lambda: tomorrow):
        with pytest.raises(InvalidInputError) as failure:
            executed.reopen_executed_route(dynamodb, OWNER, open_route['id'])
    assert failure.value.detail == LocalizationError.REOPEN_NOT_SAME_DAY.value


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def test_list_executed_routes_bounds_by_date_and_narrows_by_seller_and_plan(
    dynamodb,
    open_route
):
    '''The date range is the Query; seller and plan filter what it returned.'''
    executed.create_executed_route(dynamodb, OWNER, _start_payload(seller = 'Juan',
                                                                   start = (-17.0, -65.0)))
    executed.create_executed_route(dynamodb, OTHER, _start_payload(start = (-17.0, -65.0)))
    today = get_current_time_gmt().date().isoformat()

    everything = executed.list_executed_routes(dynamodb, OWNER, ExecutedRouteFilterSchema())
    todays = executed.list_executed_routes(
        dynamodb, OWNER, ExecutedRouteFilterSchema(date_from = today, date_to = today)
    )
    by_plan = executed.list_executed_routes(
        dynamodb, OWNER,
        ExecutedRouteFilterSchema(planned_route_id = open_route['planned_route_id'])
    )
    by_seller = executed.list_executed_routes(
        dynamodb, OWNER, ExecutedRouteFilterSchema(seller = 'Juan')
    )
    yesterday = (get_current_time_gmt().date() - timedelta(days = 1)).isoformat()
    none = executed.list_executed_routes(
        dynamodb, OWNER, ExecutedRouteFilterSchema(date_to = yesterday)
    )
    assert len(everything) == 2 and len(todays) == 2
    assert [route['id'] for route in by_plan] == [open_route['id']]
    assert [route['seller'] for route in by_seller] == ['Juan']
    assert none == []


def test_get_executed_route_of_another_owner_is_not_found(
    dynamodb,
    open_route
):
    '''A foreign executed route answers like a missing one.'''
    with pytest.raises(RegisterNotFoundError):
        executed.get_executed_route(dynamodb, OTHER, open_route['id'])


def test_last_known_locations_answers_latest_per_seller_in_window(
    dynamodb,
    open_route
):
    '''
        Ana's newest position wins over her start; Juan is located too; a
        seller with nothing reported is simply absent.
    '''
    executed.register_executed_point(dynamodb, OWNER, ExecutedPointCreateSchema(
        executed_route_id = open_route['id'], timestamp = _today_at(11),
        latitude = -16.55, longitude = -68.15
    ))
    executed.create_executed_route(dynamodb, OWNER, _start_payload(seller = 'Juan',
                                                                   start = (-17.0, -65.0)))
    located = executed.last_known_locations(dynamodb, OWNER, ['Ana', 'Juan', 'Nadie'])
    by_seller = {entry.seller: entry for entry in located}
    assert set(by_seller) == {'Ana', 'Juan'}
    assert (by_seller['Ana'].last_latitude, by_seller['Ana'].last_longitude) == (-16.55, -68.15)
    assert by_seller['Ana'].executed_route_id == open_route['id']
    assert by_seller['Juan'].last_timestamp == _today_at(8)


def test_last_known_locations_ignores_routes_older_than_the_lookback(
    dynamodb,
    open_route
):
    '''Beyond ROUTES_LIVE_LOOKBACK_DAYS a position is history, not "now".'''
    far_future = get_current_time_gmt() + timedelta(days = executed.LIVE_LOOKBACK_DAYS + 1)
    with patch.object(executed, 'get_current_time_gmt', lambda: far_future):
        assert executed.last_known_locations(dynamodb, OWNER, ['Ana']) == []
    assert open_route['seller'] == 'Ana'


def test_to_executed_detail_builds_the_dto_with_points(
    dynamodb,
    open_route
):
    '''Header plus points, native numbers, count matching the list.'''
    executed.register_executed_point(dynamodb, OWNER, ExecutedPointCreateSchema(
        executed_route_id = open_route['id'], timestamp = _today_at(9),
        latitude = -16.51, longitude = -68.11, client_id = 'PDV-2', outcome = VisitOutcome.NO_SALE
    ))
    stored = executed.get_executed_route(dynamodb, OWNER, open_route['id'])
    detail = executed.to_executed_detail(stored)
    assert detail.points_count == 1 and len(detail.points) == 1
    assert detail.points[0].executed_route_id == open_route['id']
    assert detail.points[0].outcome is VisitOutcome.NO_SALE
    assert isinstance(detail.points[0].latitude, float)
    header = executed.to_executed_response(stored)
    assert header.points_count == 1 and not hasattr(header, 'points')


def test_link_routes_to_plan_only_touches_routes_without_a_plan(
    dynamodb,
    open_route
):
    '''A free route gets the plan; one already planned keeps its own.'''
    free = executed.create_executed_route(
        dynamodb, OWNER, _start_payload(seller = 'Juan', start = (-17.0, -65.0))
    )
    linked = executed.link_routes_to_plan(dynamodb, [open_route, free], 'plan-nuevo')
    assert linked == 1
    relinked = executed.get_executed_route(dynamodb, OWNER, free['id'])
    assert relinked['planned_route_id'] == 'plan-nuevo'
    assert executed.get_executed_route(
        dynamodb, OWNER, open_route['id']
    )['planned_route_id'] == open_route['planned_route_id']


def test_parse_timestamp_moves_device_time_to_the_service_day():
    '''
        A phone reporting 01:15 UTC on the 22nd is still on the 21st in La Paz:
        the route key, the stock day and the reopen check must all say the 21st.
    '''
    local = executed.parse_timestamp('2026-09-22T01:15:56Z')
    assert local.date().isoformat() == '2026-09-21'
    assert executed.build_executed_id('2026-09-22T01:15:56Z').startswith('20260921T2115')
    naive = executed.parse_timestamp('2026-09-21T21:15:56')
    assert naive.tzinfo is not None and naive.hour == 21
