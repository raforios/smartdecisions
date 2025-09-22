'''
    CRUD service
'''
from typing import List, Optional, Dict, Any, Type, Union
from sqlalchemy.orm import Session, DeclarativeBase, selectinload, Load
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from pydantic import BaseModel

# Import custom exceptions for specific error scenarios
from services.exceptions import (
    RegisterNotFoundError
)
from services.logger_config import custom_logger as logger

def handle_db_exception(e: Exception, operation: str, entity_id: Any = None):
    '''
        Handles various database exceptions and re-raises appropriate
        custom exceptions or generic errors.

        This function acts as a centralized point for database-related
        exception handling, allowing controllers to focus on business logic.
        Specific NotFound and AlreadyExists errors are expected to be
        handled more granularly by the caller or get_record directly.
    '''
    # Re-raise specific NotFoundErrors that might come from nested calls (e.g., get_record)
    if isinstance(e, (RegisterNotFoundError)):
        raise e
    # Re-raise IntegrityError; controllers are expected to catch this
    # to provide specific business context (e.g., 'Form with this code already exists').
    if isinstance(e, IntegrityError):
        error_msg = (
            f'Integrity error during {operation} for '
            f'{entity_id if entity_id else 'entity'}: {e}'
        )
        logger.error(error_msg, exc_info = True)
        raise e
    if isinstance(e, SQLAlchemyError):
        error_msg = (
            f'SQLAlchemy error during {operation} for '
            f'{entity_id if entity_id else 'entity'}: {e}'
        )
        logger.error(error_msg, exc_info = True)
        raise RuntimeError('A database error occurred during the operation.') from e

    error_msg = f'''Unexpected error during {operation} for
            {entity_id if entity_id else 'entity'}: {e}'''
    logger.critical(error_msg, exc_info = True)
    raise RuntimeError('An unexpected internal error occurred.') from e

def create_record(
    db: Session, model: Type[DeclarativeBase], create_data: BaseModel,
    extra_fields: Optional[Dict[str, Any]] = None,
    exclude_relations: Optional[List[str]] = None
) -> DeclarativeBase:
    '''
        Generic function to create a new record in the database.

        Args:
            db (Session): The database session.
            model (Type[DeclarativeBase]): The SQLAlchemy model class.
            create_data (BaseModel): Pydantic schema with data for the new record.
            extra_fields (Optional[Dict[str, Any]]): Additional fields to add/override.

        Returns:
            DeclarativeBase: The newly created database record.

        Raises:
            IntegrityError: If a unique constraint is violated (handled by handle_db_exception).
            SQLAlchemyError: For other database-related errors (handled by handle_db_exception).
            Exception: For any other unexpected errors.
    '''
    try:
        data_dict = create_data.model_dump(exclude = set(exclude_relations or []))

        # Merge extra_fields
        if extra_fields:
            data_dict.update(extra_fields)

        message = f'Creating record for model {model.__name__} with data: {data_dict}'
        logger.debug(message)
        # The nested dict list warning is still relevant if exclude_relations isn't perfect
        if any(isinstance(v, list) and
               any(isinstance(item, dict) for item in v) for v in data_dict.values()):
            message = f'''Data dict for {model.__name__} still contains nested dict lists,
                    despite exclusion: {data_dict}'''
            logger.warning(message)

        db_record = model(**data_dict)
        db.add(db_record)
        db.flush() # Flush to get ID for relationships if needed before commit
        # Add db.refresh here to ensure ID is populated immediately
        db.refresh(db_record)
        return db_record
    except (IntegrityError, SQLAlchemyError, RegisterNotFoundError) as e:
        handle_db_exception(e, 'creation')
        raise
    except Exception as e:
        db.rollback()
        handle_db_exception(e, 'creation')
        raise

def get_record(
    db: Session, model: Type[DeclarativeBase],
    record_id: int,
    eager_load_options: Optional[List[Union[str, Load]]] = None
) -> DeclarativeBase:
    '''
        Generic function to retrieve a record by ID with flexible eager loading.

        Args:
            db (Session): The database session.
            model (Type[DeclarativeBase]): The SQLAlchemy model class to query.
            record_id (int): The ID of the record to retrieve.
            eager_load_options (Optional[List[Union[str, Load]]]):
                A list of relationship names (strings) or
                SQLAlchemy Load objects for eager loading.

        Returns:
            DeclarativeBase: The retrieved database record.

        Raises:
            RegisterNotFoundError: If the record is not found.
            Exception: For any other unexpected errors.
    '''

    try:
        query = db.query(model)
        if eager_load_options:
            for option in eager_load_options:
                match option:
                    case str():
                        # Use selectinload for simple relationship names
                        query = query.options(selectinload(getattr(model, option)))
                    case Load():
                        # Pass Load objects directly
                        query = query.options(option)
                    case _:
                        # Handle any other type
                        message = f'''Invalid eager_load_option type: {type(option)}.
                        Must be a string or a SQLAlchemy Load object.'''
                        logger.error(message, exc_info = True)
                        raise TypeError(message)

        record = query.filter(model.id == record_id).first()
        if not record:
            message = f'{model.__name__} with ID {record_id} not found.'
            logger.warning(message)
            raise RegisterNotFoundError(detail = message)
        return record
    except (SQLAlchemyError, RegisterNotFoundError, TypeError) as e:
        handle_db_exception(e, 'retrieval', record_id)
        raise
    except Exception as e:
        handle_db_exception(e, 'retrieval', record_id)
        raise

def update_record(
    db: Session, db_record: DeclarativeBase,
    update_data: BaseModel,
    exclude_relations: Optional[List[str]] = None
) -> DeclarativeBase:
    '''
        Generic function to update an existing record.

        Args:
            db (Session): The database session.
            db_record (DeclarativeBase): The existing database record to update.
            update_data (BaseModel): Pydantic schema with update data.

        Returns:
            DeclarativeBase: The updated database record.

        Raises:
            IntegrityError: If a unique constraint is violated (handled by handle_db_exception).
            SQLAlchemyError: For other database-related errors (handled by handle_db_exception).
            Exception: For any other unexpected errors.
    '''
    try:
        update_data_dict = update_data.model_dump(exclude_unset = True,
                            exclude=set(exclude_relations or []))
        for key, value in update_data_dict.items():
            setattr(db_record, key, value)
        db.add(db_record)
        db.flush() # Flush to apply changes before commit
        return db_record
    except (IntegrityError, SQLAlchemyError, RegisterNotFoundError) as e:
        handle_db_exception(e, 'update', db_record.id)
        raise
    except Exception as e:
        db.rollback()
        handle_db_exception(e, 'update', db_record.id)
        raise

def delete_record(db: Session, model: Type[DeclarativeBase], record_id: int):
    '''
        Generic function to delete a record by ID.

        Args:
            db (Session): The database session.
            model (Type[DeclarativeBase]): The SQLAlchemy model class.
            record_id (int): The ID of the record to delete.

        Raises:
            RegisterNotFoundError: If model is FormHeader and record is not found.
            Exception: For any other unexpected errors during deletion.
    '''
    try:
        db_record = get_record(db, model, record_id)
        db.delete(db_record)
        db.flush() # Flush to ensure deletion is processed
    except (IntegrityError, SQLAlchemyError, RegisterNotFoundError) as e:
        handle_db_exception(e, 'deletion', record_id)
    except Exception as e:
        db.rollback()
        handle_db_exception(e, 'deletion', record_id)
        raise

def get_all_records_paginated(
    db: Session, model: Type[DeclarativeBase],
    skip: int = 0, limit: int = 100,
    eager_load_options: Optional[List] = None
) -> List[DeclarativeBase]:
    '''
        Generic function to retrieve a paginated list of all records for a given model.

        Args:
            db (Session): The database session.
            model (Type[DeclarativeBase]): The SQLAlchemy model class to query.
            skip (int): The number of records to skip (offset).
            limit (int): The maximum number of records to retrieve.
            eager_load_options (Optional[List]): List of joinedload options for eager loading.

        Returns:
            List[DeclarativeBase]: A list of retrieved database records.

        Raises:
            SQLAlchemyError: For database-related errors (handled by handle_db_exception).
            Exception: For any other unexpected errors.
    '''
    try:
        query = db.query(model)
        if eager_load_options:
            for option in eager_load_options:
                query = query.options(option)

        records = query.offset(skip).limit(limit).all()
        message = f'''Retrieved {len(records)} records for model {model.__name__}
                (skip: {skip}, limit: {limit}).'''
        logger.debug(message)
        return records
    except SQLAlchemyError as e:
        handle_db_exception(e, 'pagination retrieval')
        raise
    except Exception as e:
        handle_db_exception(e, 'pagination retrieval')
        raise
