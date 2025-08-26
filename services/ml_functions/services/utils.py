'''
    Utility services for handling common tasks.
'''
import traceback
from functools import wraps
from fastapi import HTTPException, status
from services.logger_config import custom_logger as logger

def handle_ml_operation(func):
    '''
    Decorator to handle common exceptions for machine learning operations.
    '''
    @wraps(func)
    async def wrapper(*args, **kwargs):
        '''
        Wrapper function for the decorator.
        '''
        try:
            return await func(*args, **kwargs)
        except Exception as exc:
            error_msg = f'Internal server error while processing ML operation: {exc}'
            logger.error(error_msg, exc_info = True)
            logger.error(traceback.format_exc())
            error_msg = f'Internal server error while processing ML operation: {exc}'
            raise HTTPException(
                status_code = status.HTTP_503_SERVICE_UNAVAILABLE,
                detail = error_msg
            ) from exc
    return wrapper
