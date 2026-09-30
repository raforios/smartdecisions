'''
    Tests for plan-vs-execution scoring and statistics. The score counts a
    planned stop as visited by client id or by proximity; the full comparison
    hands both point lists to the map; the statistics gather a seller's points.
'''
import pytest
from moto import mock_aws

from schemas.localization import (
    ExecutedPointCreateSchema,
    LocalizationError,
    ExecutedRouteCreateSchema,
    ExecutedRouteFilterSchema,
    PlannedPointSchema,
    PlannedRouteCreateSchema,
    PlannedRouteStatusEnum,
    VisitOutcome
)
from services import localization, localization_executed as executed, localization_stats as stats
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.utils import get_current_time_gmt
from tests.dynamo_helpers import build_resource

# Wide enough that no reading is ever outside it: the file door has no fence.
_NO_FENCE_M = 100_000_000.0

OWNER = 'yo@miempresa.com'
STOPS = [
    ('Tienda 1', -16.5000, -68.1000, 'PDV-1'),
    ('Tienda 2', -16.5100, -68.1100, 'PDV-2'),
    ('Tienda 3', -16.5200, -68.1200, 'PDV-3'),
    ('Tienda 4', -16.5300, -68.1300, None)
]


def _at(hour: int) -> str:
    '''
        Today at `hour`, ISO 8601, service timezone.
    '''
    return get_current_time_gmt().replace(
        hour = hour, minute = 0, second = 0, microsecond = 0
    ).isoformat()


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Both tracking tables, mocked.'''
    with mock_aws():
        yield build_resource([
            (localization.PLANNED_ROUTES_TABLE, 'owner_email', 'id'),
            (executed.EXECUTED_ROUTES_TABLE, 'owner_email', 'id')
        ])


@pytest.fixture(name = 'plan')
def plan_fixture(dynamodb):
    '''An ACTIVE four-stop plan; the last stop has no client id.'''
    created = localization.create_planned_route(dynamodb, OWNER, PlannedRouteCreateSchema(
        route_name = 'Zona sur', route_code = 'R-001', seller = 'Ana',
        points = [
            PlannedPointSchema(point_name = name, secuencial = index + 1,
                               latitude = lat, longitude = lon, client_id = client)
            for index, (name, lat, lon, client) in enumerate(STOPS)
        ]
    ))
    return localization.update_planned_route_status(
        dynamodb, OWNER, created['id'], PlannedRouteStatusEnum.ACTIVE
    )


def _run_route(
    dynamodb,
    plan: dict,
    visits: list,
    fenced: bool = True
) -> dict:
    '''
        Opens a route against `plan` and reports `visits` as (lat, lon, client_id).

        `fenced` False skips the stop geofence, to build the state a visits
        FILE produces: those rows are loaded whole and were never policed at
        the door, and the comparison has to score them all the same.
    '''
    route = executed.create_executed_route(dynamodb, OWNER, ExecutedRouteCreateSchema(
        seller = 'Ana', start_time = _at(8), planned_route_id = plan['id'],
        start_latitude = STOPS[0][1], start_longitude = STOPS[0][2],
        max_distance_start_point = 100
    ))
    for hour, (lat, lon, client) in enumerate(visits, start = 9):
        point = ExecutedPointCreateSchema(
            executed_route_id = route['id'], timestamp = _at(hour),
            latitude = lat, longitude = lon, client_id = client,
            outcome = VisitOutcome.SALE if client else None
        )
        if not fenced:
            point = point.model_copy(update = {'max_distance_stop_point': _NO_FENCE_M})
        route, _ = executed.register_executed_point(dynamodb, OWNER, point)
    return route


def test_score_execution_matches_by_client_or_proximity(
    dynamodb,
    plan
):
    '''
        Stop 1 by client id from far away, stop 4 (no client) by proximity,
        stop 2 by neither, stop 3 not visited: 2 of 4.

        The far-away visit can no longer be REGISTERED by a device —the stop
        geofence refuses it— but it still arrives in a visits file, which is
        loaded whole. The comparison scores what is stored, whichever door it
        came through.
    '''
    route = _run_route(dynamodb, plan, fenced = False, visits = [
        (-16.4000, -68.0000, 'PDV-1'),          # names the client, 15 km away
        (-16.5301, -68.1300, None),             # ~11 m from stop 4
        (-16.5150, -68.1150, None)              # between 2 and 3, ~780 m from each
    ])
    score = stats.score_execution(plan, route)
    assert score.matched_points_count == 2
    assert score.planned_points_count == 4
    assert score.points_visited_count == 3
    assert score.match_percentage == 50.0
    assert score.seller == 'Ana'


def test_score_execution_with_an_empty_plan_is_zero(plan):
    '''No stops, nothing to match: 0 %, not a division error.'''
    empty = {**plan, 'points': []}
    score = stats.score_execution(empty, {'id': 'x', 'seller': 'Ana', 'points': []})
    assert score.match_percentage == 0.0 and score.planned_points_count == 0


def test_route_comparisons_scores_every_execution_in_the_period(
    dynamodb,
    plan
):
    '''Two runs of the same plan, two scores; a seller with none gives an empty list.'''
    _run_route(dynamodb, plan, [(STOPS[0][1], STOPS[0][2], 'PDV-1')])
    _run_route(dynamodb, plan, [(lat, lon, client) for _, lat, lon, client in STOPS])

    result = stats.route_comparisons(dynamodb, OWNER, plan['id'], ExecutedRouteFilterSchema())
    assert sorted(score.match_percentage for score in result.comparisons) == [25.0, 100.0]

    none = stats.route_comparisons(
        dynamodb, OWNER, plan['id'], ExecutedRouteFilterSchema(seller = 'Nadie')
    )
    assert none.comparisons == []


def test_route_comparisons_of_a_foreign_plan_is_not_found(
    dynamodb,
    plan
):
    '''Another owner asking about my plan gets not found.'''
    with pytest.raises(RegisterNotFoundError):
        stats.route_comparisons(dynamodb, 'otra@empresa.com', plan['id'],
                                ExecutedRouteFilterSchema())


def test_full_route_comparison_returns_both_point_lists(
    dynamodb,
    plan
):
    '''The map gets the planned stops and each execution with its points.'''
    _run_route(dynamodb, plan, [(STOPS[1][1], STOPS[1][2], 'PDV-2')])
    result = stats.full_route_comparison(dynamodb, OWNER, plan['id'], ExecutedRouteFilterSchema())
    assert result.planned_route.id == plan['id']
    assert [stop.secuencial for stop in result.planned_route.points] == [1, 2, 3, 4]
    assert len(result.executed_routes) == 1
    assert result.executed_routes[0].points[0].client_id == 'PDV-2'
    assert result.executed_routes[0].points[0].outcome is VisitOutcome.SALE


def test_points_visited_gathers_a_sellers_points_across_routes(
    dynamodb,
    plan
):
    '''Two routes, three points in total; another seller has none.'''
    _run_route(dynamodb, plan, [(STOPS[0][1], STOPS[0][2], 'PDV-1')])
    _run_route(dynamodb, plan, [(STOPS[1][1], STOPS[1][2], 'PDV-2'),
                                (STOPS[2][1], STOPS[2][2], 'PDV-3')])
    ana = stats.points_visited(dynamodb, OWNER, 'Ana', ExecutedRouteFilterSchema())
    nobody = stats.points_visited(dynamodb, OWNER, 'Juan', ExecutedRouteFilterSchema())
    assert ana.total_points_visited == 3
    assert sorted(point.client_id for point in ana.points_details) == ['PDV-1', 'PDV-2', 'PDV-3']
    assert nobody.total_points_visited == 0 and nobody.points_details == []


def test_a_visit_far_from_its_planned_stop_is_refused(
    dynamodb,
    plan
):
    '''
        Registering attendance from anywhere was the hole.

        A seller could mark a client without going near them and the
        comparison reported the route as met. Naming the stop is not enough:
        the reading has to be at it.
    '''
    with pytest.raises(InvalidInputError) as refused:
        _run_route(dynamodb, plan, [(-16.4000, -68.0000, 'PDV-1')])
    assert refused.value.detail == LocalizationError.OUTSIDE_STOP_GEOFENCE.value


def test_a_stop_the_plan_does_not_know_is_never_fenced(
    dynamodb,
    plan
):
    '''
        A place the plan never mentioned is a NEW client, which is exactly
        what has to be reported — blocking it would throw away the only
        evidence that the route should grow.
    '''
    route = _run_route(dynamodb, plan, [(-16.4000, -68.0000, 'PDV-NUEVO')])
    assert len(route['points']) == 1
