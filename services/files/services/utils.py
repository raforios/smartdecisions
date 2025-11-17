'''
    Utility functions and decorators for the Files service.
'''
from typing import Dict, Any, Callable, Awaitable
from functools import wraps
from botocore.exceptions import ClientError
from services.exceptions import (
    ResourceNotFoundError,
    ForbiddenError,
    ServiceUnavailableError
)
from services.logger_config import custom_logger as logger

def handle_aws_client_error(
    e: ClientError,
    context_info: Dict[str, Any]
) -> None:
    '''
        Handles Boto3 ClientError exceptions, translating them to custom HTTP exceptions.
        
        Args:
            e (ClientError): The Boto3 ClientError exception to handle.
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

    error_msg: str
    match error_code:
        case 'NoSuchKey' | 'NoSuchBucket':
            error_msg = f'Bucket {bucket_name} or file {file_key} not found.'
            logger.error(error_msg, exc_info = True)
            raise ResourceNotFoundError(detail = error_msg) from e
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
            error_msg = f'Access denied to {msg_context}.'
            logger.error(error_msg, exc_info = True)
            raise ForbiddenError(detail = error_msg) from e
        case _:
            error_msg = f'Unexpected S3 error: {e}'
            logger.error(error_msg, exc_info = True)
            raise ServiceUnavailableError(detail = error_msg) from e

def handle_aws_operation(
    func: Callable[..., Awaitable[Any]]
) -> Callable[..., Awaitable[Any]]:
    '''
        Decorator to handle AWS-related exceptions and map them to custom exceptions.
    '''
    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except ClientError as e:
            # Check for explicit context argument first
            context = kwargs.get('_context', {})

            if not context and args:
                # Fallback to the original logic if no _context is provided
                request_body = args[0]
                if hasattr(request_body, 'bucket_name'):
                    context['bucket_name'] = request_body.bucket_name
                if hasattr(request_body, 'file_key'):
                    context['file_key'] = request_body.file_key
                if hasattr(request_body, 'prefix'):
                    context['prefix'] = request_body.prefix

            handle_aws_client_error(e, context)
        except Exception as e:
            error_msg = f'Internal server error while processing the operation: {e}'
            logger.error(error_msg, exc_info = True)
            raise ServiceUnavailableError(detail = error_msg) from e
    return wrapper
