'''
    Utils service
'''

from typing import Any, Callable, Optional, Type
from functools import wraps
from pydantic import BaseModel, TypeAdapter
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from services.logger_config import custom_logger as logger
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)


def handle_service_errors(func):
    '''
        Decorator to handle common SQLAlchemy and other exceptions in service functions.
    '''
    @wraps(func)
    def wrapper(*args, **kwargs):
        db: Session = kwargs.get('db')

        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as e:
            if db:
                db.rollback()
            error_msg = f'Database error in {func.__name__}: {e}'
            logger.error(error_msg, exc_info = True)
            raise e
        except Exception as e:
            if isinstance(e, (RegisterAlreadyExistsError, RegisterNotFoundError,
                            InvalidInputError)):
                raise e

            if db:
                db.rollback()
            error_msg = f'Unexpected error in {func.__name__}: {e}'
            logger.critical(error_msg, exc_info = True)
            raise RuntimeError('An unexpected internal error occurred.') from e
    return wrapper

def handle_controller_call(
    func: Callable,
    operation: str,
    *args: Any,
    response_model: Optional[Type[BaseModel]] = None,
    **kwargs: Any
) -> Any:
    '''
        Generic utility function to handle common try/except blocks in controllers
        and validate the response model.
    '''
    try:
        message = f'Starting controller operation: {operation}'
        logger.info(message)
        result = func(*args, **kwargs)

        if response_model and result is not None:
            if response_model.__name__ == 'list' \
                or hasattr(response_model, '__origin__') \
                and response_model.__origin__ is list:
                adapter = TypeAdapter(response_model)
                return adapter.validate_python(result, from_attributes = True)
            return response_model.model_validate(result, from_attributes = True)

        return result
    except (RegisterNotFoundError, RegisterAlreadyExistsError, InvalidInputError) as e:
        error_msg = f'Failed to {operation}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during {operation}: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e
