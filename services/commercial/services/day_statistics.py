'''
    What the field did on one day: who is out, how much of what was planned
    was visited, and how far the sellers drove. Read by the main dashboard.
'''
from boto3.resources.base import ServiceResource

from models.localization import ExecutedRouteItem
from schemas.daily_stock import DayStatisticsSchema, SellerDaySchema
from schemas.localization import ExecutedRouteFilterSchema
from services.daily_stock import get_daily_stock
from services.exceptions import RegisterNotFoundError
from services.localization import get_planned_route
from services.localization_executed import list_executed_routes, route_km
from services.localization_stats import score_execution
from services.logger_config import custom_logger as logger

def _sold(
    route: ExecutedRouteItem,
    prices: dict[str, float]
) -> tuple[float, float]:
    '''
        What a route sold on its visits: units, and bolivianos at the price of
        the day's stock. A SKU without a price counts its units, not an amount.

        Args:
            route (ExecutedRouteItem): The executed route with its points.
            prices (dict[str, float]): Unit price per SKU of the day.

        Returns:
            tuple[float, float]: Units and bolivianos.
    '''
    lines = [item for point in route.get('points', []) for item in point.get('items') or []]
    units = sum(float(item.get('quantity') or 0) for item in lines)
    amount = sum(float(item.get('quantity') or 0) * prices.get(str(item.get('sku')), 0.0)
                 for item in lines)
    return units, amount


def _by_seller(
    routes: list[ExecutedRouteItem],
    prices: dict[str, float]
) -> list[SellerDaySchema]:
    '''
        Each seller's day, the largest sale first.

        Args:
            routes (list[ExecutedRouteItem]): The day's routes.
            prices (dict[str, float]): Unit price per SKU of the day.

        Returns:
            list[SellerDaySchema]: One row per seller.
    '''
    sellers: dict[str, dict] = {}
    for route in routes:
        row = sellers.setdefault(str(route['seller']), {
            'on_route': False, 'visits': 0, 'units': 0.0, 'amount': 0.0, 'km': 0.0})
        units, amount = _sold(route, prices)
        row['on_route'] = row['on_route'] or not route.get('end_time')
        row['visits'] += sum(1 for point in route.get('points', []) if point.get('client_id'))
        row['units'] += units
        row['amount'] += amount
        row['km'] += route.get('distance_km') or route_km(route)
    return sorted((SellerDaySchema(
        seller = seller, on_route = row['on_route'], visits = row['visits'],
        units_sold = round(row['units'], 2), sales_amount = round(row['amount'], 2),
        distance_km = round(row['km'], 2)) for seller, row in sellers.items()),
        key = lambda row: row.sales_amount, reverse = True)


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
    stock = get_daily_stock(dynamodb_resource, owner_email, day)
    prices = {str(row['sku']): float(row['unit_price']) for row in stock
              if row.get('unit_price') is not None}
    sellers = _by_seller(routes, prices)
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
        distance_km = round(sum(row.distance_km for row in sellers), 2),
        sales_amount = round(sum(row.sales_amount for row in sellers), 2),
        stock_available_value = round(sum(
            float(row['available_quantity']) * prices.get(str(row['sku']), 0.0)
            for row in stock), 2) if stock else None,
        sellers = sellers
    )
