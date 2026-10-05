'''
    Ingest support: persistence of dataset metadata and file storage.

    Keeps the ingest domain logic in ingest.py free of infrastructure detail:
    the DynamoDB items of a dataset, and the thin turn of a stored file into
    the frame this service works with.

    Talking to FILES is NOT here: it lives in `services/utils.py`, which is
    the model any new DynamoDB microservice copies. What stays is the one
    direct read the rule allows — the static template.
'''
import hashlib
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
import pandas as pd
from boto3.dynamodb.conditions import Attr
from boto3.resources.base import ServiceResource

from models.ingest import IngestDataset
from schemas.files import FilesError
from schemas.ingest import IngestError
from services.crud import create_item, get_item_by_key
from services.environment import load_and_validate_env_vars
from services.exceptions import ResourceNotFoundError, ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.utils import (
    audit_event,
    get_current_time_gmt,
    read_file_rows,
    store_file
)


ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_INGEST_DATASETS': str,
    'BUCKET_NAME': str,
    'HISTORY_DEFAULT_LIMIT': int,
})
DATASETS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_INGEST_DATASETS']
BUCKET_NAME = ENV_VARS['BUCKET_NAME']

# The ONLY direct S3 access left, and the exception the rule names in
# `CLAUDE.md` §9: the templates are static objects, identical for every client,
# and FILES cannot hand back a file AS a file —its reader parses and returns
# rows—. Everything the client sends or the service stores goes through FILES.
_s3_client = boto3.client('s3')


def download_template_bytes(file_key: str) -> bytes:
    '''
        Reads one static template straight from the bucket.

        Args:
            file_key (str): S3 object key of the template.

        Returns:
            bytes: The template, byte for byte.

        Raises:
            ServiceUnavailableError: If the object cannot be read.
    '''
    try:
        return _s3_client.get_object(Bucket = BUCKET_NAME, Key = file_key)['Body'].read()
    except Exception as error:
        error_msg = f'Failed to read the template s3://{BUCKET_NAME}/{file_key}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = FilesError.UNREACHABLE.value
        ) from error


# ---------------------------------------------------------------------------
# Dataset metadata (DynamoDB)
# ---------------------------------------------------------------------------

def _build_dataset_item(payload: Dict[str, Any]) -> IngestDataset:
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


def to_dynamo(value: Any) -> Any:
    '''
        Turns floats into Decimal, which is the only numeric type DynamoDB
        accepts. Walks dicts and lists so a summary travels whole. Named as in
        OPTIMIZATION, which solves the same problem the same way.

        Args:
            value (Any): Node of the payload being written.

        Returns:
            Any: The same node, with its floats converted.
    '''
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: to_dynamo(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_dynamo(item) for item in value]
    return value


def from_dynamo(value: Any) -> Any:
    '''
        The inverse of `to_dynamo`: the Decimals DynamoDB hands back become
        native numbers, so DTOs and arithmetic never meet a Decimal.

        Args:
            value (Any): Node of the payload just read.

        Returns:
            Any: The same node, with int/float instead of Decimal.
    '''
    if isinstance(value, Decimal):
        integral = int(value)
        return integral if value == integral else float(value)
    if isinstance(value, dict):
        return {key: from_dynamo(item) for key, item in value.items()}
    if isinstance(value, list):
        return [from_dynamo(item) for item in value]
    return value


def attach_to_dataset(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Attaches a secondary load —payments, stock— to a sales dataset.

        An update and not a new row because neither is another dataset: the
        payments are the same sale collected, and the stock is the warehouse
        behind the same catalogue. Each keeps ONE object key, so re-uploading
        replaces the previous load instead of accumulating copies nobody can
        tell apart — which for a daily stock snapshot is the whole point.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Dataset the load belongs to.
            payload (Dict[str, Any]): Attributes to write: the object key and
                the summary of the load.

        Returns:
            Dict[str, Any]: The dataset as it now stands.
    '''
    values = {f':{name}': value for name, value in payload.items()}
    assignments = ', '.join(f'#{name} = :{name}' for name in payload)
    updated = dynamodb_resource.Table(DATASETS_TABLE).update_item(
        Key = {'id': dataset_id},
        UpdateExpression = f'SET {assignments}',
        ExpressionAttributeNames = {f'#{name}': name for name in payload},
        ExpressionAttributeValues = to_dynamo(values),
        ReturnValues = 'ALL_NEW'
    )
    message = f'Attached a secondary load to dataset {dataset_id}.'
    logger.info(message)
    return updated.get('Attributes', {})


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


# How many history rows a caller gets when they do not ask for a number.
HISTORY_DEFAULT_LIMIT = ENV_VARS['HISTORY_DEFAULT_LIMIT']


def content_fingerprint(file_bytes: bytes) -> str:
    '''
        Returns a stable fingerprint of an uploaded file.

        Args:
            file_bytes (bytes): Raw content as uploaded.

        Returns:
            str: Hexadecimal SHA-256 of the bytes.
    '''
    return hashlib.sha256(file_bytes).hexdigest()


def find_dataset_by_fingerprint(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    fingerprint: str
) -> Optional[Dict[str, Any]]:
    '''
        Returns the caller's dataset with this exact content, if it exists.

        Uploading the same file twice used to mint a second identifier, a second
        copy in S3 and a second row here — forty-six of them accumulated from one
        file during testing. Nothing told the user they already had it, and the
        history filled with rows indistinguishable from each other.

        Identity is the content, not the filename: the same figures renamed are
        the same dataset, and a corrected file is a different one even under the
        same name.

        Args:
            dynamodb_resource (ServiceResource): DynamoDB resource.
            owner_email (str): Authenticated caller.
            fingerprint (str): Content fingerprint to look for.

        Returns:
            Dict[str, Any] | None: The stored record, or None if it is new.
    '''
    table = dynamodb_resource.Table(DATASETS_TABLE)
    scan_kwargs: Dict[str, Any] = {
        'FilterExpression': (Attr('owner_email').eq(owner_email)
                             & Attr('file_fingerprint').eq(fingerprint))
    }
    while True:
        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])
        if items:
            return items[0]
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            return None
        scan_kwargs['ExclusiveStartKey'] = last_key


def list_datasets_for_owner(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    limit: int = HISTORY_DEFAULT_LIMIT
) -> List[Dict[str, Any]]:
    '''
        Returns the caller's own uploads, most recent first.

        The owner is part of the scan filter, so the query cannot return
        somebody else's rows even by mistake. With `id` as the partition key
        there is no Query that filters by owner, so this scans; at POC volumes
        that is fine, and the right move when the table grows is a Global
        Secondary Index on `owner_email`.

        Args:
            dynamodb_resource (ServiceResource): DynamoDB resource.
            owner_email (str): Authenticated caller.
            limit (int): Most rows to return.

        Returns:
            List[Dict[str, Any]]: Stored dataset records, newest first.
    '''
    table = dynamodb_resource.Table(DATASETS_TABLE)
    items: List[Dict[str, Any]] = []
    scan_kwargs: Dict[str, Any] = {
        'FilterExpression': Attr('owner_email').eq(owner_email)
    }
    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get('Items', []))
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        scan_kwargs['ExclusiveStartKey'] = last_key

    items.sort(key = lambda item: str(item.get('created_at', '')), reverse = True)
    return items[:limit]


def get_owned_dataset(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    owner_email: str
) -> Dict[str, Any]:
    '''
        Retrieves a dataset only if it belongs to whoever is asking.

        Every read by id goes through here. Without it, an authenticated user of
        one client who knows —or guesses— an identifier reads the sales data of
        another: the owner was being stored on every record and never checked.

        A dataset of somebody else answers exactly like one that does not exist.
        Telling them apart would let a caller confirm which identifiers are real,
        which is a map of the customer base.

        Args:
            dynamodb_resource (ServiceResource): DynamoDB resource.
            dataset_id (str): Identifier of the dataset.
            owner_email (str): Authenticated caller.

        Returns:
            Dict[str, Any]: The stored dataset record.

        Raises:
            ResourceNotFoundError: If it does not exist or belongs to someone else.
    '''
    item = get_dataset_by_id(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )
    if not item or item.get('owner_email') != owner_email:
        error_msg = f'Dataset {dataset_id} is not available for {owner_email}.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = IngestError.DATASET_NOT_FOUND.value)
    return item


# ---------------------------------------------------------------------------
# Storage, through FILES
# ---------------------------------------------------------------------------

def read_stored_frame(
    file_key: str,
    auth_token: str,
    delimiter: str = ','
) -> pd.DataFrame:
    '''
        An object of the bucket as a frame, read through FILES.

        The conversation with FILES lives in the boilerplate
        (`services/utils.py`), which is the model any new DynamoDB service
        copies; here it is only turned into the frame this service works with.

        Args:
            file_key (str): S3 object key.
            auth_token (str): The caller's Authorization header.
            delimiter (str): Field separator, for a CSV.

        Returns:
            pd.DataFrame: The rows the file holds.
    '''
    return pd.DataFrame(read_file_rows(file_key, auth_token, delimiter))


def upload_bytes(
    file_key: str,
    data: bytes,
    content_type: str,
    auth_token: str
) -> str:
    '''
        Stores bytes in the bucket through FILES and returns the object key.

        Args:
            file_key (str): Destination object key.
            data (bytes): Content to store.
            content_type (str): MIME type stored on the object.
            auth_token (str): The caller's Authorization header.

        Returns:
            str: The stored object key.
    '''
    return store_file(file_key, data, auth_token, content_type)
