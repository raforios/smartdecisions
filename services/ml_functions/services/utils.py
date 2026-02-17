'''
    Utility services for handling common tasks.
'''
import traceback
from functools import wraps
from typing import Callable, Type, Optional, Any
from fastapi import HTTPException, status
from services.logger_config import custom_logger as logger

def handle_operation(
    exc_type: Type[Exception] = Exception,
    error_detail: Optional[str] = None
):
    '''
    Decorator to handle exceptions for any operation in a standardized way.
    It catches a specified exception type and raises a custom HTTP exception.
    
    Args:
        exc_type (Type[Exception]): The type of exception to catch.
                                    Defaults to the base Exception class.
        error_detail (Optional[str]): A custom error message to use for
                                      the HTTPException.
    '''
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any):
            try:
                context = kwargs.get('_context', None)
                if not context and args:
                    for arg in args:
                        if isinstance(arg, dict) and '_context' in arg:
                            context = arg['_context']
                            break

                return await func(*args, **kwargs)
            except exc_type as exc:
                error_msg = error_detail or f'Error processing operation: {exc}'

                if context:
                    error_msg += f' with context: {context}'

                logger.error(error_msg, exc_info=True)
                logger.error(traceback.format_exc())

                if isinstance(exc, (ValueError, TypeError)):
                    http_status = status.HTTP_400_BAD_REQUEST
                else:
                    http_status = status.HTTP_503_SERVICE_UNAVAILABLE

                raise HTTPException(
                    status_code = http_status,
                    detail = error_msg
                ) from exc
        return wrapper
    return decorator
