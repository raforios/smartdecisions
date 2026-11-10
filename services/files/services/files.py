'''
    The bucket: reading, storing, deleting and listing objects, and signing
    direct uploads. Every refusal is a code of `FilesError`.
'''
import base64
import hashlib
import os
import re
from io import BytesIO, StringIO

import boto3
import pandas as pd

from core.environment import load_and_validate_env_vars
from core.exceptions import ForbiddenError, InvalidInputError
from core.logger_config import custom_logger as logger
from core.utils import handle_aws_operation
from schemas.files import (
    ALLOWED_TYPES,
    FileDeleteResponse,
    FileDownloadResponse,
    FileReadResponse,
    FilesError,
    FilesResult,
    FileUploadData,
    FileUploadResponse,
    PresignedUrlRequest,
    PresignedUrlResponse
)

ENV_VARS = load_and_validate_env_vars({'ALLOWED_BUCKETS': str, 'DOWNLOAD_URL_SECONDS': int,
                                       'PUBLIC_READ_PREFIXES': str})
# The only buckets FILES works on: the caller names one of them, never any
# other the Lambda's role happens to reach.
ALLOWED_BUCKETS: frozenset[str] = frozenset(ENV_VARS['ALLOWED_BUCKETS'].split())

# What every company may read and nobody writes through FILES: the templates.
PUBLIC_READ_PREFIXES: tuple[str, ...] = tuple(
    prefix.strip('/') + '/' for prefix in ENV_VARS['PUBLIC_READ_PREFIXES'].split())

# Every other object lives in the folder of the company that owns it
# (Rafael, 5-nov-2026): the caller names a key relative to its own folder, so
# it cannot name another company's file.
TENANTS_ROOT = 'tenants'

s3_client = boto3.client('s3')

# How each readable kind comes back.
SHEETS = ('.csv', '.xls', '.xlsx')
TEXTS = ('.txt',)


def extension_of(file_key: str) -> str:
    '''
        The extension of an object key, lower case.

        Args:
            file_key (str): The object key.

        Returns:
            str: Such as '.csv'.
    '''
    return os.path.splitext(file_key)[1].lower()


def require_allowed(
    extension: str | None = None,
    content_type: str | None = None
) -> None:
    '''
        Refuses a file FILES does not take, by extension or by MIME type.

        Args:
            extension (str | None): The extension, when it is checked.
            content_type (str | None): The MIME type, when it is checked.

        Raises:
            InvalidInputError: UNSUPPORTED_FORMAT.
    '''
    refused = ((extension is not None and extension not in ALLOWED_TYPES)
               or (content_type is not None and content_type not in ALLOWED_TYPES.values()))
    if refused:
        error_msg = f'Unsupported file: extension {extension}, content type {content_type}.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = FilesError.UNSUPPORTED_FORMAT.value)


def owner_folder(owner: str) -> str:
    '''
        The folder of one owner: its name made safe for a key, and a digest
        of the exact name so two names that read alike never share a folder.

        Args:
            owner (str): The owner key (client, or e-mail without one).

        Returns:
            str: Such as 'tenants/distribuidora-andina-s-r-l-3f2a1c'.
    '''
    slug = re.sub(r'[^a-z0-9]+', '-', owner.lower()).strip('-')
    digest = hashlib.sha256(owner.encode('utf-8')).hexdigest()[:6]
    return f'{TENANTS_ROOT}/{slug}-{digest}'


def owned_key(
    file_key: str,
    owner: str
) -> str:
    '''
        The full key of an object the caller owns: its relative key inside
        the caller's folder.

        Args:
            file_key (str): The key as the caller names it.
            owner (str): The caller's owner key.

        Returns:
            str: The key in the bucket.

        Raises:
            InvalidInputError: INVALID_KEY, for an empty key, an absolute one
                or one that climbs out with '..'.
    '''
    relative = (file_key or '').strip()
    if not relative or relative.startswith('/') or '..' in relative.split('/'):
        error_msg = f'Key refused for {owner}: {file_key!r}.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = FilesError.INVALID_KEY.value)
    return f'{owner_folder(owner)}/{relative}'


def readable_key(
    file_key: str,
    owner: str
) -> str:
    '''
        The full key of an object the caller may read: a public template as
        it is, anything else inside the caller's folder.

        Args:
            file_key (str): The key as the caller names it.
            owner (str): The caller's owner key.

        Returns:
            str: The key in the bucket.
    '''
    if file_key.startswith(PUBLIC_READ_PREFIXES) and '..' not in file_key.split('/'):
        return file_key
    return owned_key(file_key, owner)


def require_bucket(bucket_name: str) -> None:
    '''
        Refuses a bucket outside ALLOWED_BUCKETS.

        Args:
            bucket_name (str): The bucket the caller named.

        Raises:
            ForbiddenError: BUCKET_NOT_ALLOWED.
    '''
    if bucket_name not in ALLOWED_BUCKETS:
        error_msg = f'Bucket {bucket_name} refused: it is not one FILES works on.'
        logger.warning(error_msg)
        raise ForbiddenError(detail = FilesError.BUCKET_NOT_ALLOWED.value)


def _sheet_rows(
    file_key: str,
    content: bytes,
    delimiter: str | None
) -> list[dict]:
    '''
        The rows of a CSV or Excel file.

        Args:
            file_key (str): The object key, for its extension and the log.
            content (bytes): The file.
            delimiter (str | None): The CSV separator; sniffed when None.

        Returns:
            list[dict]: One dictionary per row.

        Raises:
            InvalidInputError: EMPTY_FILE.
    '''
    # Empty is said here, not left to pandas: from 3.1 an empty CSV no longer
    # raises EmptyDataError but a delimiter error, and the caller's mistake came
    # back as a 503 (GitHub Actions, 22-oct-2026).
    try:
        if not content.strip():
            raise pd.errors.EmptyDataError(f'{file_key} has no content.')
        if extension_of(file_key) == '.csv':
            # Sniffing the separator (delimiter None) is only done by the python
            # engine; saying so keeps pandas from warning about it.
            frame = pd.read_csv(StringIO(content.decode('utf-8')), delimiter = delimiter,
                                engine = 'python' if delimiter is None else 'c')
        else:
            frame = pd.read_excel(BytesIO(content))
    except pd.errors.EmptyDataError as error:
        error_msg = f'File {file_key} is empty or not in the expected format.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = FilesError.EMPTY_FILE.value) from error
    return frame.to_dict(orient = 'records')


@handle_aws_operation
async def read_file(
    bucket_name: str,
    file_key: str,
    owner: str,
    delimiter: str | None = None
) -> FileReadResponse:
    '''
        Reads an object: rows for a sheet, text for a .txt, base64 for the
        documents and images.

        Args:
            bucket_name (str): The bucket.
            file_key (str): The object key.
            owner (str): The caller's owner key: the file is read inside its folder,
                unless it is a public template.
            delimiter (str | None): The CSV separator; sniffed when None.

        Returns:
            FileReadResponse: The content, in the field of its kind.

        Raises:
            InvalidInputError: UNSUPPORTED_FORMAT or EMPTY_FILE.
    '''
    require_bucket(bucket_name)
    extension = extension_of(file_key)
    require_allowed(extension = extension)
    content = s3_client.get_object(Bucket = bucket_name,
                                   Key = readable_key(file_key, owner))['Body'].read()
    message = f'File {file_key} of bucket {bucket_name} read by {owner}.'
    logger.info(message)
    if extension in SHEETS:
        return FileReadResponse(filename = file_key,
                                data = _sheet_rows(file_key, content, delimiter))
    if extension in TEXTS:
        return FileReadResponse(filename = file_key, content = content.decode('utf-8'))
    return FileReadResponse(filename = file_key,
                            content_base64 = base64.b64encode(content).decode('utf-8'))


@handle_aws_operation
async def store_file(
    upload_data: FileUploadData,
    owner: str
) -> FileUploadResponse:
    '''
        Stores an object.

        Args:
            upload_data (FileUploadData): Where, what and its MIME type.
            owner (str): The caller's owner key: the file is stored in its folder.

        Returns:
            FileUploadResponse: UPLOADED, the URL and the key.

        Raises:
            ForbiddenError: BUCKET_NOT_ALLOWED.
            InvalidInputError: UNSUPPORTED_FORMAT, by extension or MIME type.
    '''
    require_bucket(upload_data.bucket_name)
    require_allowed(extension = extension_of(upload_data.file_key),
                    content_type = upload_data.content_type)
    s3_client.put_object(Bucket = upload_data.bucket_name,
                         Key = owned_key(upload_data.file_key, owner),
                         Body = upload_data.file_content,
                         ContentType = upload_data.content_type)
    file_url = f'https://{upload_data.bucket_name}.s3.amazonaws.com/{upload_data.file_key}'
    message = (f'File {upload_data.file_key} stored by {owner} in bucket '
               f'{upload_data.bucket_name}.')
    logger.info(message)
    return FileUploadResponse(message = FilesResult.UPLOADED, url = file_url,
                              file_key = upload_data.file_key)


@handle_aws_operation
async def delete_file(
    bucket_name: str,
    file_key: str,
    owner: str
) -> FileDeleteResponse:
    '''
        Deletes an object.

        Args:
            bucket_name (str): The bucket.
            file_key (str): The object key.
            owner (str): The caller's owner key: only its own files can go.

        Returns:
            FileDeleteResponse: DELETED.

        Raises:
            ForbiddenError: BUCKET_NOT_ALLOWED.
    '''
    require_bucket(bucket_name)
    s3_client.delete_object(Bucket = bucket_name, Key = owned_key(file_key, owner))
    message = f'File {file_key} deleted by {owner} from bucket {bucket_name}.'
    logger.info(message)
    return FileDeleteResponse(message = FilesResult.DELETED)


@handle_aws_operation
async def list_files(
    bucket_name: str,
    prefix: str,
    owner: str
) -> list[str]:
    '''
        The object keys under a prefix, folders left out.

        Args:
            bucket_name (str): The bucket.
            prefix (str): The prefix.
            owner (str): The caller's owner key: only its folder is listed.

        Returns:
            list[str]: The keys.

        Raises:
            ForbiddenError: BUCKET_NOT_ALLOWED.
    '''
    require_bucket(bucket_name)
    folder = owner_folder(owner) + '/'
    keys = [item['Key'][len(folder):]
            for page in s3_client.get_paginator('list_objects_v2').paginate(
                Bucket = bucket_name, Prefix = folder + (prefix or '').lstrip('/'))
            for item in page.get('Contents', []) if not item['Key'].endswith('/')]
    message = f'{owner} listed {len(keys)} file(s) in {bucket_name} under {prefix}.'
    logger.info(message)
    return keys


@handle_aws_operation
async def presigned_upload_url(
    request: PresignedUrlRequest,
    owner: str
) -> PresignedUrlResponse:
    '''
        A URL the client uploads one object to directly, so the bytes do not
        go through API Gateway. The extension of the key written is always
        checked and the MIME type is the one it calls for: the signature
        fixes both, so the URL cannot carry anything else.

        Args:
            request (PresignedUrlRequest): Where and for how long.
            owner (str): The caller's owner key: the URL points inside its folder.

        Returns:
            PresignedUrlResponse: The signed URL and the key.

        Raises:
            ForbiddenError: BUCKET_NOT_ALLOWED.
            InvalidInputError: UNSUPPORTED_FORMAT.
    '''
    require_bucket(request.bucket_name)
    extension = extension_of(request.file_key)
    require_allowed(extension = extension)
    content_type = ALLOWED_TYPES[extension]
    url = s3_client.generate_presigned_url(
        ClientMethod = 'put_object',
        Params = {'Bucket': request.bucket_name, 'Key': owned_key(request.file_key, owner),
                  'ContentType': content_type},
        ExpiresIn = request.expiration_seconds
    )
    message = (f'{owner} got a presigned URL for {request.file_key} in '
               f'{request.bucket_name} ({content_type}).')
    logger.info(message)
    return PresignedUrlResponse(presigned_url = url, file_key = request.file_key)


@handle_aws_operation
async def download_url(
    bucket_name: str,
    file_key: str,
    owner: str
) -> FileDownloadResponse:
    '''
        A short-lived URL to fetch one object as it is stored: a file too
        large to come back as rows, or one that must stay a file (a template).

        Args:
            bucket_name (str): The bucket.
            file_key (str): The object key.
            owner (str): The caller's owner key: the URL points inside its folder.

        Returns:
            FileDownloadResponse: The URL, the key and how long it lives.

        Raises:
            ForbiddenError: BUCKET_NOT_ALLOWED.
            InvalidInputError: UNSUPPORTED_FORMAT.
    '''
    require_bucket(bucket_name)
    require_allowed(extension = extension_of(file_key))
    seconds = ENV_VARS['DOWNLOAD_URL_SECONDS']
    url = s3_client.generate_presigned_url(
        ClientMethod = 'get_object',
        Params = {'Bucket': bucket_name, 'Key': readable_key(file_key, owner)},
        ExpiresIn = seconds)
    message = f'{owner} got a download URL for {file_key} in {bucket_name}.'
    logger.info(message)
    return FileDownloadResponse(url = url, file_key = file_key, expires_in = seconds)
