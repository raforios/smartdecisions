'''
    Utils service
'''

from functools import wraps
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
