'''
    Business logic services for the Planning microservice.
'''
from typing import List
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from services.crud import create_record, get_record, update_record
from services.exceptions import RegisterNotFoundError, InvalidInputError
from services.logger_config import custom_logger as logger

from models.planning import Planning
from schemas.planning import PlanningCreateSchema, PlanningUpdateSchema

def get_plannings_by_week(db: Session, week_number: int) -> List[Planning]:
    '''
        Retrieves all plannings for a specific week number.
    '''
    message = f'Fetching plannings for week number {week_number}.'
    logger.info(message)
    plannings = db.query(Planning).filter(Planning.week_number == week_number).all()
    if not plannings:
        raise RegisterNotFoundError(
            detail=f"No plannings found for week number {week_number}."
        )
    return plannings

def get_plannings_by_date(db: Session, planning_date: date) -> List[Planning]:
    '''
        Retrieves all plannings that are active on a specific date.
    '''
    message = f'Fetching plannings for date {planning_date}.'
    logger.info(message)
    plannings = db.query(Planning).filter(
        Planning.start_date <= planning_date,
        Planning.end_date >= planning_date
    ).all()
    if not plannings:
        raise RegisterNotFoundError(
            detail=f"No plannings found for date {planning_date}."
        )
    return plannings

def create_planning_with_details(
    db: Session, planning_data: PlanningCreateSchema
) -> Planning:
    '''
        Creates a planning record in a transactional block.
    '''
    try:
        if planning_data.start_date > planning_data.end_date:
            raise InvalidInputError(detail='`start_date` cannot be after `end_date`')

        db_planning = create_record(db, Planning, planning_data)

        db.commit()
        db.refresh(db_planning)
        return db_planning
    except (IntegrityError, SQLAlchemyError, InvalidInputError, RegisterNotFoundError) as e:
        db.rollback()
        error_msg = f'Failed to create planning {planning_data.planning_name}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error creating planning: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e

def update_planning_with_details(
    db: Session, planning_id: int, planning_data: PlanningUpdateSchema
) -> Planning:
    '''
        Updates a planning record in a transactional block.
    '''
    try:
        db_planning = get_record(db, Planning, planning_id)

        if planning_data.start_date and planning_data.end_date and \
           planning_data.start_date > planning_data.end_date:
            raise InvalidInputError(detail = '`start_date` cannot be after `end_date`')

        db_planning = update_record(db, db_planning, planning_data)

        db.commit()
        db.refresh(db_planning)
        return db_planning
    except (IntegrityError, SQLAlchemyError, InvalidInputError, RegisterNotFoundError) as e:
        db.rollback()
        error_msg = f'Failed to update planning {planning_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error updating planning: {e}'
        logger.critical(error_msg, exc_info=True)
        raise RuntimeError('An unexpected internal error occurred.') from e
