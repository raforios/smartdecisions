'''
    Tests for plan-vs-execution scoring and statistics. The score counts a
    planned stop as visited by client id or by proximity; the full comparison
    hands both point lists to the map; the statistics gather a seller's points.
'''
import pytest
from moto import mock_aws

from schemas.daily_stock import DailyStockLoadSchema, SaleItemSchema, StockItemLoadSchema
from schemas.localization import (
    ExecutedPointCreateSchema,
    LocalizationError,
    ExecutedRouteCreateSchema,
    ExecutedRouteFilterSchema,
    ExecutedRouteUpdateSchema,
    PlannedPointSchema,
    PlannedRouteCreateSchema,
    PlannedRouteStatusEnum,
    VisitOutcome
)
from services import daily_stock
from services import localization, localization_executed as executed, localization_stats as stats
from services.day_statistics import day_statistics, route_km
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
            (executed.EXECUTED_ROUTES_TABLE, 'owner_email', 'id'),
            (daily_stock.DAILY_STOCK_TABLE, 'owner_email', 'stock_key')
        ])


@pytest.fixture(name = 'linked_users', autouse = True)
def linked_users_fixture(monkeypatch: pytest.MonkeyPatch) -> set:
    '''
        INGEST's seller directory, in memory: who each seller of the files
        signs in as. Empty unless a test links someone.

        Returns:
            set: The emails linked to the plan's seller, to fill in.
    '''
    linked: set = set()
    monkeypatch.setattr(stats, 'users_of_seller', lambda seller, token: set(linked))
    return linked


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
    fenced: bool = True,
    seller: str = 'Ana'
) -> dict:
    '''
        Opens a route against `plan` and reports `visits` as (lat, lon, client_id).

        `fenced` False skips the stop geofence, to build the state a visits
        FILE produces: those rows are loaded whole and were never policed at
        the door, and the comparison has to score them all the same.
    '''
    route = executed.create_executed_route(dynamodb, OWNER, ExecutedRouteCreateSchema(
        seller = seller, start_time = _at(8), planned_route_id = plan['id'],
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


def test_only_the_plans_own_seller_is_scored_against_it(
    dynamodb,
    plan,
    linked_users
):
    '''
        A plan of Ana measures Ana. Juan running it is not a measure of how
        Ana did; that is how the whole team ended up scored against the
        whole team's stops. Ana's phone reports with her email, linked in
        INGEST's seller master, and it counts as her.
    '''
    linked_users.add('ana@empresa.com')
    _run_route(dynamodb, plan, [(STOPS[0][1], STOPS[0][2], 'PDV-1')], seller = 'Juan')
    _run_route(dynamodb, plan, [(STOPS[0][1], STOPS[0][2], 'PDV-1')], seller = 'ANA@empresa.com')

    result = stats.route_comparisons(dynamodb, OWNER, plan['id'], ExecutedRouteFilterSchema())
    assert [score.seller for score in result.comparisons] == ['ANA@empresa.com']


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


def test_the_day_counts_who_is_out_and_how_much_of_the_plan_was_visited(
    dynamodb,
    plan
):
    '''One open route that visited 2 of the 4 planned stops: one seller out, 50 %.'''
    _run_route(dynamodb, plan, [(STOPS[0][1], STOPS[0][2], 'PDV-1'),
                                (STOPS[1][1], STOPS[1][2], 'PDV-2')])
    today = get_current_time_gmt().date().isoformat()

    day = day_statistics(dynamodb, OWNER, today)

    assert (day.sellers_on_route, day.routes_started, day.routes_closed) == (1, 1, 0)
    assert (day.planned_stops, day.visited_stops) == (4, 2)
    assert day.visit_compliance == 50.0
    assert day.distance_km > 0


def test_a_day_without_routes_has_nothing_to_measure(dynamodb):
    '''No route run: zeros, and no compliance rather than a made-up 0 %.'''
    day = day_statistics(dynamodb, OWNER, '2026-01-02')

    assert day.routes_started == 0
    assert day.visit_compliance is None
    assert day.distance_km == 0.0


def test_the_kilometres_follow_the_points_in_the_order_reported():
    '''Two readings 0.01 degrees of latitude apart are about 1.11 km.'''
    route = {'points': [
        {'latitude': -16.51, 'longitude': -68.1, 'timestamp': '2026-10-12T10:00:00'},
        {'latitude': -16.50, 'longitude': -68.1, 'timestamp': '2026-10-12T09:00:00'},
    ]}

    assert route_km(route) == 1.11



def test_the_day_sells_at_the_price_of_its_stock(
    dynamodb,
    plan
):
    '''Ana sold 3 units of A at 7.50 on a visit: 22.50 Bs, and 7 units remain at 52.50.'''
    today = get_current_time_gmt().date().isoformat()
    daily_stock.load_daily_stock(dynamodb, OWNER, DailyStockLoadSchema(date = today, items = [
        StockItemLoadSchema(sku = 'A', quantity = 10, unit_price = 7.5)]))
    route = executed.create_executed_route(dynamodb, OWNER, ExecutedRouteCreateSchema(
        seller = 'Ana', start_time = _at(8), planned_route_id = plan['id'],
        start_latitude = STOPS[0][1], start_longitude = STOPS[0][2],
        max_distance_start_point = 100))
    executed.register_executed_point(dynamodb, OWNER, ExecutedPointCreateSchema(
        executed_route_id = route['id'], timestamp = _at(9), latitude = STOPS[0][1],
        longitude = STOPS[0][2], client_id = 'PDV-1', outcome = VisitOutcome.SALE,
        items = [SaleItemSchema(sku = 'A', quantity = 3)]))

    day = day_statistics(dynamodb, OWNER, today)

    assert day.sales_amount == 22.5
    assert day.stock_available_value == 52.5
    assert [(row.seller, row.visits, row.units_sold) for row in day.sellers] == [('Ana', 1, 3.0)]


def test_closing_a_route_fixes_its_kilometres(
    dynamodb,
    plan
):
    '''The route keeps what it covered from the moment it closes.'''
    route = _run_route(dynamodb, plan, [(STOPS[0][1], STOPS[0][2], 'PDV-1'),
                                        (STOPS[1][1], STOPS[1][2], 'PDV-2')])
    closed = executed.close_executed_route(dynamodb, OWNER, route['id'], ExecutedRouteUpdateSchema(
        end_time = _at(18), end_latitude = STOPS[1][1], end_longitude = STOPS[1][2],
        max_distance_end_point = _NO_FENCE_M))

    assert closed['distance_km'] == route_km(closed) > 0
    assert executed.to_executed_response(closed).distance_km == closed['distance_km']
