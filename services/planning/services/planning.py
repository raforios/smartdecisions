'''
    Business logic services for the Planning microservice.
'''
from typing import List
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from services.logger_config import custom_logger as logger
from models.planning import Planning

def get_plannings_by_week(db: Session, week_number: int) -> List[Planning]:
    '''
        Retrieves all planning records for a given week number.

        Args:
            db (Session): The database session.
            week_number (int): The week number to filter by.

        Returns:
            List[Planning]: A list of planning records.
    '''
    try:
        message = f'Fetching plannings for week number: {week_number}'
        logger.info(message)
        return db.query(Planning).filter(Planning.week_number == week_number).all()
    except SQLAlchemyError as e:
        error_msg = (f'Database error while retrieving plannings '
                     f'for week {week_number}: {e}')
        logger.error(error_msg, exc_info = True)
        raise RuntimeError(
            'A database error occurred while retrieving weekly plannings.'
        ) from e

def get_plannings_by_date(db: Session, date_to_filter: date) -> List[Planning]:
    '''
        Retrieves all planning records for a given date.

        Args:
            db (Session): The database session.
            date_to_filter (date): The date to filter by.

        Returns:
            List[Planning]: A list of planning records.
    '''
    try:
        message = f'Fetching plannings for date: {date_to_filter}'
        logger.info(message)
        return db.query(Planning).filter(
            Planning.start_date <= date_to_filter,
            Planning.end_date >= date_to_filter
        ).all()
    except SQLAlchemyError as e:
        error_msg = (f'Database error while retrieving plannings '
                     f'for date {date_to_filter}: {e}')
        logger.error(error_msg, exc_info = True)
        raise RuntimeError(
            'A database error occurred while retrieving daily plannings.'
        ) from e
