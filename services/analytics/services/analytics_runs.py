'''
    Persistence layer for analytics runs.
'''
import uuid
from decimal import Decimal
from typing import Any, Dict, List
from boto3.dynamodb.conditions import Key
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
    '''
    now = get_current_time_gmt()
    return {
        'dataset_id': payload['dataset_id'],
        'run_id': payload.get('run_id') or str(uuid.uuid4()),
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

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            payload (Dict[str, Any]): Run output (summary + opportunities + parameters).

        Returns:
            Dict[str, Any]: The persisted item (with Decimal values converted back
            to native types so the controller can map it into the response schema).
    '''
    item = _build_run_item(payload)
    create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = ANALYTICS_RUNS_TABLE,
        item_data = item,
        unique_key_attribute = 'run_id'
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
    '''
    table = dynamodb_resource.Table(ANALYTICS_RUNS_TABLE)
    response = table.query(
        KeyConditionExpression = Key('dataset_id').eq(dataset_id)
    )
    items: List[Dict[str, Any]] = response.get('Items', [])
    if not items:
        error_msg = f'No analytics run found for dataset {dataset_id}.'
        logger.warning(error_msg)
        raise RegisterNotFoundError(detail = error_msg)
    items.sort(key = lambda record: record.get('created_at', ''), reverse = True)
    return _decimal_to_native(items[0])
