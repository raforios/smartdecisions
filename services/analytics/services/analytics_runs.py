'''
    Persistence layer for analytics runs.
'''
import uuid
from decimal import Decimal
from typing import Any, Dict, List
from boto3.dynamodb.conditions import Attr
from boto3.resources.base import ServiceResource

from services.crud import create_item
from services.environment import load_and_validate_env_vars
from services.events_emitter import audit_event
from services.exceptions import RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt, handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_ANALYTICS_RUNS': str
})

ANALYTICS_RUNS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_ANALYTICS_RUNS']


def _floats_to_decimal(value: Any) -> Any:
    '''
        Recursively converts floats to Decimal so DynamoDB accepts them.
    '''
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _floats_to_decimal(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_floats_to_decimal(inner) for inner in value]
    return value


def _decimal_to_native(value: Any) -> Any:
    '''
        Inverse of `_floats_to_decimal` — used when serializing items back to
        the API response (FastAPI / Pydantic don't accept Decimal natively).
    '''
    if isinstance(value, Decimal):
        as_float = float(value)
        return int(as_float) if as_float.is_integer() else as_float
    if isinstance(value, dict):
        return {key: _decimal_to_native(inner) for key, inner in value.items()}
    if isinstance(value, list):
        return [_decimal_to_native(inner) for inner in value]
    return value


def _build_run_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Materializes the DynamoDB item shape for a finished analytics run.

        The AWS table `analytics_runs` uses a simple partition key `id` (S).
        Each item carries `id = run_id` (UUID) so collisions are impossible,
        and `dataset_id` is a regular attribute used to filter runs by
        dataset.
    '''
    now = get_current_time_gmt()
    run_id = payload.get('run_id') or str(uuid.uuid4())
    return {
        'id': run_id,
        'run_id': run_id,
        'dataset_id': payload['dataset_id'],
        'status': payload['status'],
        'owner_email': payload['owner_email'],
        'summary': _floats_to_decimal(payload.get('summary', {})),
        'opportunities': _floats_to_decimal(payload.get('opportunities', [])),
        'parameters': _floats_to_decimal(payload.get('parameters', {})),
        'created_at': now.isoformat()
    }


@handle_service_errors
@audit_event('ANALYTICS', 'AnalyticsRun', 'CREATE')
def persist_run(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Persists a finished analytics run.
    '''
    item = _build_run_item(payload)
    create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = ANALYTICS_RUNS_TABLE,
        item_data = item,
        unique_key_attribute = 'id'
    )
    message = (
        f'Persisted analytics run {item["run_id"]} for dataset {item["dataset_id"]} '
        f'(status={item["status"]}).'
    )
    logger.info(message)
    return _decimal_to_native(item)


@handle_service_errors
def get_latest_run_for_dataset(
    dynamodb_resource: ServiceResource,
    dataset_id: str
) -> Dict[str, Any]:
    '''
        Returns the most recent run for the given dataset.

        With PK `id`, there is no DynamoDB Query that filters by dataset_id
        directly, so we Scan the table with a FilterExpression. This is OK
        for POC volumes; if the table grows, the right move is to add a
        Global Secondary Index on `dataset_id`.
    '''
    table = dynamodb_resource.Table(ANALYTICS_RUNS_TABLE)
    items: List[Dict[str, Any]] = []
    last_evaluated_key = None
    while True:
        scan_kwargs = {'FilterExpression': Attr('dataset_id').eq(dataset_id)}
        if last_evaluated_key:
            scan_kwargs['ExclusiveStartKey'] = last_evaluated_key
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        last_evaluated_key = response.get('LastEvaluatedKey')
        if not last_evaluated_key:
            break

    if not items:
        error_msg = f'No analytics run found for dataset {dataset_id}.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = error_msg)
    items.sort(key = lambda record: record.get('created_at', ''), reverse = True)
    return _decimal_to_native(items[0])
