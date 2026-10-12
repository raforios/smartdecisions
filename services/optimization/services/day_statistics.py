'''
    What the field did on one day: who is out, how much of what was planned
    was visited, and how far the sellers drove. Read by the main dashboard.
'''
from boto3.resources.base import ServiceResource

from models.localization import ExecutedRouteItem
from schemas.daily_stock import DayStatisticsSchema
from schemas.localization import ExecutedRouteFilterSchema
from services.common import calculate_distance
from services.exceptions import RegisterNotFoundError
from services.localization import get_planned_route
from services.localization_executed import list_executed_routes
from services.localization_stats import score_execution
from services.logger_config import custom_logger as logger

_METRES_PER_KM = 1000.0


def route_km(route: ExecutedRouteItem) -> float:
    '''
        The distance a route covered, point to point in the order reported.

        Args:
            route (ExecutedRouteItem): The executed route with its points.

        Returns:
            float: Kilometres, rounded to two decimals.
    '''
    points = sorted(route.get('points', []), key = lambda point: point.get('timestamp') or '')
    metres = sum(
        calculate_distance(first['latitude'], first['longitude'],
                           second['latitude'], second['longitude'])
        for first, second in zip(points, points[1:])
    )
    return round(metres / _METRES_PER_KM, 2)


def day_statistics(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    day: str
) -> DayStatisticsSchema:
    '''
        The field figures of one day.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            day (str): YYYY-MM-DD.

        Returns:
            DayStatisticsSchema: Sellers out, plan compliance and kilometres.
    '''
    routes = list_executed_routes(
        dynamodb_resource, owner_email, ExecutedRouteFilterSchema(date_from = day, date_to = day))
    plans: dict = {}
    planned = visited = 0
    for route in routes:
        plan_id = route.get('planned_route_id')
        if not plan_id:
            continue
        if plan_id not in plans:
            try:
                plans[plan_id] = get_planned_route(dynamodb_resource, owner_email, plan_id)
            except RegisterNotFoundError:
                # A plan deleted after it was run no longer measures anything.
                plans[plan_id] = None
        if plans[plan_id] is None:
            continue
        score = score_execution(plans[plan_id], route)
        planned += score.planned_points_count
        visited += score.matched_points_count
    closed = sum(1 for route in routes if route.get('end_time'))
    message = f'Day {day} of {owner_email}: {len(routes)} route(s), {closed} closed.'
    logger.info(message)
    return DayStatisticsSchema(
        date = day,
        sellers_on_route = len({route['seller'] for route in routes if not route.get('end_time')}),
        routes_started = len(routes),
        routes_closed = closed,
        planned_stops = planned,
        visited_stops = visited,
        visit_compliance = round(100.0 * visited / planned, 2) if planned else None,
        distance_km = round(sum(route_km(route) for route in routes), 2)
    )
