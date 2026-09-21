'''
    Plan vs execution — comparison and statistics, ported from LOCALIZATION.

    LOCALIZATION returned the two point lists and left `match_percentage` at
    zero for the frontend to work out. Here the score is computed: a planned
    stop counts as visited when a reported point names its client or falls
    within `ROUTES_VISIT_MATCH_RADIUS_M` metres of it. The map still gets both
    lists through the full comparison.
'''
from typing import List

from boto3.resources.base import ServiceResource

from models.localization import (
    ExecutedPointItem,
    ExecutedRouteItem,
    PlannedPointItem,
    PlannedRouteItem
)
from schemas.localization import (
    ExecutedRouteFilterSchema,
    PlannedRouteComparisonSchema,
    PointsVisitedResponseSchema,
    RouteComparisonFullResponseSchema,
    RouteComparisonSchema,
    RouteComparisonsResponseSchema
)
from services.common import calculate_distance
from services.environment import load_and_validate_env_vars
from services.localization import get_planned_route, to_point_response
from services.localization_executed import (
    list_executed_routes,
    to_executed_detail,
    to_executed_point_response
)
from services.logger_config import custom_logger as logger

_SETTINGS = load_and_validate_env_vars({'ROUTES_VISIT_MATCH_RADIUS_M': float})
VISIT_MATCH_RADIUS_M = _SETTINGS['ROUTES_VISIT_MATCH_RADIUS_M']


def _stop_was_visited(
    stop: PlannedPointItem,
    points: List[ExecutedPointItem]
) -> bool:
    '''
        True when any reported point names the stop's client or lies within the
        match radius of it.
    '''
    for point in points:
        if stop.get('client_id') and point.get('client_id') == stop['client_id']:
            return True
        if calculate_distance(
            stop['latitude'], stop['longitude'], point['latitude'], point['longitude']
        ) <= VISIT_MATCH_RADIUS_M:
            return True
    return False


def score_execution(
    plan: PlannedRouteItem,
    route: ExecutedRouteItem
) -> RouteComparisonSchema:
    '''
        How one execution measured up against its plan.

        Args:
            plan (PlannedRouteItem): Planned route item.
            route (ExecutedRouteItem): Executed route item.

        Returns:
            RouteComparisonSchema: Counts and the share of planned stops visited.
    '''
    stops = plan.get('points', [])
    points = route.get('points', [])
    matched = sum(1 for stop in stops if _stop_was_visited(stop, points))
    return RouteComparisonSchema(
        planned_route_id = plan['id'],
        planned_route_name = plan['route_name'],
        executed_route_id = route['id'],
        seller = route['seller'],
        match_percentage = round(100.0 * matched / len(stops), 2) if stops else 0.0,
        planned_points_count = len(stops),
        points_visited_count = len(points),
        matched_points_count = matched
    )


def _executions_of(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    planned_route_id: str,
    filters: ExecutedRouteFilterSchema
) -> List[ExecutedRouteItem]:
    '''
        The executed routes that followed `planned_route_id`, within the filters.
    '''
    scoped = filters.model_copy(update = {'planned_route_id': planned_route_id})
    return list_executed_routes(dynamodb_resource, owner_email, scoped)


def route_comparisons(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    planned_route_id: str,
    filters: ExecutedRouteFilterSchema
) -> RouteComparisonsResponseSchema:
    '''
        Every execution of a plan, scored.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            planned_route_id (str): The plan.
            filters (ExecutedRouteFilterSchema): Period and seller.

        Returns:
            RouteComparisonsResponseSchema: One score per execution.
    '''
    plan = get_planned_route(dynamodb_resource, owner_email, planned_route_id)
    routes = _executions_of(dynamodb_resource, owner_email, planned_route_id, filters)
    message = f'Scoring {len(routes)} execution(s) of planned route {planned_route_id}.'
    logger.info(message)
    return RouteComparisonsResponseSchema(
        comparisons = [score_execution(plan, route) for route in routes]
    )


def full_route_comparison(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    planned_route_id: str,
    filters: ExecutedRouteFilterSchema
) -> RouteComparisonFullResponseSchema:
    '''
        The plan with its stops and every execution with its points, for the map.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            planned_route_id (str): The plan.
            filters (ExecutedRouteFilterSchema): Period and seller.

        Returns:
            RouteComparisonFullResponseSchema: Both sides, points included.
    '''
    plan = get_planned_route(dynamodb_resource, owner_email, planned_route_id)
    routes = _executions_of(dynamodb_resource, owner_email, planned_route_id, filters)
    return RouteComparisonFullResponseSchema(
        planned_route = PlannedRouteComparisonSchema(
            id = plan['id'],
            route_name = plan['route_name'],
            seller = plan.get('seller'),
            points = [to_point_response(plan['id'], stop) for stop in plan.get('points', [])]
        ),
        executed_routes = [to_executed_detail(route) for route in routes]
    )


def points_visited(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    seller: str,
    filters: ExecutedRouteFilterSchema
) -> PointsVisitedResponseSchema:
    '''
        Every point a seller reported in a period, across all their routes.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            seller (str): The seller.
            filters (ExecutedRouteFilterSchema): Period (and plan, if wanted).

        Returns:
            PointsVisitedResponseSchema: Count and the points themselves.
    '''
    scoped = filters.model_copy(update = {'seller': seller})
    routes = list_executed_routes(dynamodb_resource, owner_email, scoped)
    details = [
        to_executed_point_response(route['id'], point)
        for route in routes
        for point in route.get('points', [])
    ]
    message = f'{seller} reported {len(details)} point(s) over {len(routes)} route(s).'
    logger.info(message)
    return PointsVisitedResponseSchema(
        seller = seller,
        total_points_visited = len(details),
        points_details = details
    )
