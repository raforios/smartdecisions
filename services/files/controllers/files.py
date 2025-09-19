'''
    Files controller
'''
import os
import base64
from io import StringIO, BytesIO
from typing import List, Optional
import pandas as pd
import boto3
from schemas.files import FileUploadData
from services.logger_config import custom_logger as logger
from services.exceptions import (
    InvalidInputError
)
from services.utils import handle_aws_operation

s3_client = boto3.client('s3')

@handle_aws_operation
# pylint: disable=too-many-locals
async def read_data_from_s3(
    bucket_name: str,
    file_key: str,
    current_user: str,
    delimiter: Optional[str] = None
) -> dict:
    '''
    Loads data from a given S3 bucket and processes it based on file extension.

    This function supports CSV and Excel files, returning their content as a
    list of dictionaries. It also supports reading plain text files, and
    binary files like images and documents (JPG, PNG, DOC, PDF).

    Args:
        bucket_name (str): The name of the S3 bucket.
        file_key (str): The key of the file to load.
        current_user (str): The user accessing the file.

    Returns:
        dict: A dictionary containing the filename and the processed data or
              text/binary content.

    Raises:
        InvalidInputError: If the file extension is not supported or the file
                           is empty.
        ServiceUnavailableError: For internal server errors during processing.
    '''
    _context = {'bucket_name': bucket_name, 'file_key': file_key}
    response = s3_client.get_object(Bucket = bucket_name, Key = file_key)
    file_extension = os.path.splitext(file_key)[1].lower()

    match file_extension:
        case '.csv' | '.xls' | '.xlsx':
            try:
                file_content = response['Body'].read()
                df: pd.DataFrame
                if file_extension == '.csv':
                    df = pd.read_csv(StringIO(file_content.decode('utf-8')), delimiter = delimiter)
                else:
                    df = pd.read_excel(BytesIO(file_content))

                processed_data = df.to_dict(orient = 'records')
                message = f'''Data file {file_key} was accessed and processed by
                        user {current_user} on bucket {bucket_name}.'''
                logger.info(message)
                return {'filename': file_key, 'data': processed_data}
            except pd.errors.EmptyDataError as e:
                error_msg = f'File {file_key} is empty or not in the expected format.'
                logger.error(error_msg, exc_info = True)
                raise InvalidInputError(detail = error_msg) from e

        case '.txt':
            file_content = response['Body'].read().decode('utf-8')
            message = f'''Text file {file_key} was accessed and read by user {current_user}
                    on bucket {bucket_name}.'''
            logger.info(message)
            return {'filename': file_key, 'content': file_content}

        case '.doc' | '.docx' | '.pdf' | '.jpg' | '.jpeg' | '.png':
            file_content_bytes = response['Body'].read()
            encoded_content = base64.b64encode(file_content_bytes).decode('utf-8')
            message = f'''Binary file {file_key} was accessed and read by user {current_user}
                    on bucket {bucket_name}.'''
            logger.info(message)
            return {'filename': file_key, 'content_base64': encoded_content}

        case _:
            allowed_extensions = [
                '.csv', '.xls', '.xlsx', '.txt', '.doc', '.docx', '.pdf', '.jpg', '.jpeg', '.png'
            ]
            error_msg = f'''Unsupported file format for {file_key}.
                    Allowed file types are: {', '.join(allowed_extensions)}.'''
            logger.error(error_msg, exc_info = True)
            raise InvalidInputError(detail = error_msg)

@handle_aws_operation
async def upload_s3_file(
    upload_data: FileUploadData,
    current_user: str
) -> dict:
    '''
    Uploads a file to a specified S3 bucket.
    '''
    _context = {'bucket_name': upload_data.bucket_name, 'file_key': upload_data.file_key}
    s3_client.put_object(
        Bucket = upload_data.bucket_name,
        Key = upload_data.file_key,
        Body = upload_data.file_content,
        ContentType = upload_data.content_type
    )

    file_url = f'https://{upload_data.bucket_name}.s3.amazonaws.com/{upload_data.file_key}'
    message = f'''File {upload_data.file_name} uploaded successfully by
            user {current_user} to bucket {upload_data.bucket_name}. URL: {file_url}'''
    logger.info(message)

    return {
        'message': f'File {upload_data.file_name} uploaded successfully.',
        'url': file_url,
        'file_key': upload_data.file_key
    }

@handle_aws_operation
async def delete_s3_file(
    bucket_name: str,
    file_key: str,
    current_user: str
) -> dict:
    '''
    Deletes a file from a given S3 bucket.
    '''
    _context = {'bucket_name': bucket_name, 'file_key': file_key}
    s3_client.delete_object(Bucket = bucket_name, Key = file_key)
    message = f'''File {file_key} deleted successfully by user {current_user}
            from bucket {bucket_name}.'''
    logger.info(message)
    return {'message': f'File {file_key} deleted successfully from {bucket_name}.'}

@handle_aws_operation
async def list_s3_files(
    bucket_name: str,
    prefix: str,
    current_user: str
) -> List[str]:
    '''
    Lists files in a given S3 bucket with an optional prefix.
    '''
    _context = {'bucket_name': bucket_name, 'prefix': prefix}
    files = []
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket = bucket_name, Prefix = prefix)

    for page in pages:
        if 'Contents' in page:
            for obj in page['Contents']:
                if not obj['Key'].endswith('/'):
                    files.append(obj['Key'])

    message = f'''User {current_user} listed {len(files)} files in bucket {bucket_name}
            with prefix {prefix}.'''
    logger.info(message)
    return files

@handle_aws_operation
async def create_presigned_upload_url(
    bucket_name: str,
    file_key: str,
    expiration: int,
    current_user: str,
    content_type: str
) -> str:
    '''
    Generates a pre-signed URL for uploading an object to S3.
    '''
    _context = {'bucket_name': bucket_name, 'file_key': file_key}
    response = s3_client.generate_presigned_url(
        ClientMethod='put_object',
        Params={
            'Bucket': bucket_name,
            'Key': file_key,
            'ContentType': content_type
        },
        ExpiresIn=expiration
    )
    message = f'''User {current_user} generated a presigned URL for {file_key}
            in bucket {bucket_name}.'''
    logger.info(message)
    return response
