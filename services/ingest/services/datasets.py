'''
    Business logic for the Datasets module of the Ingest service.
'''
import uuid
from typing import Any, Dict
from boto3.resources.base import ServiceResource

from services.crud import create_item, get_item_by_key
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger
from services.utils import audit_event, get_current_time_gmt

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_INGEST_DATASETS': str
})

DATASETS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_INGEST_DATASETS']


def _build_dataset_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Builds the DynamoDB item shape for a new ingested dataset.

        Note on the schema: the live AWS table `ingest_datasets` uses a
        simple partition key named `id` (S). We keep `dataset_id` as a
        mirror attribute so callers and downstream services that already
        rely on the `dataset_id` label do not need to change.
    '''
    now = get_current_time_gmt()
    dataset_id = payload.get('dataset_id') or str(uuid.uuid4())
    return {
        'id': dataset_id,
        'dataset_id': dataset_id,
        'owner_email': payload['owner_email'],
        'status': payload['status'],
        'file_s3_key': payload.get('file_s3_key'),
        'rejected_s3_key': payload.get('rejected_s3_key'),
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


@audit_event('INGEST', 'IngestDataset', 'CREATE')
def persist_dataset(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Persists a new ingested dataset record in DynamoDB.
    '''
    item = _build_dataset_item(payload)
    persisted = create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = DATASETS_TABLE,
        item_data = item,
        unique_key_attribute = 'id'
    )
    message = f'Persisted ingest dataset {item["dataset_id"]} (status={item["status"]}).'
    logger.info(message)
    return persisted


def update_dataset_result(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    payload: Dict[str, Any]
) -> None:
    '''
        Updates a dataset record with the outcome of async processing: final
        status, normalized file key, summary metrics and per-row errors. The
        immutable fields (id, owner, created_at) are left untouched.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Primary key of the record to update.
            payload (Dict[str, Any]): status, file_s3_key, the summary metrics
                and errors to store.
    '''
    table = dynamodb_resource.Table(DATASETS_TABLE)
    table.update_item(
        Key = {'id': dataset_id},
        UpdateExpression = (
            'SET #st = :st, file_s3_key = :fk, rejected_s3_key = :rk, '
            'total_rows = :tr, valid_rows = :vr, '
            'error_rows = :er, unique_points_of_sale = :pv, unique_products = :up, '
            'date_range_start = :ds, date_range_end = :de, errors = :errs'
        ),
        ExpressionAttributeNames = {'#st': 'status'},
        ExpressionAttributeValues = {
            ':st': payload['status'],
            ':fk': payload.get('file_s3_key'),
            ':rk': payload.get('rejected_s3_key'),
            ':tr': int(payload.get('total_rows', 0)),
            ':vr': int(payload.get('valid_rows', 0)),
            ':er': int(payload.get('error_rows', 0)),
            ':pv': int(payload.get('unique_points_of_sale', 0)),
            ':up': int(payload.get('unique_products', 0)),
            ':ds': payload.get('date_range_start'),
            ':de': payload.get('date_range_end'),
            ':errs': payload.get('errors', [])
        }
    )
    message = f'Updated ingest dataset {dataset_id} (status={payload["status"]}).'
    logger.info(message)


def get_dataset_by_id(
    dynamodb_resource: ServiceResource,
    dataset_id: str
) -> Dict[str, Any]:
    '''
        Retrieves an ingested dataset record by its primary key.

        The AWS table uses `id` as the PK; we accept the logical
        `dataset_id` argument and use it as the key value.
    '''
    return get_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = DATASETS_TABLE,
        key = {'id': dataset_id}
    )
