'''
    The bucket: reading, storing, deleting and listing objects, and signing
    direct uploads. Every refusal is a code of `FilesError`.
'''
import base64
import os
from io import BytesIO, StringIO
from mimetypes import guess_type

import boto3
import pandas as pd

from schemas.files import (
    ALLOWED_TYPES,
    FileDeleteResponse,
    FileReadResponse,
    FilesError,
    FilesResult,
    FileUploadData,
    FileUploadResponse,
    PresignedUrlRequest,
    PresignedUrlResponse
)
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger
from services.utils import handle_aws_operation

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


def content_type_for(file_name: str) -> str:
    '''
        The MIME type a name suggests, or a generic one.

        Args:
            file_name (str): The file name.

        Returns:
            str: The MIME type.
    '''
    mime_type, _ = guess_type(file_name)
    return mime_type or 'application/octet-stream'


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
    current_user: str,
    delimiter: str | None = None
) -> FileReadResponse:
    '''
        Reads an object: rows for a sheet, text for a .txt, base64 for the
        documents and images.

        Args:
            bucket_name (str): The bucket.
            file_key (str): The object key.
            current_user (str): Who reads it, for the log.
            delimiter (str | None): The CSV separator; sniffed when None.

        Returns:
            FileReadResponse: The content, in the field of its kind.

        Raises:
            InvalidInputError: UNSUPPORTED_FORMAT or EMPTY_FILE.
    '''
    extension = extension_of(file_key)
    require_allowed(extension = extension)
    content = s3_client.get_object(Bucket = bucket_name, Key = file_key)['Body'].read()
    message = f'File {file_key} of bucket {bucket_name} read by {current_user}.'
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
    current_user: str
) -> FileUploadResponse:
    '''
        Stores an object.

        Args:
            upload_data (FileUploadData): Where, what and its MIME type.
            current_user (str): Who stores it, for the log.

        Returns:
            FileUploadResponse: UPLOADED, the URL and the key.

        Raises:
            InvalidInputError: UNSUPPORTED_FORMAT.
    '''
    require_allowed(content_type = upload_data.content_type)
    s3_client.put_object(Bucket = upload_data.bucket_name, Key = upload_data.file_key,
                         Body = upload_data.file_content,
                         ContentType = upload_data.content_type)
    file_url = f'https://{upload_data.bucket_name}.s3.amazonaws.com/{upload_data.file_key}'
    message = (f'File {upload_data.file_key} stored by {current_user} in bucket '
               f'{upload_data.bucket_name}.')
    logger.info(message)
    return FileUploadResponse(message = FilesResult.UPLOADED, url = file_url,
                              file_key = upload_data.file_key)


@handle_aws_operation
async def delete_file(
    bucket_name: str,
    file_key: str,
    current_user: str
) -> FileDeleteResponse:
    '''
        Deletes an object.

        Args:
            bucket_name (str): The bucket.
            file_key (str): The object key.
            current_user (str): Who deletes it, for the log.

        Returns:
            FileDeleteResponse: DELETED.
    '''
    s3_client.delete_object(Bucket = bucket_name, Key = file_key)
    message = f'File {file_key} deleted by {current_user} from bucket {bucket_name}.'
    logger.info(message)
    return FileDeleteResponse(message = FilesResult.DELETED)


@handle_aws_operation
async def list_files(
    bucket_name: str,
    prefix: str,
    current_user: str
) -> list[str]:
    '''
        The object keys under a prefix, folders left out.

        Args:
            bucket_name (str): The bucket.
            prefix (str): The prefix.
            current_user (str): Who lists, for the log.

        Returns:
            list[str]: The keys.
    '''
    keys = [item['Key']
            for page in s3_client.get_paginator('list_objects_v2').paginate(
                Bucket = bucket_name, Prefix = prefix)
            for item in page.get('Contents', []) if not item['Key'].endswith('/')]
    message = f'{current_user} listed {len(keys)} file(s) in {bucket_name} under {prefix}.'
    logger.info(message)
    return keys


@handle_aws_operation
async def presigned_upload_url(
    request: PresignedUrlRequest,
    current_user: str
) -> PresignedUrlResponse:
    '''
        A URL the client uploads one object to directly, so the bytes do not
        go through API Gateway. The MIME type is the one given, or the one the
        name suggests.

        Args:
            request (PresignedUrlRequest): Where, for how long, and whether the
                extension is checked.
            current_user (str): Who asks, for the log.

        Returns:
            PresignedUrlResponse: The signed URL and the key.

        Raises:
            InvalidInputError: UNSUPPORTED_FORMAT, when the extension is checked.
    '''
    if request.validation:
        require_allowed(extension = extension_of(request.file_name))
    content_type = request.content_type or content_type_for(request.file_name)
    url = s3_client.generate_presigned_url(
        ClientMethod = 'put_object',
        Params = {'Bucket': request.bucket_name, 'Key': request.file_key,
                  'ContentType': content_type},
        ExpiresIn = request.expiration_seconds
    )
    message = (f'{current_user} got a presigned URL for {request.file_key} in '
               f'{request.bucket_name} ({content_type}).')
    logger.info(message)
    return PresignedUrlResponse(presigned_url = url, file_key = request.file_key)
