'''
    Business logic for the Datasets module of the Ingest service.
'''
import uuid
from typing import Any, Dict
from boto3.resources.base import ServiceResource

from services.crud import create_item, get_item_by_key
from services.environment import load_and_validate_env_vars
from services.events_emitter import audit_event
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt, handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_INGEST_DATASETS': str
})

DATASETS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_INGEST_DATASETS']


def _build_dataset_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Builds the DynamoDB item shape for a new ingested dataset.

        Args:
            payload (Dict[str, Any]): Pre-computed values from the ingest pipeline.

        Returns:
            Dict[str, Any]: Item ready to persist.
    '''
    now = get_current_time_gmt()
    return {
        'dataset_id': payload.get('dataset_id') or str(uuid.uuid4()),
        'owner_email': payload['owner_email'],
        'status': payload['status'],
        'file_s3_key': payload.get('file_s3_key'),
        'template_version': payload.get('template_version', 'v1'),
        'total_rows': int(payload.get('total_rows', 0)),
        'valid_rows': int(payload.get('valid_rows', 0)),
        'error_rows': int(payload.get('error_rows', 0)),
        'unique_points_of_sale': int(payload.get('unique_points_of_sale', 0)),
        'unique_products': int(payload.get('unique_products', 0)),
        'date_range_start': payload.get('date_range_start'),
        'date_range_end': payload.get('date_range_end'),
        'errors': payload.get('errors', []),
        'created_at': now.isoformat()
    }


@handle_service_errors
@audit_event('INGEST', 'IngestDataset', 'CREATE')
def persist_dataset(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Persists a new ingested dataset record in DynamoDB.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            payload (Dict[str, Any]): Ingest metadata (already computed by the
                                      pipeline + s3 key + owner).

        Returns:
            Dict[str, Any]: The persisted item.
    '''
    item = _build_dataset_item(payload)
    persisted = create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = DATASETS_TABLE,
        item_data = item,
        unique_key_attribute = 'dataset_id'
    )
    message = f'Persisted ingest dataset {item["dataset_id"]} (status={item["status"]}).'
    logger.info(message)
    return persisted


@handle_service_errors
def get_dataset_by_id(
    dynamodb_resource: ServiceResource,
    dataset_id: str
) -> Dict[str, Any]:
    '''
        Retrieves an ingested dataset record by its primary key.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): The UUID of the dataset.

        Returns:
            Dict[str, Any]: The dataset item.

        Raises:
            RegisterNotFoundError: If no record exists for that dataset_id.
    '''
    return get_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = DATASETS_TABLE,
        key = {'dataset_id': dataset_id}
    )
