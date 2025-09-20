'''
    Utils service
'''
from functools import wraps
from typing import Any, Dict
from botocore.exceptions import ClientError as AWSClientError
from services.logger_config import custom_logger as logger
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)

def handle_service_errors(func):
    '''
        Decorator to handle common exceptions in service functions.
    '''
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AWSClientError as e:
            error_msg = f'AWS client error in {func.__name__}: {e}'
            logger.error(error_msg, exc_info = True)
            raise RuntimeError('A database client error occurred.') from e
        except Exception as e:
            if isinstance(e, (RegisterAlreadyExistsError, RegisterNotFoundError,
                InvalidInputError)):
                raise e

            error_msg = f'Unexpected error in {func.__name__}: {e}'
            logger.critical(error_msg, exc_info = True)
            raise RuntimeError('An unexpected internal error occurred.') from e
    return wrapper

def process_query_params(
    query_params: Any
) -> Dict[str, Any]:
    '''
        Processes query parameters from a Pydantic model or dictionary
        into a dictionary for DynamoDB queries.
    '''
    if hasattr(query_params, 'dict'):
        return query_params.dict(exclude_none=True)
    return query_params
