'''
    Route data access layer for the Optimization service.

    Reads the geolocated client points that feed the optimization algorithm.
    Replaces the legacy monolith's `SELECT * FROM routes WHERE route_id = X
    AND day = Y` (api/controllers/optimization.py:database_to_df) with a
    single DynamoDB Query on `t_optimization_routes`.
'''
from typing import Any, Dict, List
from boto3.dynamodb.conditions import Key
from boto3.resources.base import ServiceResource

from services.environment import load_and_validate_env_vars
from services.exceptions import RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.utils import handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_OPTIMIZATION_ROUTES': str
})

ROUTES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_OPTIMIZATION_ROUTES']


def _build_route_day_key(route_id: int, day: int) -> str:
    '''
        Builds the composite partition key used by t_optimization_routes.

        Args:
            route_id (int): Identifier of the planned route.
            day (int): Day index within the plan.

        Returns:
            str: Composite key in the form "{route_id}#{day}".
    '''
    return f'{int(route_id)}#{int(day)}'


@handle_service_errors
def get_route_points(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int
) -> List[Dict[str, Any]]:
    '''
        Retrieves all client geolocation points for a (route_id, day) pair.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            route_id (int): Identifier of the planned route.
            day (int): Day index within the plan.

        Returns:
            List[Dict[str, Any]]: Items shaped as RoutePoint TypedDict.

        Raises:
            RegisterNotFoundError: If no points exist for that (route_id, day).
    '''
    table = dynamodb_resource.Table(ROUTES_TABLE)
    partition_key = _build_route_day_key(route_id, day)

    response = table.query(
        KeyConditionExpression = Key('route_day_key').eq(partition_key)
    )
    items: List[Dict[str, Any]] = response.get('Items', [])

    if not items:
        error_msg = (
            f'No route points found for route_id={route_id} day={day}.'
        )
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = error_msg)

    message = (
        f'Retrieved {len(items)} client points for route_id={route_id} '
        f'day={day} from {ROUTES_TABLE}.'
    )
    logger.info(message)
    return items
