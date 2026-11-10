'''
    CRUD service

    Taken from LOCALIZATION and TRADE (Rafael, 10-nov-2026). One change: the
    owner is part of every query (CLAUDE.md §8). A record is looked up by its
    owner and its own key, never by an id alone, so a record of another
    company answers exactly like one that does not exist.

    The functions flush and never commit: the controller commits once, at
    the end of the operation, so a sale and its stock movement are saved
    together or not at all.
'''
from typing import Any

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from core.db_connection import Base
from core.exceptions import RegisterNotFoundError
from core.logger_config import custom_logger as logger


def handle_db_exception(
    e: Exception,
    operation: str,
    entity_id: Any = None
) -> None:
    '''
        Logs a database failure and re-raises it as the error the caller expects.

        Not-found and integrity errors go up as they are: the controller gives
        them their business meaning (a duplicate SKU, a missing note). Any
        other database failure becomes a RuntimeError.

        Args:
            e (Exception): The error raised by the database call.
            operation (str): What was being done, for the log.
            entity_id (Any): Which record, for the log.

        Raises:
            RegisterNotFoundError: When that was the error.
            IntegrityError: When a unique or foreign key constraint failed.
            RuntimeError: For any other failure.
    '''
    entity = entity_id if entity_id is not None else 'entity'
    if isinstance(e, RegisterNotFoundError):
        raise e
    if isinstance(e, IntegrityError):
        error_msg = f'Integrity error during {operation} for {entity}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    if isinstance(e, SQLAlchemyError):
        error_msg = f'SQLAlchemy error during {operation} for {entity}: {e}'
        logger.error(error_msg, exc_info = True)
        raise RuntimeError('A database error occurred during the operation.') from e
    error_msg = f'Unexpected error during {operation} for {entity}: {e}'
    logger.critical(error_msg, exc_info = True)
    raise RuntimeError('An unexpected internal error occurred.') from e


def create_record(
    db: Session,
    model: type[Base],
    create_data: BaseModel,
    extra_fields: dict[str, Any] | None = None,
    exclude_relations: list[str] | None = None
) -> Base:
    '''
        Creates a record from a Pydantic schema.

        Args:
            db (Session): The database session.
            model (type[Base]): The SQLAlchemy model class.
            create_data (BaseModel): The data of the new record.
            extra_fields (dict[str, Any] | None): Fields the schema does not
                carry, such as the owner.
            exclude_relations (list[str] | None): Schema fields that are
                relations, created by the caller.

        Returns:
            Base: The new record, with its database defaults filled in.
    '''
    try:
        data_dict = create_data.model_dump(exclude = set(exclude_relations or []))
        data_dict.update(extra_fields or {})
        db_record = model(**data_dict)
        db.add(db_record)
        db.flush()
        db.refresh(db_record)
        return db_record
    except Exception as e:  # pylint: disable=broad-exception-caught
        handle_db_exception(e, f'creation of {model.__name__}')
        raise


def find_record(
    db: Session,
    model: type[Base],
    owner: str,
    **keys: Any
) -> Base | None:
    '''
        The owner's record with those keys, or None.

        Args:
            db (Session): The database session.
            model (type[Base]): The SQLAlchemy model class.
            owner (str): Whose record it is: always part of the query.
            **keys (Any): The record's own key columns and values.

        Returns:
            Base | None: The record, or None when the owner has none.
    '''
    try:
        return db.query(model).filter_by(owner = owner, **keys).one_or_none()
    except Exception as e:  # pylint: disable=broad-exception-caught
        handle_db_exception(e, f'retrieval of {model.__name__}', keys)
        raise


def get_record(
    db: Session,
    model: type[Base],
    owner: str,
    **keys: Any
) -> Base:
    '''
        The owner's record with those keys.

        Args:
            db (Session): The database session.
            model (type[Base]): The SQLAlchemy model class.
            owner (str): Whose record it is: always part of the query.
            **keys (Any): The record's own key columns and values.

        Returns:
            Base: The record.

        Raises:
            RegisterNotFoundError: When the owner has no such record, which
                is also the answer for another company's record.
    '''
    record = find_record(db, model, owner, **keys)
    if record is None:
        message = f'{model.__name__} {keys} not found.'
        logger.warning(message)
        raise RegisterNotFoundError(detail = message)
    return record


def update_record(
    db: Session,
    db_record: Base,
    update_data: BaseModel,
    exclude_relations: list[str] | None = None
) -> Base:
    '''
        Applies to a record the fields the schema sets.

        Args:
            db (Session): The database session.
            db_record (Base): The record, as read with get_record.
            update_data (BaseModel): The changes; unset fields are left alone.
            exclude_relations (list[str] | None): Schema fields that are relations.

        Returns:
            Base: The updated record.
    '''
    try:
        changes = update_data.model_dump(exclude_unset = True,
                                         exclude = set(exclude_relations or []))
        for key, value in changes.items():
            setattr(db_record, key, value)
        db.add(db_record)
        db.flush()
        return db_record
    except Exception as e:  # pylint: disable=broad-exception-caught
        handle_db_exception(e, f'update of {type(db_record).__name__}')
        raise


def delete_record(
    db: Session,
    model: type[Base],
    owner: str,
    **keys: Any
) -> None:
    '''
        Deletes the owner's record with those keys.

        Args:
            db (Session): The database session.
            model (type[Base]): The SQLAlchemy model class.
            owner (str): Whose record it is.
            **keys (Any): The record's own key columns and values.

        Raises:
            RegisterNotFoundError: When the owner has no such record.
    '''
    record = get_record(db, model, owner, **keys)
    try:
        db.delete(record)
        db.flush()
    except Exception as e:  # pylint: disable=broad-exception-caught
        handle_db_exception(e, f'deletion of {model.__name__}', keys)
        raise


def get_all_records_paginated(
    db: Session,
    model: type[Base],
    owner: str,
    pagination: tuple[int, int],
    order_by: Any = None
) -> list[Base]:
    '''
        A page of the owner's records.

        Args:
            db (Session): The database session.
            model (type[Base]): The SQLAlchemy model class.
            owner (str): Whose records: always part of the query.
            pagination (tuple[int, int]): How many to skip and how many to return.
            order_by (Any): The column or expression that orders the page.

        Returns:
            list[Base]: The records of that page.
    '''
    skip, limit = pagination
    try:
        query = db.query(model).filter_by(owner = owner)
        if order_by is not None:
            query = query.order_by(order_by)
        return query.offset(skip).limit(limit).all()
    except Exception as e:  # pylint: disable=broad-exception-caught
        handle_db_exception(e, f'page of {model.__name__}')
        raise
