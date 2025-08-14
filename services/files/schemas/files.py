'''
    Files Schemas (Request/Response)
'''

from typing import Optional, List
from pydantic import BaseModel, Field

class BaseS3FileModel(BaseModel):
    '''
        Base model for S3 file-related requests with common fields and key logic.
    '''
    bucket_name: str = Field(..., description = 'Name of the S3 bucket.')
    file_path: Optional[str] = Field('', description = 'Path within the S3 bucket.')
    file_name: str = Field(..., description = 'Name of the file.')

    @property
    def file_key(self):
        '''
            Generates the full S3 object key (path + filename).
        '''
        effective_file_path = self.file_path if self.file_path is not None else ''
        if effective_file_path and not effective_file_path.endswith('/'):
            return f'{effective_file_path}/{self.file_name}'
        return f'{effective_file_path}{self.file_name}'

class S3FileRequest(BaseS3FileModel):
    '''
        S3File Request model.
    '''
    # Inherits fields and file_key from BaseS3FileModel
    # pass # Pylint W0107 will no longer flag if there's content; it's fine as is if no content.

class FileUploadData(BaseS3FileModel):
    '''
        FileUploadData model for file content and metadata.
    '''
    file_content: bytes
    content_type: str = Field(..., description = 'MIME type of the file (e.g., "text/csv").')

    class Config: # pylint: disable=too-few-public-methods
        '''
            FileUploadData - Config Class - To get form attributes
        '''
        arbitrary_types_allowed = True

class ListFilesRequest(BaseModel):
    '''
        ListFiles Request model for S3 bucket file listing.
    '''
    bucket_name: Optional[str] = Field(None,
                description = 'Optional: Name of the S3 bucket.')
    prefix: Optional[str] = Field('',
                description = 'Optional prefix to filter files.')

class ListFilesResponse(BaseModel):
    '''
        ListFiles Response model for listed S3 files.
    '''
    bucket_name: str = Field(..., description = 'Name of the S3 bucket.')
    prefix: str = Field(..., description = 'Prefix used to filter files.')
    files: List[str] = Field(..., description = 'List of file keys found.')
    count: int = Field(..., description = 'Number of files in the list.')

class PresignedUrlRequest(BaseS3FileModel):
    '''
        PresignedUrl Request model for generating S3 pre-signed URLs.
    '''
    expiration_seconds: int = Field(3600,
                    description = 'Expiration time of the URL in seconds.')
    validation: bool = Field(...,
                    description = 'If validation for file extension should be used.')
    content_type: Optional[str] = Field(None,
                    description = 'Optional: The Content-Type of the file.')

class PresignedUrlResponse(BaseModel):
    '''
        PresignedUrl Response model containing the URL and file key.
    '''
    presigned_url: str = Field(..., description = 'The generated pre-signed URL.')
    file_key: str = Field(..., description = 'The full S3 key.')
