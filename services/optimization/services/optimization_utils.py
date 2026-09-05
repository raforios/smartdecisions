'''
    Optimization support: reading the planned route points from DynamoDB and
    loading the normalized sales dataset produced by ingest.

    Keeps optimization.py free of plumbing: nothing here plans a route, it only
    makes the data available.
'''
from decimal import Decimal
from io import BytesIO
from typing import Any, Dict, List

import boto3
import pandas as pd
from boto3.dynamodb.conditions import Key
from boto3.resources.base import ServiceResource

from schemas.optimization import OptimizationError
from services.environment import load_and_validate_env_vars
from services.exceptions import (
    InvalidInputError,
    RegisterNotFoundError,
    ServiceUnavailableError
)
from services.logger_config import custom_logger as logger


ENV_VARS = load_and_validate_env_vars({
    'BUCKET_NAME': str,
    'DYNAMODB_TABLE_NAME_INGEST_DATASETS': str,
    'DYNAMODB_TABLE_NAME_OPTIMIZATION_ROUTES': str,
})
ROUTES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_OPTIMIZATION_ROUTES']
INGEST_DATASETS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_INGEST_DATASETS']
FILES_BUCKET_NAME = ENV_VARS['BUCKET_NAME']


# ---------------------------------------------------------------------------
# Planned route points (DynamoDB)
# ---------------------------------------------------------------------------




def _build_route_day_key(owner_email: str, route_id: int, day: int) -> str:
    '''
        Builds the partition key of the routes table.

        The owner is part of the key, not a filter applied afterwards, because
        this partition is deleted before every upload. Without it, two clients
        planning "route 1, day 1" — and route identifiers are small integers
        everybody uses — share a partition, so the second upload **erases the
        first client's points**. That is worse than reading somebody else's
        data, and no filter on the read path would have prevented it.

        Args:
            owner_email (str): Owner of the plan.
            route_id (int): Identifier of the planned route.
            day (int): Day index within the plan.

        Returns:
            str: Composite key in the form "{owner}#{route_id}#{day}".
    '''
    return f'{owner_email}#{int(route_id)}#{int(day)}'


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
        error_msg = f'Invalid route point {raw}: {e}'
        logger.warning(error_msg)
        raise InvalidInputError(detail = OptimizationError.INVALID_POINT.value) from e

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
    day: int,
    owner_email: str
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
    partition_key = _build_route_day_key(owner_email, route_id, day)

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
    day: int,
    owner_email: str
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
    partition_key = _build_route_day_key(owner_email, route_id, day)
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
    points: List[Dict[str, Any]],
    owner_email: str
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
        raise InvalidInputError(detail = OptimizationError.EMPTY_POINT_LIST.value)

    partition_key = _build_route_day_key(owner_email, route_id, day)
    deleted = delete_points_for_route_day(
        dynamodb_resource = dynamodb_resource,
        route_id = route_id,
        day = day,
        owner_email = owner_email
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


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------



# boto3 resolves region + credentials from the default chain (Lambda IAM
# role in AWS, ~/.aws/credentials in local dev) — same way AUTH and EVENTS
# do it. No region_name argument needed.
_s3_client = boto3.client('s3')


def get_dataset_metadata(
    dynamodb_resource: ServiceResource,
    dataset_id: str
) -> dict:
    '''
        Retrieves a dataset record from the ingest service's table.

        Args:
            dynamodb_resource (ServiceResource): The shared DynamoDB resource.
            dataset_id (str): UUID issued by the ingest service.

        Returns:
            dict: The persisted ingest item.

        Raises:
            RegisterNotFoundError: If the dataset_id is unknown.
            InvalidInputError: If the dataset exists but its status is not 'validated'.
    '''
    # The AWS table `ingest_datasets` uses `id` as its partition key (set
    # to the same UUID value as the logical `dataset_id` attribute by the
    # ingest service — see ingest/services/datasets.py:_build_dataset_item).
    table = dynamodb_resource.Table(INGEST_DATASETS_TABLE)
    response = table.get_item(Key = {'id': dataset_id})
    item = response.get('Item')
    if not item:
        error_msg = f'Dataset {dataset_id} not found in {INGEST_DATASETS_TABLE}.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = error_msg)
    if item.get('status') != 'validated':
        error_msg = (
            f'Dataset {dataset_id} cannot be analyzed because its status is '
            f'"{item.get("status")}". Re-upload a valid file via /v1/ingest/excel.'
        )
        logger.warning(error_msg)
        raise InvalidInputError(detail = error_msg)
    return item


def _read_dataframe(file_bytes: bytes, s3_key: str) -> pd.DataFrame:
    '''
        Parses the downloaded bytes into a DataFrame based on the key suffix.
    '''
    lower = s3_key.lower()
    buffer = BytesIO(file_bytes)
    if lower.endswith('.xlsx'):
        return pd.read_excel(buffer, engine = 'openpyxl')
    if lower.endswith('.csv'):
        return pd.read_csv(buffer)
    error_msg = f'Unsupported file extension on S3 key "{s3_key}".'
    logger.error(error_msg)
    raise InvalidInputError(detail = error_msg)


def load_dataframe_from_s3(s3_key: str) -> pd.DataFrame:
    '''
        Downloads the validated file from S3 and returns it as a DataFrame.

        Args:
            s3_key (str): S3 object key under FILES_BUCKET_NAME.

        Returns:
            pd.DataFrame: Sales rows ready for the route planner.

        Raises:
            ServiceUnavailableError: If S3 is unreachable or denies access.
    '''
    try:
        response = _s3_client.get_object(Bucket = FILES_BUCKET_NAME, Key = s3_key)
        file_bytes = response['Body'].read()
    except Exception as error:
        error_msg = (
            f'Failed to download s3://{FILES_BUCKET_NAME}/{s3_key}: {error}'
        )
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = 'No se pudo leer el archivo del bucket de FILES.'
        ) from error

    message = (
        f'Downloaded {len(file_bytes)} bytes from '
        f's3://{FILES_BUCKET_NAME}/{s3_key} for analytics.'
    )
    logger.info(message)
    return _read_dataframe(file_bytes, s3_key)
