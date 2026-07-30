'''
    Direct S3 access (boto3) for large-file ingestion.

    Files that exceed the ~10 MB API Gateway payload limit are uploaded straight
    to S3 by the browser (pre-signed URL) and read/written here with boto3, so a
    real-sized sales export never transits API Gateway or Lambda's request body.
    The ingest Lambda role already carries S3 access.
'''
import boto3

from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger

ENV_VARS = load_and_validate_env_vars({'BUCKET_NAME': str})
BUCKET_NAME = ENV_VARS['BUCKET_NAME']

# Region + credentials come from the default chain (Lambda role in AWS).
_s3_client = boto3.client('s3')


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
