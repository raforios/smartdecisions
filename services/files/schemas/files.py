'''
    Files Schemas (Request/Response)
'''

import os
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FilesError(str, Enum):
    '''
        Why FILES refused a request: a code, the wording belongs to whoever
        shows it.
    '''
    EMPTY_FILE = 'EMPTY_FILE'
    UNSUPPORTED_FORMAT = 'UNSUPPORTED_FORMAT'
    FILE_NOT_FOUND = 'FILE_NOT_FOUND'
    ACCESS_DENIED = 'ACCESS_DENIED'
    STORAGE_UNAVAILABLE = 'STORAGE_UNAVAILABLE'


class FilesResult(str, Enum):
    '''
        What a request did, as a code.
    '''
    UPLOADED = 'UPLOADED'
    DELETED = 'DELETED'


# The files FILES takes, by extension, with the MIME type each travels as: the
# one list the upload, the presigned URL and the read all check against.
ALLOWED_TYPES: dict[str, str] = {
    '.csv': 'text/csv',
    '.xls': 'application/vnd.ms-excel',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.txt': 'text/plain',
    '.doc': 'application/msword',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.pdf': 'application/pdf',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
}

class BaseS3FileModel(BaseModel):
    '''
        Base model for S3 file-related requests with common fields and key logic.
    '''
    bucket_name: str = Field(..., description = 'Name of the S3 bucket.')
    file_path: str | None = Field('', description = 'Path within the S3 bucket.')
    file_name: str = Field(..., description = 'Name of the file.')

    @property
    def file_key(self) -> str:
        '''
            Generates the full S3 object key (path + filename).
        '''
        effective_file_path = self.file_path or ''
        return os.path.join(effective_file_path, self.file_name)
class S3FileRequest(BaseS3FileModel):
    '''
        S3File Request model.
    '''

class FileUploadData(BaseS3FileModel):
    '''
        FileUploadData model for file content and metadata.
    '''
    file_content: bytes
    content_type: str = Field(..., description = 'MIME type of the file (e.g., "text/csv").')

    # The raw bytes of the file travel as they are, with no Pydantic type.
    model_config = ConfigDict(arbitrary_types_allowed = True)

class ListFilesRequest(BaseModel):
    '''
        ListFiles Request model for S3 bucket file listing.
    '''
    bucket_name: str | None = Field(None,
                description = 'Optional: Name of the S3 bucket.')
    prefix: str | None = Field('',
                description = 'Optional prefix to filter files.')

class ListFilesResponse(BaseModel):
    '''
        ListFiles Response model for listed S3 files.
    '''
    bucket_name: str = Field(..., description = 'Name of the S3 bucket.')
    prefix: str = Field(..., description = 'Prefix used to filter files.')
    files: list[str] = Field(..., description = 'List of file keys found.')
    count: int = Field(..., description = 'Number of files in the list.')

class PresignedUrlRequest(BaseS3FileModel):
    '''
        PresignedUrl Request model for generating S3 pre-signed URLs.
    '''
    expiration_seconds: int = Field(3600,
                    description = 'Expiration time of the URL in seconds.')
    validation: bool = Field(...,
                    description = 'If validation for file extension should be used.')
    content_type: str | None = Field(None,
                    description = 'Optional: The Content-Type of the file.')

class PresignedUrlResponse(BaseModel):
    '''
        PresignedUrl Response model containing the URL and file key.
    '''
    presigned_url: str = Field(..., description = 'The generated pre-signed URL.')
    file_key: str = Field(..., description = 'The full S3 key.')


class FileReadResponse(BaseModel):
    '''
        A file read back: rows for a sheet, text for a .txt, base64 for the
        rest. Only the field of its kind is sent.
    '''
    filename: str = Field(..., description = 'The object key read.')
    data: list[dict[str, Any]] | None = Field(None, description = 'Rows of a CSV or Excel file.')
    content: str | None = Field(None, description = 'Text of a .txt file.')
    content_base64: str | None = Field(None, description = 'Bytes of a binary file, in base64.')


class FileUploadResponse(BaseModel):
    '''
        A file stored.
    '''
    message: FilesResult = Field(..., description = 'UPLOADED.')
    url: str = Field(..., description = 'The object URL.')
    file_key: str = Field(..., description = 'The full S3 key.')


class FileDeleteResponse(BaseModel):
    '''
        A file deleted.
    '''
    message: FilesResult = Field(..., description = 'DELETED.')
