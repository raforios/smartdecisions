'''
    Utility functions and decorators for the Files service.
'''
from collections.abc import Callable, Awaitable
import inspect
from typing import Any
from functools import wraps
from botocore.exceptions import ClientError
from fastapi import HTTPException

from core.exceptions import (
    ResourceNotFoundError,
    ForbiddenError,
    ServiceUnavailableError
)
from core.logger_config import custom_logger as logger
from schemas.files import FilesError

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
    # The bucket, the key and the prefix go to the log, where the 404 must name
    # them (Rafael, 19-oct-2026); the caller receives the code.
    where = ', '.join(f'{name} {value}' for name, value in context_info.items() if value)
    error_msg = f'S3 answered {error_code} for {where or "an S3 resource"}: {e}'
    logger.error(error_msg, exc_info = True)
    match error_code:
        case 'NoSuchKey' | 'NoSuchBucket':
            raise ResourceNotFoundError(detail = FilesError.FILE_NOT_FOUND.value) from e
        case 'AccessDenied':
            raise ForbiddenError(detail = FilesError.ACCESS_DENIED.value) from e
        case _:
            raise ServiceUnavailableError(detail = FilesError.STORAGE_UNAVAILABLE.value) from e

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
            # The names come from the call itself: as plain arguments (read:
            # bucket_name, file_key) or as fields of the request body. Reading
            # only the body left a read's 404 saying "Bucket None or file None"
            # (Rafael, 19-oct-2026).
            context: dict[str, Any] = {}
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
            raise ServiceUnavailableError(detail = FilesError.STORAGE_UNAVAILABLE.value) from e
    return wrapper
