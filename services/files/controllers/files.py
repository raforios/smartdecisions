'''
    Files controller: each request handed to `services/files.py`.
'''
from schemas.files import (
    FileDeleteResponse,
    FileDownloadResponse,
    FileReadResponse,
    FileUploadData,
    FileUploadResponse,
    PresignedUrlRequest,
    PresignedUrlResponse
)
from services import files


async def read_data_from_s3(
    bucket_name: str,
    file_key: str,
    owner: str,
    delimiter: str | None = None
) -> FileReadResponse:
    '''
        Reads an object.
    '''
    return await files.read_file(bucket_name, file_key, owner, delimiter)


async def upload_s3_file(
    upload_data: FileUploadData,
    owner: str
) -> FileUploadResponse:
    '''
        Stores an object.
    '''
    return await files.store_file(upload_data, owner)


async def delete_s3_file(
    bucket_name: str,
    file_key: str,
    owner: str
) -> FileDeleteResponse:
    '''
        Deletes an object.
    '''
    return await files.delete_file(bucket_name, file_key, owner)


async def list_s3_files(
    bucket_name: str,
    prefix: str,
    owner: str
) -> list[str]:
    '''
        Lists the object keys under a prefix.
    '''
    return await files.list_files(bucket_name, prefix, owner)


async def create_presigned_upload_url(
    request: PresignedUrlRequest,
    owner: str
) -> PresignedUrlResponse:
    '''
        Signs a direct upload.
    '''
    return await files.presigned_upload_url(request, owner)


async def create_download_url(
    bucket_name: str,
    file_key: str,
    owner: str
) -> FileDownloadResponse:
    '''
        Signs a direct download.
    '''
    return await files.download_url(bucket_name, file_key, owner)
