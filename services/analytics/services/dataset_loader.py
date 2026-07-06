'''
    Dataset loader — bridges the analytics service with the ingest output.

    Reads the dataset metadata (file_s3_key, owner) from `t_ingest_datasets`,
    downloads the raw .xlsx / .csv from S3 with boto3 and returns it as a
    pandas DataFrame ready for the affinity engine.

    Note on the service boundary: the cleanest design would route this through
    FILES (HTTP). For the POC we go straight to S3 with boto3 to avoid an
    extra hop; both services share the same AWS account and bucket.
'''
from io import BytesIO
import boto3
import pandas as pd
from boto3.resources.base import ServiceResource

from services.environment import load_and_validate_env_vars
from services.exceptions import (
    InvalidInputError,
    RegisterNotFoundError,
    ServiceUnavailableError
)
from services.logger_config import custom_logger as logger

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_INGEST_DATASETS': str,
    'BUCKET_NAME': str,
})

INGEST_DATASETS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_INGEST_DATASETS']
FILES_BUCKET_NAME = ENV_VARS['BUCKET_NAME']

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
            pd.DataFrame: Sales rows ready for the affinity engine.

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
