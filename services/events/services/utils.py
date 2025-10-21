'''
    Utils service
'''
from datetime import datetime
from zoneinfo import ZoneInfo
from functools import wraps
from typing import Any, Dict
from botocore.exceptions import ClientError as AWSClientError
from services.logger_config import custom_logger as logger
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from services.environment import load_and_validate_env_vars

# Carga las variables de entorno necesarias
ENV_VARS = load_and_validate_env_vars(
    {
        'TARGET_TIMEZONE': str
    }
)

TARGET_TIMEZONE = ENV_VARS['TARGET_TIMEZONE']

def get_current_time_gmt() -> datetime:
    '''
        Returns the current datetime object aware of the target timezone.
        This function should be used as the default value for all SQLAlchemy 
        DateTime columns to ensure database consistency.
    '''
    tz = ZoneInfo(TARGET_TIMEZONE)
    return datetime.now(tz = tz)

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
