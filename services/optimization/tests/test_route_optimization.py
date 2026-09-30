'''
    Tests for optimizing a route that already exists.

    The question they answer is the one the client asks: this route I already
    have, in what order was it worth doing, and how much would I have saved?
    The proposal must be measurable, drawable, and must never touch the route
    it studies.
'''
from unittest.mock import patch

import pytest
from moto import mock_aws

from schemas.localization import PlannedPointSchema, PlannedRouteCreateSchema
from schemas.route_optimization import RouteOptimizationError
from services import localization, route_optimization as optimizer
from services.exceptions import InvalidInputError
from tests.dynamo_helpers import build_resource

OWNER = 'yo@miempresa.com'

# A square with its stops loaded in the worst possible order: opposite corners
# first, so the route crosses itself twice. Straight-line lengths make the
# saving arithmetic checkable by hand.
CROSSED = [
    ('A', -16.500, -68.100),
    ('C', -16.520, -68.120),
    ('B', -16.500, -68.120),
    ('D', -16.520, -68.100),
]


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''
        A DynamoDB double with the planned routes table.

        Returns:
            ServiceResource: The resource.
    '''
    with mock_aws():
        yield build_resource([(localization.PLANNED_ROUTES_TABLE, 'owner_email', 'id')])


def _plan(
    dynamodb,
    stops: list
) -> dict:
    '''
        Stores a plan with the stops given, in the order given.

        Args:
            dynamodb: The resource.
            stops (list): Tuples of name, latitude and longitude.

        Returns:
            dict: The stored route.
    '''
    return localization.create_planned_route(dynamodb, OWNER, PlannedRouteCreateSchema(
        route_name = 'Prueba', route_code = f'R-{len(stops)}-{stops[0][0]}',
        points = [
            PlannedPointSchema(point_name = name, secuencial = index + 1,
                               latitude = lat, longitude = lon, client_id = f'PDV-{name}')
            for index, (name, lat, lon) in enumerate(stops)
        ]
    ))


def _straight_line_trip(stops: list) -> dict:
    '''
        Stands in for OSRM: the length of the path, in metres, as the crow
        flies. The order is what is under test, not the street network.

        Args:
            stops (list): Ordered (latitude, longitude) pairs.

        Returns:
            dict: Distance, duration and an empty geometry.
    '''
    import numpy as np # pylint: disable=import-outside-toplevel
    from services.optimization import haversine_matrix # pylint: disable=import-outside-toplevel
    if len(stops) < 2:
        return {'distance': 0.0, 'duration': 0.0, 'geometry': []}
    matrix = haversine_matrix(np.array(stops))
    total = sum(matrix[index][index + 1] for index in range(len(stops) - 1))
    return {'distance': float(total), 'duration': float(total) / 10.0,
            'geometry': [[lon, lat] for lat, lon in stops]}


def test_a_crossed_route_is_proposed_untangled_and_the_saving_is_measured(dynamodb):
    '''
        The point of the whole feature.

        A route loaded in the worst order comes back untangled, with both
        orders measured so the saving can be SEEN — a number nobody can check
        is not an argument.
    '''
    plan = _plan(dynamodb, CROSSED)

    with patch.object(optimizer, 'road_trip', _straight_line_trip):
        study = optimizer.optimize_planned_route(dynamodb, OWNER, plan['id'])

    assert study.already_optimal is False
    assert study.saved_metres > 0
    assert study.optimized.distance_metres < study.current.distance_metres
    # Both orders hold the same stops: optimizing is reordering, not dropping.
    assert sorted(stop.point_name for stop in study.optimized.stops) == ['A', 'B', 'C', 'D']
    # Every stop says where it used to be, which is what makes the change
    # readable on screen.
    assert sorted(stop.original_order for stop in study.optimized.stops) == [1, 2, 3, 4]


def test_a_route_already_in_the_best_order_says_so(dynamodb):
    '''
        Defending a route somebody built is worth as much as improving one.
    '''
    plan = _plan(dynamodb, [
        ('A', -16.500, -68.100), ('B', -16.500, -68.120),
        ('C', -16.520, -68.120), ('D', -16.520, -68.100),
    ])

    with patch.object(optimizer, 'road_trip', _straight_line_trip):
        study = optimizer.optimize_planned_route(dynamodb, OWNER, plan['id'])

    assert study.already_optimal is True
    assert study.saved_percentage == 0.0


def test_studying_a_route_never_changes_it(dynamodb):
    '''
        It proposes. Accepting is a separate act, because reordering a route
        somebody is already running is not something a report should do.
    '''
    plan = _plan(dynamodb, CROSSED)

    with patch.object(optimizer, 'road_trip', _straight_line_trip):
        optimizer.optimize_planned_route(dynamodb, OWNER, plan['id'])

    stored = localization.get_planned_route(dynamodb, OWNER, plan['id'])
    assert [stop['point_name'] for stop in stored['points']] == ['A', 'C', 'B', 'D']


def test_a_route_with_two_stops_has_nothing_to_propose(dynamodb):
    '''Two stops have one possible order.'''
    plan = _plan(dynamodb, CROSSED[:2])

    with pytest.raises(InvalidInputError) as refused:
        optimizer.optimize_planned_route(dynamodb, OWNER, plan['id'])
    assert refused.value.detail == RouteOptimizationError.NOT_ENOUGH_STOPS.value


def test_a_route_without_coordinates_cannot_be_studied(dynamodb):
    '''
        Coordinate zero is the absence of a reading, not the Gulf of Guinea,
        so a route of them is a route that cannot go on a map.
    '''
    plan = _plan(dynamodb, [('A', 0.0, 0.0), ('B', 0.0, 0.0), ('C', 0.0, 0.0)])

    with pytest.raises(InvalidInputError) as refused:
        optimizer.optimize_planned_route(dynamodb, OWNER, plan['id'])
    assert refused.value.detail == RouteOptimizationError.NO_COORDINATES.value


def test_the_accepted_order_renumbers_the_stops(dynamodb):
    '''
        Accepting the proposal turns it into stops a route can be built from.
    '''
    plan = _plan(dynamodb, CROSSED)

    with patch.object(optimizer, 'road_trip', _straight_line_trip):
        study = optimizer.optimize_planned_route(dynamodb, OWNER, plan['id'])
    reordered = optimizer.apply_optimized_order(plan['points'], study)

    assert [stop['secuencial'] for stop in reordered] == [1, 2, 3, 4]
    assert [stop['point_name'] for stop in reordered] == \
        [stop.point_name for stop in study.optimized.stops]


def test_repeating_a_route_optimized_creates_it_in_the_better_order(dynamodb):
    '''
        Accepting the proposal.

        The reorder happens on the service and not on the screen, so what is
        created cannot drift from what was shown. The studied route is left
        exactly as it was: this creates a new plan, it does not move an old one.
    '''
    from schemas.localization import RepeatPlannedRouteSchema # pylint: disable=import-outside-toplevel
    from services import localization_sources as sources # pylint: disable=import-outside-toplevel

    plan = _plan(dynamodb, CROSSED)
    with patch.object(optimizer, 'road_trip', _straight_line_trip):
        study = optimizer.optimize_planned_route(dynamodb, OWNER, plan['id'])
        created = sources.repeat_planned_route(
            dynamodb, OWNER, plan['id'],
            RepeatPlannedRouteSchema(plan_date = '2026-10-05', optimized = True)
        )

    assert [stop['point_name'] for stop in created['points']] == \
        [stop.point_name for stop in study.optimized.stops]
    assert [stop['secuencial'] for stop in created['points']] == [1, 2, 3, 4]
    # The route that was studied keeps the order it had.
    untouched = localization.get_planned_route(dynamodb, OWNER, plan['id'])
    assert [stop['point_name'] for stop in untouched['points']] == ['A', 'C', 'B', 'D']
