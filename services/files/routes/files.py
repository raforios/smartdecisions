'''
    Files: routes handler
'''
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from core.environment import load_and_validate_env_vars
from core.security import get_current_owner
from core.logger_config import custom_logger as logger
from controllers.files import (
    create_download_url,
    read_data_from_s3,
    upload_s3_file,
    delete_s3_file,
    list_s3_files,
    create_presigned_upload_url
)
from schemas.files import (
    FileDeleteResponse,
    FileDownloadResponse,
    FileReadResponse,
    FileUploadData,
    FileUploadResponse,
    ListFilesRequest,
    ListFilesResponse,
    PresignedUrlRequest,
    PresignedUrlResponse,
    S3FileRequest
)

router = APIRouter(prefix = '/v1/s3', tags = ['Management S3 File System'])

ENV_VARS = load_and_validate_env_vars({
    'ML_DATA_BUCKET_NAME': str,
})
# The bucket a listing falls back to when the caller names none. Required, not
# optional: a service that lists "whatever bucket the environment happened to
# have" cannot say whose files it just showed.
ML_DATA_BUCKET_NAME = ENV_VARS['ML_DATA_BUCKET_NAME']

@router.get(
    '/read/{bucket_name}/{file_key:path}',
    response_model = FileReadResponse,
    response_model_exclude_none = True
)
async def read_s3_file_route(
    bucket_name: str,
    file_key: str,
    owner: str = Depends(get_current_owner),
    delimiter: str | None = Query(None, description = 'The delimiter used for CSV files.')
) -> FileReadResponse:
    '''
        Reads a file from an S3 bucket, processes it, and returns the data.

        Args:
            bucket_name (str): S3 bucket name.
            file_key (str): The file key (full path) within the S3 bucket.
            owner (str): The caller's owner key; its files are the only ones it reaches.

        Returns:
            FileReadResponse: Rows, text or base64, by the kind of file.
    '''
    message = f'Owner: {owner} accessing file: {file_key} in bucket: {bucket_name
            } with delimiter {delimiter}.'
    logger.info(message)
    return await read_data_from_s3(
        bucket_name = bucket_name,
        file_key = file_key,
        owner = owner,
        delimiter = delimiter
    )

@router.post(
    '/upload',
    response_model = FileUploadResponse
)
async def upload_file_to_s3_route(
    file: UploadFile = File(...),
    bucket_name: str = Form(..., description = 'Name of the S3 bucket.'),
    file_path: str = Form('', description='Path within the S3 bucket.'),
    owner: str = Depends(get_current_owner)
) -> FileUploadResponse:
    '''
        Uploads a file to a specified S3 bucket.

        Args:
            file (UploadFile): The file to upload.
            bucket_name (str): The S3 bucket name.
            file_path (str): The path within the S3 bucket (e.g., 'data/raw/').
            owner (str): The caller's owner key; its files are the only ones it reaches.

        Returns:
            FileUploadResponse: UPLOADED, the URL and the key.
    '''
    message = f'Owner: {owner} attempting to upload file: {file.filename
            } to bucket: {bucket_name}/{file_path}.'
    logger.info(message)

    file_content = await file.read()

    upload_data_obj = FileUploadData(
        bucket_name = bucket_name,
        file_path = file_path,
        file_name = file.filename,
        file_content = file_content,
        content_type = file.content_type
    )

    return await upload_s3_file(upload_data_obj, owner)

@router.delete(
    '/delete',
    response_model = FileDeleteResponse
)
async def delete_file_from_s3_route(
    request: S3FileRequest,
    owner: str = Depends(get_current_owner)
) -> FileDeleteResponse:
    '''
        Deletes a specified file from an S3 bucket.

        Args:
            request (S3FileRequest): Contains bucket_name, file_path, and file_name.
            owner (str): The caller's owner key; its files are the only ones it reaches.

        Returns:
            FileDeleteResponse: DELETED.
    '''
    message = f'Owner: {owner} attempting to delete file: {
        request.file_key} from bucket: {request.bucket_name}.'

    logger.info(message)
    return await delete_s3_file(request.bucket_name, request.file_key, owner)

@router.post(
    '/list-files',
    response_model = ListFilesResponse
)
async def list_files_s3_route(
    request: ListFilesRequest,
    owner: str = Depends(get_current_owner)
) -> ListFilesResponse:
    '''
        Lists files in the predefined ML data S3 bucket with an optional prefix.

        Args:
            request (ListFilesRequest): Contains bucket_name and an optional prefix.
            owner (str): The caller's owner key; its files are the only ones it reaches.

        Returns:
            ListFilesResponse: A dictionary with the list of files.
    '''
    target_bucket = request.bucket_name or ML_DATA_BUCKET_NAME

    message = f'Owner: {owner} attempting to list files in bucket: {
            target_bucket} with prefix: {request.prefix}.'

    logger.info(message)
    files_list = await list_s3_files(target_bucket, request.prefix, owner)

    return ListFilesResponse(bucket_name = target_bucket, prefix = request.prefix,
                             files = files_list, count = len(files_list))

@router.post(
    '/upload-presigned',
    response_model = PresignedUrlResponse
)
async def get_presigned_upload_url_route(
    request: PresignedUrlRequest,
    owner: str = Depends(get_current_owner)
) -> PresignedUrlResponse:
    '''
        Generates an S3 pre-signed URL for direct file upload from the client.

        Args:
            request (PresignedUrlRequest): Contains bucket_name, file_path, file_name,
            expiration_seconds.
            owner (str): The caller's owner key; its files are the only ones it reaches.

        Returns:
            PresignedUrlResponse: A dictionary containing the pre-signed URL and the full S3 key.
    '''
    message = (f'Owner: {owner} requesting presigned URL for {request.file_key} '
               f'in bucket {request.bucket_name}.')
    logger.info(message)
    return await create_presigned_upload_url(request, owner)


@router.get(
    '/download-url/{bucket_name}/{file_key:path}',
    response_model = FileDownloadResponse
)
async def get_download_url_route(
    bucket_name: str,
    file_key: str,
    owner: str = Depends(get_current_owner)
) -> FileDownloadResponse:
    '''
        A short-lived URL to fetch one object directly from the bucket: the
        way a file too large to come back as rows, or one that must stay a
        file, reaches its caller.

        Args:
            bucket_name (str): S3 bucket name.
            file_key (str): The object key.
            owner (str): The caller's owner key; its files are the only ones it reaches.

        Returns:
            FileDownloadResponse: The URL, the key and how long it lives.
    '''
    message = f'Owner: {owner} asking a download URL for {file_key} in {bucket_name}.'
    logger.info(message)
    return await create_download_url(bucket_name, file_key, owner)
