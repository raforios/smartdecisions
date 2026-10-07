'''
    Optimizing a route that already exists.

    The planner in `optimization.py` builds a week from the sales file, from
    scratch. This does the other half, and the half the client asks for: it
    takes the stops a route ALREADY has —imported, inferred from a worked day,
    or built by a seller on the street— and answers in what order it was worth
    doing them and what that would have saved.

    It reuses the planner's own ordering (`order_stops`: nearest neighbour
    improved by 2-opt) and the same OSRM projection, so the optimized route
    is measured exactly like the planned one. A second implementation would
    be a second answer to one question.

    It proposes and never writes. Accepting the proposal is a separate act.
'''
from typing import Any

import numpy as np
from boto3.resources.base import ServiceResource

from models.localization import PlannedPointItem, PlannedRouteItem
from schemas.route_optimization import (
    OptimizedStopSchema,
    RouteOptimizationError,
    RouteOptimizationSchema,
    RouteShapeSchema
)
from services.exceptions import InvalidInputError
from services.localization import get_planned_route
from services.logger_config import custom_logger as logger
from services.optimization import order_stops
from services.routing import road_trip

# Two stops have one possible order, so there is nothing to propose.
_MIN_STOPS = 3
# A coordinate of exactly zero is the absence of a reading, the same rule the
# rest of the product follows.
_NO_COORDINATE = 0.0


def _placeable(points: list[PlannedPointItem]) -> list[PlannedPointItem]:
    '''
        The stops that can go on a map, in their current order.

        Args:
            points (list[PlannedPointItem]): Stops of the route.

        Returns:
            list[PlannedPointItem]: Those with a real coordinate.
    '''
    return [
        point for point in sorted(points, key = lambda stop: stop['secuencial'])
        if point.get('latitude') not in (None, _NO_COORDINATE)
        and point.get('longitude') not in (None, _NO_COORDINATE)
    ]


def _shape(
    points: list[PlannedPointItem],
    order: list[int]
) -> RouteShapeSchema:
    '''
        One ordering of the stops, measured on real streets.

        Args:
            points (list[PlannedPointItem]): Stops, in their original order.
            order (list[int]): Indices into `points`, in visiting order.

        Returns:
            RouteShapeSchema: The ordering, its length and its geometry.
    '''
    ordered = [points[index] for index in order]
    trip = road_trip([(point['latitude'], point['longitude']) for point in ordered])
    return RouteShapeSchema(
        stops = [
            OptimizedStopSchema(
                point_name = point['point_name'],
                client_id = point.get('client_id'),
                latitude = point['latitude'],
                longitude = point['longitude'],
                order = position + 1,
                original_order = order[position] + 1
            )
            for position, point in enumerate(ordered)
        ],
        distance_metres = trip['distance'],
        duration_seconds = trip['duration'],
        geometry = trip['geometry']
    )


def _savings(
    current: RouteShapeSchema,
    optimized: RouteShapeSchema
) -> tuple[float, float, float]:
    '''
        What the proposal saves against the order the route has today.

        Args:
            current (RouteShapeSchema): The route as it stands.
            optimized (RouteShapeSchema): The proposal.

        Returns:
            tuple[float, float, float]: Metres, seconds and percentage saved.
    '''
    metres = current.distance_metres - optimized.distance_metres
    seconds = current.duration_seconds - optimized.duration_seconds
    share = (metres / current.distance_metres * 100.0) if current.distance_metres else 0.0
    return metres, seconds, share


def optimize_planned_route(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    route_id: str
) -> RouteOptimizationSchema:
    '''
        Proposes a better order for a route the owner already has.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            route_id (str): The route to study.

        Returns:
            RouteOptimizationSchema: Both orders, both measured, and the saving.

        Raises:
            InvalidInputError: NOT_ENOUGH_STOPS when there is nothing to
                reorder, NO_COORDINATES when no stop can be placed on a map.
    '''
    route: PlannedRouteItem = get_planned_route(dynamodb_resource, owner_email, route_id)
    points = _placeable(route.get('points', []))

    if not points:
        error_msg = f'Planned route {route_id} has no stop with coordinates.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = RouteOptimizationError.NO_COORDINATES.value)
    if len(points) < _MIN_STOPS:
        error_msg = f'Planned route {route_id} has {len(points)} placeable stop(s).'
        logger.warning(error_msg)
        raise InvalidInputError(detail = RouteOptimizationError.NOT_ENOUGH_STOPS.value)

    current = _shape(points, list(range(len(points))))
    proposal = order_stops(
        np.array([[point['latitude'], point['longitude']] for point in points])
    )
    optimized = _shape(points, proposal)

    metres, seconds, share = _savings(current, optimized)
    message = (f'Route {route_id} studied: {len(points)} stops, '
               f'{metres:.0f} m and {seconds:.0f} s saved ({share:.1f}%).')
    logger.info(message)

    return RouteOptimizationSchema(
        planned_route_id = route_id,
        route_code = route['route_code'],
        current = current,
        optimized = optimized,
        saved_metres = metres,
        saved_seconds = seconds,
        saved_percentage = max(share, 0.0),
        # The order it has may already be the best one. Saying so defends the
        # route somebody built, which is worth as much as proposing a change.
        already_optimal = proposal == list(range(len(points)))
    )


def apply_optimized_order(
    points: list[PlannedPointItem],
    optimization: RouteOptimizationSchema
) -> list[dict[str, Any]]:
    '''
        The stops of a route renumbered into the proposed order.

        Separate from the study on purpose: reading a proposal and accepting
        it are two decisions, and only the second one changes a route.

        Args:
            points (list[PlannedPointItem]): Stops as stored.
            optimization (RouteOptimizationSchema): The accepted proposal.

        Returns:
            list[dict[str, Any]]: The same stops, with `secuencial` reassigned.
    '''
    placeable = _placeable(points)
    reordered = []
    for stop in optimization.optimized.stops:
        original = placeable[stop.original_order - 1]
        reordered.append({**original, 'secuencial': stop.order})
    return reordered
