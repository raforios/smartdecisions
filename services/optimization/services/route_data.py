'''
    Route data access layer for the Optimization service.

    Reads the geolocated client points that feed the optimization algorithm.
    Replaces the legacy monolith's `SELECT * FROM routes WHERE route_id = X
    AND day = Y` (api/controllers/optimization.py:database_to_df) with a
    single DynamoDB Query on `t_optimization_routes`.
'''
from decimal import Decimal
from typing import Any, Dict, List
from boto3.dynamodb.conditions import Key
from boto3.resources.base import ServiceResource

from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.logger_config import custom_logger as logger

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


def _point_to_item(
    raw: Dict[str, Any],
    route_id: int,
    day: int,
    partition_key: str
) -> Dict[str, Any]:
    '''
        Converts a raw CSV point dict into the DynamoDB item shape.

        Raises:
            InvalidInputError: If a mandatory coordinate/key is missing or
                not numeric.
    '''
    try:
        client_id = int(raw['client_id'])
        latitude = float(raw['latitude'])
        longitude = float(raw['longitude'])
    except (KeyError, TypeError, ValueError) as e:
        raise InvalidInputError(detail = f'Punto inválido: {raw}. Error: {e}') from e

    item: Dict[str, Any] = {
        'route_day_key': partition_key,
        'client_id': client_id,
        'route_id': int(route_id),
        'day': int(day),
        # DynamoDB rejects native floats; store as Decimal.
        'latitude': Decimal(str(latitude)),
        'longitude': Decimal(str(longitude)),
    }
    raw_client = raw.get('client')
    client_name = raw_client.strip() if isinstance(raw_client, str) else ''
    if client_name:
        item['client'] = client_name
    return item


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


def delete_points_for_route_day(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int
) -> int:
    '''
        Removes every existing point under the (route_id, day) partition.

        Used as the first step of `bulk_upload_points` to guarantee that
        a re-upload of the same (route_id, day) replaces the data instead
        of accumulating duplicates.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            route_id (int): Identifier of the planned route.
            day (int): Day index within the plan.

        Returns:
            int: Number of items deleted.
    '''
    table = dynamodb_resource.Table(ROUTES_TABLE)
    partition_key = _build_route_day_key(route_id, day)
    response = table.query(
        KeyConditionExpression = Key('route_day_key').eq(partition_key),
        ProjectionExpression = 'route_day_key, client_id'
    )
    existing = response.get('Items', [])
    if not existing:
        return 0
    with table.batch_writer() as batch:
        for item in existing:
            batch.delete_item(
                Key = {
                    'route_day_key': item['route_day_key'],
                    'client_id': item['client_id']
                }
            )
    message = (
        f'Deleted {len(existing)} stale points under partition '
        f'{partition_key} before re-upload.'
    )
    logger.info(message)
    return len(existing)


def bulk_upload_points(
    dynamodb_resource: ServiceResource,
    route_id: int,
    day: int,
    points: List[Dict[str, Any]]
) -> int:
    '''
        Persists a list of geolocated client points under the given
        (route_id, day) partition. Stale items under the same partition
        are deleted first so re-uploads behave like a full replace.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            route_id (int): Identifier of the planned route.
            day (int): Day index within the plan.
            points (List[Dict[str, Any]]): One dict per client. Required keys:
                client_id (int), latitude (float), longitude (float). Optional:
                client (str).

        Returns:
            int: Number of items written.

        Raises:
            InvalidInputError: If the payload is empty or a point misses keys.
    '''
    if not points:
        raise InvalidInputError(detail = 'La lista de puntos está vacía.')

    partition_key = _build_route_day_key(route_id, day)
    deleted = delete_points_for_route_day(
        dynamodb_resource = dynamodb_resource,
        route_id = route_id,
        day = day
    )

    table = dynamodb_resource.Table(ROUTES_TABLE)
    written = 0
    seen_client_ids = set()
    with table.batch_writer() as batch:
        for raw in points:
            item = _point_to_item(raw, route_id, day, partition_key)
            if item['client_id'] in seen_client_ids:
                # Composite SK requires client_id unique per partition.
                continue
            seen_client_ids.add(item['client_id'])
            batch.put_item(Item = item)
            written += 1

    message = (
        f'Bulk-uploaded {written} point(s) to partition {partition_key} '
        f'(replaced {deleted}).'
    )
    logger.info(message)
    return written
