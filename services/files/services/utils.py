'''
    Utility functions and decorators for the Files service.
'''
from collections.abc import Callable, Awaitable
import inspect
from typing import Any
from functools import wraps
from botocore.exceptions import ClientError
from fastapi import HTTPException
from services.exceptions import (
    ResourceNotFoundError,
    ForbiddenError,
    ServiceUnavailableError
)
from services.logger_config import custom_logger as logger

def handle_aws_client_error(
    e: ClientError,
    context_info: dict[str, Any]
) -> None:
    '''
        Handles Boto3 ClientError exceptions, translating them to custom HTTP exceptions.
        
        Args:
            e (ClientError): The Boto3 ClientError exception to handle.
            context_info (dict[str, Any]): A dictionary containing contextual information
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
    async def wrapper(
        *args,
        **kwargs
    ) -> Any:
        try:
            return await func(*args, **kwargs)
        except ClientError as e:
            # Check for explicit context argument first
            context = kwargs.get('_context', {})

            if not context:
                # The names come from the call itself: as plain arguments
                # (read: bucket_name, file_key) or as fields of the request
                # body. Reading only the body left a read's 404 saying
                # "Bucket None or file None" (Rafael, 19-oct-2026).
                bound = inspect.signature(func).bind_partial(*args, **kwargs).arguments
                request_body = next(iter(bound.values()), None)
                for name in ('bucket_name', 'file_key', 'prefix'):
                    value = bound.get(name, getattr(request_body, name, None))
                    if value:
                        context[name] = value

            handle_aws_client_error(e, context)
        except HTTPException:
            # Already an answer for the caller (an empty or unsupported file is
            # a 400); wrapping it below would turn it into a 503 (Rafael, 19-oct-2026).
            raise
        except Exception as e:
            error_msg = f'Internal server error while processing the operation: {e}'
            logger.error(error_msg, exc_info = True)
            raise ServiceUnavailableError(detail = error_msg) from e
    return wrapper
