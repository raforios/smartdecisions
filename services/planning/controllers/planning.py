'''
    Planning controllers.
'''
from typing import List
from datetime import date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from services.logger_config import custom_logger as logger
from services.exceptions import (
    RegisterNotFoundError
)
from services.crud import (
    get_record,
)
from services.planning import (
    get_plannings_by_week,
    get_plannings_by_date,
    create_planning_with_details,
    update_planning_with_details
)
from models.planning import (
    Planning,
    PlanningDetail
)
from schemas.planning import (
    PlanningCreateSchema,
    PlanningUpdateSchema
)

def create_planning_controller(
    planning_data: PlanningCreateSchema,
    db: Session
) -> Planning:
    '''
        Controller to create a new planning.
    '''
    message = f'Received request to create planning: {planning_data.planning_name}'
    logger.info(message)

    return create_planning_with_details(db, planning_data)

def get_planning_by_id_controller(planning_id: int, db: Session) -> Planning:
    '''
        Controller to retrieve a planning by its ID.
    '''
    message = f'Fetching planning with ID: {planning_id}'
    logger.info(message)
    try:
        eager_options = [
            joinedload(Planning.details).joinedload(PlanningDetail.materials)
        ]
        return get_record(db, Planning, planning_id, eager_load_options = eager_options)
    except (RegisterNotFoundError, SQLAlchemyError) as e:
        error_msg = f'Failed to fetch planning {planning_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error retrieving planning {planning_id}: {e}'
        logger.critical(error_msg)
        raise RuntimeError('An unexpected internal error occurred.') from e

def update_planning_controller(
    planning_id: int,
    planning_data: PlanningUpdateSchema,
    db: Session
) -> Planning:
    '''
        Controller to update an existing planning record.
    '''
    message = f'Received request to update planning {planning_id}'
    logger.info(message)

    return update_planning_with_details(db, planning_id, planning_data)

def get_weekly_plannings_controller(week_number: int, db: Session) -> List[Planning]:
    '''
        Controller to get all plannings for a specific week.
    '''
    message = f'Fetching plannings for week: {week_number}'
    logger.info(message)
    try:
        return get_plannings_by_week(db, week_number)
    except (SQLAlchemyError, RegisterNotFoundError) as e:
        error_msg = f'Failed to fetch weekly plannings for week {week_number}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def get_daily_plannings_controller(date_to_filter: date, db: Session) -> List[Planning]:
    '''
        Controller to get all plannings for a specific date.
    '''
    message = f'Fetching plannings for date: {date_to_filter}'
    logger.info(message)
    try:
        return get_plannings_by_date(db, date_to_filter)
    except (SQLAlchemyError, RegisterNotFoundError) as e:
        error_msg = f'Failed to fetch daily plannings for date {date_to_filter}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
