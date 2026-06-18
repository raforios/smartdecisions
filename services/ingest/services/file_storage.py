'''
    HTTP client for the FILES microservice (S3-backed storage gateway).

    The Ingest service does NOT talk to S3 directly: all object operations go
    through FILES, which owns the bucket, pre-signed URLs, encryption, and
    audit logging. This keeps the storage policy centralized.
'''
from typing import Optional
import requests

from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger

ENV_VARS = load_and_validate_env_vars({
    'FILES_SERVICE_URL': str
})

FILES_SERVICE_URL = ENV_VARS['FILES_SERVICE_URL'].rstrip('/')
UPLOAD_TIMEOUT_SECONDS = 30


def upload_excel(
    file_bytes: bytes,
    filename: str,
    bearer_token: str,
    folder: str = 'ingest'
) -> str:
    '''
        Uploads a validated Excel/CSV file to S3 via the FILES microservice.

        Args:
            file_bytes (bytes): Raw file content.
            filename (str): Original filename (used to preserve extension in S3).
            bearer_token (str): Authorization header value (sin el prefijo "Bearer ").
            folder (str): Logical folder/prefix inside the bucket. Defaults to 'ingest'.

        Returns:
            str: The S3 object key assigned by FILES.

        Raises:
            ServiceUnavailableError: If FILES does not respond with 2xx or the
                                     payload does not include a file key.
    '''
    url = f'{FILES_SERVICE_URL}/v1/files/upload'
    headers = {'Authorization': f'Bearer {bearer_token}'}
    files = {'file': (filename, file_bytes)}
    data = {'folder': folder}

    try:
        response = requests.post(
            url,
            headers = headers,
            files = files,
            data = data,
            timeout = UPLOAD_TIMEOUT_SECONDS
        )
    except requests.exceptions.RequestException as e:
        error_msg = f'Network error calling FILES at {url}: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = 'No se pudo contactar al servicio de archivos.'
        ) from e

    if not response.ok:
        error_msg = (
            f'FILES upload failed: status={response.status_code} '
            f'body={response.text[:200]}'
        )
        logger.error(error_msg)
        raise ServiceUnavailableError(
            detail = 'El servicio de archivos rechazó la subida del Excel.'
        )

    payload = response.json()
    s3_key: Optional[str] = payload.get('file_s3_key') or payload.get('key')
    if not s3_key:
        error_msg = f'FILES response missing s3 key: {payload}'
        logger.error(error_msg)
        raise ServiceUnavailableError(
            detail = 'Respuesta inválida del servicio de archivos.'
        )

    message = f'Excel "{filename}" uploaded to S3 with key={s3_key}.'
    logger.info(message)
    return s3_key
