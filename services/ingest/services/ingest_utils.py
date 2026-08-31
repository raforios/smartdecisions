'''
    Ingest support: persistence of dataset metadata and file storage.

    Keeps the ingest domain logic in ingest.py free of infrastructure detail —
    DynamoDB items, direct S3 access for files too large for API Gateway, and
    the FILES service for regular uploads.
'''
import uuid
from typing import Any, Dict, Optional

import boto3
import requests
from boto3.resources.base import ServiceResource

from schemas.ingest import IngestError
from services.crud import create_item, get_item_by_key
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.utils import audit_event, get_current_time_gmt


ENV_VARS = load_and_validate_env_vars(
    env_vars = {
        'DYNAMODB_TABLE_NAME_INGEST_DATASETS': str,
        'BUCKET_NAME': str,
        'FILES_SERVICE_URL': str,
    },
    optional_env_vars = {
        'BUCKET_PATH': str,
        'UPLOAD_TIMEOUT_SECONDS': int,
    }
)
DATASETS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_INGEST_DATASETS']
BUCKET_NAME = ENV_VARS['BUCKET_NAME']
FILES_SERVICE_URL = ENV_VARS['FILES_SERVICE_URL'].rstrip('/')
DEFAULT_BUCKET_PATH = (ENV_VARS['BUCKET_PATH'] or 'ingest').strip('/')
UPLOAD_TIMEOUT_SECONDS = ENV_VARS['UPLOAD_TIMEOUT_SECONDS'] or 60

# Region + credentials come from the default chain (Lambda role in AWS).
_s3_client = boto3.client('s3')


# ---------------------------------------------------------------------------
# Dataset metadata (DynamoDB)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Direct S3 access
# ---------------------------------------------------------------------------

def download_bytes(file_key: str) -> bytes:
    '''
        Downloads an object from the ingest bucket and returns its raw bytes.

        Args:
            file_key (str): S3 object key of the file to read.

        Returns:
            bytes: The object's content.

        Raises:
            ServiceUnavailableError: If S3 is unreachable or the key is missing.
    '''
    try:
        response = _s3_client.get_object(Bucket = BUCKET_NAME, Key = file_key)
        return response['Body'].read()
    except Exception as error:
        error_msg = f'Failed to download s3://{BUCKET_NAME}/{file_key}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = 'No se pudo leer el archivo subido desde el bucket.'
        ) from error


def upload_bytes(file_key: str, data: bytes, content_type: str) -> str:
    '''
        Writes bytes to the ingest bucket and returns the object key.

        Args:
            file_key (str): Destination S3 object key.
            data (bytes): Content to store.
            content_type (str): MIME type stored on the object.

        Returns:
            str: The stored object key.

        Raises:
            ServiceUnavailableError: If S3 rejects the write.
    '''
    try:
        _s3_client.put_object(
            Bucket = BUCKET_NAME,
            Key = file_key,
            Body = data,
            ContentType = content_type
        )
    except Exception as error:
        error_msg = f'Failed to upload s3://{BUCKET_NAME}/{file_key}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = 'No se pudo guardar el archivo normalizado en el bucket.'
        ) from error
    message = f'Stored normalized dataset at s3://{BUCKET_NAME}/{file_key}.'
    logger.info(message)
    return file_key


# ---------------------------------------------------------------------------
# FILES service
# ---------------------------------------------------------------------------

def _content_type_for(filename: str) -> str:
    '''
        Picks the multipart content-type the FILES service whitelists.
    '''
    lower = filename.lower()
    if lower.endswith('.xlsx'):
        return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    if lower.endswith('.csv'):
        return 'text/csv'
    return 'application/octet-stream'


def _key_from_url(raw_url: str, bucket_name: str) -> Optional[str]:
    '''
        Extracts the S3 object key from a FILES URL, preserving any folder
        prefix so downstream S3 downloads do not fail with NoSuchKey.

        Handles s3:// URIs, virtual-hosted style
        (https://<bucket>.s3.<region>.amazonaws.com/<key>) and path-style
        (https://s3.<region>.amazonaws.com/<bucket>/<key>) URLs.
    '''
    # s3://bucket/path/to/file → strip scheme + bucket
    if raw_url.startswith('s3://'):
        without_scheme = raw_url[len('s3://'):]
        if '/' in without_scheme:
            return without_scheme.split('/', 1)[1] or None
        return None

    bucket_token = f'/{bucket_name}/'
    if bucket_token in raw_url:
        return raw_url.split(bucket_token, 1)[1] or None

    # Last-resort: drop scheme + host, return whatever path remains.
    after_scheme = raw_url.split('://', 1)[-1]
    if '/' in after_scheme:
        return after_scheme.split('/', 1)[1] or None
    return None


def _extract_s3_key(payload: dict, bucket_name: str) -> Optional[str]:
    '''
        Extracts the FULL S3 object key from the FILES upload response.

        Current FILES `POST /v1/s3/upload` returns a dict with a canonical
        `file_key` field (plus legacy aliases and a `url`). We prefer the
        explicit key and fall back to parsing the URL.
    '''
    if not isinstance(payload, dict):
        return None

    direct = (
        payload.get('file_key')
        or payload.get('file_s3_key')
        or payload.get('key')
    )
    if direct:
        return direct

    raw_url = payload.get('url') or payload.get('s3_url') or ''
    if not raw_url:
        return None

    return _key_from_url(raw_url, bucket_name)


def upload_excel(
    file_bytes: bytes,
    filename: str,
    bearer_token: str,
    folder: str = ''
) -> str:
    '''
        Uploads a validated Excel/CSV file to S3 via the FILES microservice.

        Args:
            file_bytes (bytes): Raw file content.
            filename (str): Original filename (used as S3 key suffix).
            bearer_token (str): Authorization token (without the "Bearer " prefix).
            folder (str): Optional subpath inside the bucket. Falls back to
                          `BUCKET_PATH` env var (default `ingest`).

        Returns:
            str: The S3 object key assigned by FILES.

        Raises:
            ServiceUnavailableError: If FILES does not respond with 2xx or
                                     the response payload is unusable.
    '''
    url = f'{FILES_SERVICE_URL}/v1/s3/upload'
    target_folder = (folder or DEFAULT_BUCKET_PATH or '').strip('/')

    headers = {'Authorization': f'Bearer {bearer_token}'}
    files = {'file': (filename, file_bytes, _content_type_for(filename))}
    form = {
        'bucket_name': BUCKET_NAME,
        'file_path': target_folder
    }

    try:
        response = requests.post(
            url,
            headers = headers,
            files = files,
            data = form,
            timeout = UPLOAD_TIMEOUT_SECONDS
        )
    except requests.exceptions.RequestException as e:
        error_msg = f'Network error calling FILES at {url}: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = IngestError.FILES_SERVICE_UNREACHABLE.value
        ) from e

    if not response.ok:
        error_msg = (
            f'FILES upload failed: status={response.status_code} '
            f'body={response.text[:300]}'
        )
        logger.error(error_msg)
        raise ServiceUnavailableError(
            detail = IngestError.FILES_SERVICE_REJECTED_UPLOAD.value
        )

    payload: dict = {}
    try:
        payload = response.json()
    except ValueError:
        # FILES answered 2xx with a non-JSON body; the S3 key is then looked up
        # from the fallback path below instead of failing the whole upload.
        error_msg = f'FILES returned a non-JSON body: {response.text[:300]}'
        logger.warning(error_msg)

    s3_key = _extract_s3_key(payload, BUCKET_NAME)
    if not s3_key:
        # Last-resort fallback: rebuild the conventional key from what we sent.
        s3_key = f'{target_folder}/{filename}' if target_folder else filename
        message = (
            f'FILES response did not include a key; falling back to constructed '
            f'key "{s3_key}". Raw response: {payload}'
        )
        logger.warning(message)

    message = f'Excel "{filename}" uploaded via FILES; s3_key={s3_key}.'
    logger.info(message)
    return s3_key
