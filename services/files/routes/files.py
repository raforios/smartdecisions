'''
    Files: routes handler
'''
import os
from typing import Dict, Any
from mimetypes import guess_type
from fastapi import APIRouter, Depends, UploadFile, File
from fastapi import Form
from controllers.files import (
    read_data_from_s3,
    upload_s3_file,
    delete_s3_file,
    list_s3_files
)
from controllers.files import create_presigned_upload_url
from schemas.files import (
    S3FileRequest,
    ListFilesRequest,
    ListFilesResponse,
    FileUploadData
)
from schemas.files import (
    PresignedUrlRequest,
    PresignedUrlResponse
)

from services.security import get_current_user
from services.logger_config import custom_logger as logger
from services.exceptions import InvalidInputError

router = APIRouter(prefix = '/v1/s3', tags = ['Management S3 File System'])

ALLOWED_EXTENSIONS = ['.csv', '.xls', '.xlsx', '.txt']
ALLOWED_CONTENT_TYPES = [
    'text/csv',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain'
]

@router.get('/read/{bucket_name}/{file_key}', response_model = Dict[str, Any])
async def read_s3_file(
    bucket_name: str,
    file_key: str,
    current_user: str = Depends(get_current_user)):
    '''
    Reads a CSV file from an S3 bucket, processes it, and returns the data as JSON.

    Args:
        bucket_name (str): bucket S3 name.
        file_key (str): The file key (full path) within the S3 bucket.

    Returns:
        Dict[str, Any]: A dictionary containing the processed data from the file.

    '''
    message = f'User: {current_user} accessing file: {file_key} in bucket: {bucket_name}.'
    logger.info(message)
    return await read_data_from_s3(bucket_name, file_key, current_user)

@router.post('/upload', response_model = Dict[str, str])
async def upload_file_to_s3(
    file: UploadFile = File(...),
    bucket_name: str = Form(..., description = 'Name of the S3 bucket.'),
    file_path: str = Form('', description='Path within the S3 bucket.'),
    current_user: str = Depends(get_current_user)
):
    '''
    Uploads a CSV, Excel, or TXT file to a specified S3 bucket.

    Args:
        file (UploadFile): The file to upload (CSV, Excel, or TXT).
        bucket_name (str): The S3 bucket name.
        file_path (str): The path within the S3 bucket (e.g., 'data/raw/').
        current_user (str): The authenticated user.

    Returns:
        Dict[str, str]: A dictionary containing the S3 URL of the uploaded file.

    '''
    message = f'''User: {current_user} attempting to upload file: {file.filename}
    to bucket: {bucket_name}/{file_path}.'''
    logger.info(message)

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        error_msg = f'''Unsupported file type: {file.content_type}.
        Only CSV, Excel and TXT files are allowed.'''
        logger.error(error_msg)
        raise InvalidInputError(
            detail = error_msg
        )

    file_content = await file.read()

    upload_data_obj = FileUploadData(
        bucket_name = bucket_name,
        file_path = file_path,
        file_name = file.filename,
        file_content = file_content,
        content_type = file.content_type
    )

    return await upload_s3_file(
        upload_data_obj,
        current_user
    )

@router.delete('/delete', response_model = Dict[str, str])
async def delete_file_from_s3(
    request: S3FileRequest,
    current_user: str = Depends(get_current_user)
):
    '''
    Deletes a specified file from an S3 bucket.

    Args:
        request (S3FileRequest): Contains bucket_name, file_path, and file_name.
        current_user (str): The authenticated user.

    Returns:
        Dict[str, str]: A message indicating success.

    '''
    message = f'''User: {current_user} attempting to delete file:
    {request.file_key} from bucket: {request.bucket_name}.'''

    logger.info(message)
    return await delete_s3_file(request.bucket_name, request.file_key, current_user)

@router.post('/list-files', response_model = ListFilesResponse)
async def list_files_s3(
    request: ListFilesRequest,
    current_user: str = Depends(get_current_user)
):
    '''
    Lists files in the predefined ML data S3 bucket with an optional prefix.

    Args:
        request (ListFilesRequest): Contains bucket_name and an optional prefix.
        current_user (str): The authenticated user.

    Returns:
        ListFilesResponse: A dictionary with the list of files.

    '''
    predefined_ml_data_bucket = os.environ.get('ML_DATA_BUCKET_NAME')

    target_bucket = request.bucket_name if request.bucket_name else predefined_ml_data_bucket

    message = f'''User: {current_user} attempting to list files in bucket:
    {target_bucket} with prefix: {request.prefix}.'''

    logger.info(message)
    files_list = await list_s3_files(target_bucket, request.prefix, current_user)

    return {
        'bucket_name': target_bucket,
        'prefix': request.prefix,
        'files': files_list,
        'count': len(files_list)
    }

def get_content_type_from_filename(
    filename: str
) -> str:
    '''
        Try to guess the MIME type, if not, use a generic value.
    '''
    mime_type, _ = guess_type(filename)
    return mime_type if mime_type else 'application/octet-stream'

@router.post('/upload-presigned', response_model = PresignedUrlResponse)
async def get_presigned_upload_url(
    request: PresignedUrlRequest,
    current_user: str = Depends(get_current_user)
):
    '''
    Generates an S3 pre-signed URL for direct file upload from the client.

    Args:
        request (PresignedUrlRequest): Contains bucket_name, file_path, file_name,
        expiration_seconds. current_user (str): The authenticated user.

    Returns:
        PresignedUrlResponse: A dictionary containing the pre-signed URL and the full S3 key.
    '''
    file_extension = os.path.splitext(request.file_name)[1].lower()

    if request.validation :
        if file_extension not in ALLOWED_EXTENSIONS:
            error_msg = f'''Unsupported file type: {file_extension}.
            Only CSV (.csv), Excel (.xls, .xlsx) and TXT (.txt) files are allowed for upload.'''

            raise InvalidInputError(
                detail = error_msg
            )

    content_type_for_signature = request.content_type
    message = f'Content-Type provided by client: {content_type_for_signature}'
    if not content_type_for_signature:
        message = f'Content-Type not provided by client. Inferred: {content_type_for_signature}'
        content_type_for_signature = get_content_type_from_filename(request.file_name)

    logger.info(message)

    message = f'''User: {current_user} requesting presigned URL for {request.file_key}
    in bucket {request.bucket_name}.'''

    logger.info(message)

    presigned_url = await create_presigned_upload_url(
        request.bucket_name,
        request.file_key,
        request.expiration_seconds,
        current_user,
        content_type = content_type_for_signature
    )
    return {'presigned_url': presigned_url, 'file_key': request.file_key}
