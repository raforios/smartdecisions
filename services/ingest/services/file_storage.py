'''
    HTTP client for the FILES microservice.

    Calls `POST {FILES_SERVICE_URL}/v1/s3/upload` with a multipart payload
    (field `file` + form fields `bucket_name` + `file_path`). The FILES
    service responds with a dict that includes the S3 URL / key of the
    uploaded object.
'''
from typing import Optional
import requests

from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger

ENV_VARS = load_and_validate_env_vars(
    env_vars = {
        'FILES_SERVICE_URL': str,
        'BUCKET_NAME': str
    },
    optional_env_vars = {
        'BUCKET_PATH': str
    }
)

FILES_SERVICE_URL = ENV_VARS['FILES_SERVICE_URL'].rstrip('/')
BUCKET_NAME = ENV_VARS['BUCKET_NAME']
DEFAULT_BUCKET_PATH = (ENV_VARS.get('BUCKET_PATH') or 'ingest').strip('/')

UPLOAD_TIMEOUT_SECONDS = 60


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
            detail = 'No se pudo contactar al servicio de archivos.'
        ) from e

    if not response.ok:
        error_msg = (
            f'FILES upload failed: status={response.status_code} '
            f'body={response.text[:300]}'
        )
        logger.error(error_msg)
        raise ServiceUnavailableError(
            detail = (
                'El servicio de archivos rechazó la subida del Excel '
                f'({response.status_code}).'
            )
        )

    payload: dict = {}
    try:
        payload = response.json()
    except ValueError:
        pass

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
