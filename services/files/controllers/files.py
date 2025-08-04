'''
    Files controller
'''

import os
from io import StringIO, BytesIO
from typing import List, Dict, Any
import pandas as pd
import boto3
from botocore.exceptions import ClientError
from schemas.files import FileUploadData
from services.logger_config import custom_logger as logger
from services.exceptions import (
    ResourceNotFoundError,
    ForbiddenError,
    InvalidInputError,
    ServiceUnavailableError
)

s3_client = boto3.client('s3')

def _handle_s3_client_error(
    e: ClientError,
    context_info: Dict[str, Any]
) -> None:
    '''
        Handles Boto3 ClientError exceptions, translating them to custom HTTP exceptions.
        
        Args:
            error (ClientError): The Boto3 ClientError exception to handle.
            context_info (Dict[str, Any]): A dictionary containing contextual information
                                        like 'bucket_name', 'file_key', or 'prefix'.
        
        Raises:
            ResourceNotFoundError: If the S3 bucket or file does not exist.
            ForbiddenError: If there is an access denied issue.
            ServiceUnavailableError: For any other unexpected S3 errors.
    '''
    error_code = e.response.get('Error', {}).get('Code')
    bucket_name = context_info.get('bucket_name')
    file_key = context_info.get('file_key')
    prefix = context_info.get('prefix')

    match error_code:
        case 'NoSuchKey' | 'NoSuchBucket':
            error_msg = f'''Bucket '{bucket_name}' or file '{file_key}'
                        not found.'''
            logger.error(error_msg, exc_info = True)
            raise ResourceNotFoundError(
                detail = error_msg
            ) from e

        case 'AccessDenied':
            msg_context = ''
            if bucket_name:
                msg_context += f'bucket {bucket_name}'
            if file_key:
                msg_context += f' or file {file_key}'
            if prefix:
                msg_context += f' or prefix {prefix}'

            if not msg_context:
                msg_context = 'S3 resource'

            error_msg = f"Access denied to {msg_context}."
            logger.error(error_msg, exc_info = True)
            raise ForbiddenError(
                detail = error_msg
            ) from e

        case _:
            error_msg = f"Unexpected S3 error: {e}"
            logger.error(error_msg, exc_info = True)
            raise ServiceUnavailableError(
                detail = error_msg
            ) from e


async def read_data_from_s3(
    bucket_name: str,
    file_key: str,
    current_user: str
) -> dict:
    '''
        Loads data from a given S3 bucket and processes it based on file extension.

        This function supports CSV and Excel files, returning their content as a
        list of dictionaries. It also supports reading plain text files.

        Args:
            bucket_name (str): The name of the S3 bucket.
            file_key (str): The key of the file to load.
            current_user (str): The user accessing the file.

        Returns:
            dict: A dictionary containing the filename and the processed data or
                text content.

        Raises:
            InvalidInputError: If the file extension is not supported or the file
                            is empty.
            ServiceUnavailableError: For internal server errors during processing.
    '''
    try:
        response = s3_client.get_object(Bucket = bucket_name, Key = file_key)
        file_extension = os.path.splitext(file_key)[1].lower()
        processed_data: Any = None
        df = None

        match file_extension:
            case '.csv':
                file_content = response['Body'].read().decode('utf-8')
                df = pd.read_csv(StringIO(file_content))
                message = f'''CSV file '{file_key}' was accessed and processed by
                user '{current_user}' on bucket '{bucket_name}'.'''
                logger.info(message)

            case '.xls' | '.xlsx':
                file_content_bytes = response['Body'].read()
                df = pd.read_excel(BytesIO(file_content_bytes))
                message = f'''Excel file '{file_key}' was accessed and processed by
                user '{current_user}' on bucket '{bucket_name}'.'''
                logger.info(message)

            case '.txt':
                file_content = response['Body'].read().decode('utf-8')
                message = f'''Text file '{file_key}' was accessed and read by
                user '{current_user}' on bucket '{bucket_name}'.'''
                logger.info(message)
                return {'filename': file_key, 'content': file_content}

            case _:
                error_msg = f'''Unsupported file format for '{file_key}'. Only CSV (.csv)
                and Excel (.xls, .xlsx) files are supported for processing.'''
                logger.error(error_msg, exc_info = True)
                raise InvalidInputError(
                    detail = error_msg
                )

        processed_data = df.to_dict(orient='records')
        message = f'''File '{file_key}' was successfully processed and returned by
                user '{current_user}' on bucket '{bucket_name}'.'''
        logger.info(message)
        return {'filename': file_key, 'data': processed_data}

    except ClientError as e:
        _handle_s3_client_error(
            e,
            {'bucket_name': bucket_name, 'file_key': file_key}
        )
    except pd.errors.EmptyDataError as e:
        error_msg = f'{file_key} file is empty or is not in the expected CSV format.'
        logger.error(error_msg, exc_info = True)
        raise InvalidInputError(
            detail = error_msg
        ) from e
    except Exception as e:
        error_msg = f'Internal server error while processing the file: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = error_msg
        ) from e

async def upload_s3_file(
    upload_data: FileUploadData,
    current_user: str
) -> dict:
    '''
        Upload a file to a specified S3 bucket.

        Handles CSV and Excel files.
    '''
    bucket_name = upload_data.bucket_name
    file_path = upload_data.file_path
    file_name = upload_data.file_name
    file_content = upload_data.file_content
    content_type = upload_data.content_type

    try:
        s3_client.put_object(
            Bucket = bucket_name,
            Key = upload_data.file_key,
            Body = file_content,
            ContentType = content_type
        )

        message = f'''{file_name} uploaded successfully by user {current_user}
            to bucket {bucket_name}/{file_path}.'''

        logger.info(message)
        return {'message': f'File {file_name} uploaded successfully to {bucket_name}/{file_path}'}

    except ClientError as e:
        _handle_s3_client_error(
            e,
            {'bucket_name': bucket_name, 'file_key': upload_data.file_key}
        )
    except Exception as e:
        error_msg = f'Internal server error during file upload: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = error_msg
        ) from e

async def delete_s3_file(
    bucket_name: str,
    file_key: str,
    current_user: str
) -> dict:
    '''
        Delete a file from a given S3 bucket.
    '''
    try:
        s3_client.delete_object(Bucket=bucket_name, Key = file_key)
        message = f'''{file_key} deleted successfully by user {current_user}
        from bucket {bucket_name}.'''
        logger.info(message)
        return {'message': f'File {file_key} deleted successfully from {bucket_name}'}
    except ClientError as e:
        _handle_s3_client_error(
            e,
            {'bucket_name': bucket_name, 'file_key': file_key}
        )
    except Exception as e:
        error_msg = f'Internal server error during file deletion: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = error_msg
        ) from e

async def list_s3_files(
    bucket_name: str,
    prefix: str,
    current_user: str
) -> List[str]:
    '''
        List files in a given S3 bucket with an optional prefix.
    '''
    try:
        files = []
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    if not obj['Key'].endswith('/') and obj['Key'] != prefix:
                        files.append(obj['Key'])

        message = f'''User: {current_user} listed {len(files)} files in bucket
        {bucket_name} with prefix {prefix}.'''
        logger.info(message)
        return files
    except ClientError as e:
        _handle_s3_client_error(
            e,
            {'bucket_name': bucket_name, 'prefix': prefix}
        )
    except Exception as e:
        error_msg = f'Internal server error during file listing: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = error_msg
        ) from e

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
    try:
        response = s3_client.generate_presigned_url(
            ClientMethod = 'put_object',
            Params = {
                'Bucket': bucket_name,
                'Key': file_key,
                'ContentType': content_type
            },
            ExpiresIn=expiration
        )
        message = f'''User: {current_user} generated presigned URL for {file_key} in
        bucket {bucket_name}.'''

        logger.info(message)
        return response
    except ClientError as e:
        _handle_s3_client_error(
            e,
            {'bucket_name': bucket_name, 'file_key': file_key}
        )
    except Exception as e:
        error_msg = f'Internal server error while generating presigned URL: {e}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = error_msg
        ) from e
