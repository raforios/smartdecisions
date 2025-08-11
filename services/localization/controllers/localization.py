'''
    Localization Controllers
'''
from datetime import datetime
from fastapi import Depends, Path, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from services.db_connection import GET_DB_DEPENDENCY
from services.crud import get_record
from services.exceptions import (
    RegisterNotFoundError,
    RegisterAlreadyExistsError,
    InvalidInputError
)
from services.logger_config import custom_logger as logger
from services.localization import (
    create_planned_route_with_points,
    get_route_comparisons,
    get_statistics_user_points,
    register_attendance
)
from models.localization import (
    PlannedRoute,
    ExecutedRoute,
    ExecutedPoint
)
from schemas.localization import (
    PlannedRouteCreateSchema,
    PlannedRouteResponseSchema,
    ExecutedRouteCreateSchema,
    ExecutedRouteResponseSchema,
    ExecutedPointCreateSchema,
    ExecutedPointResponseSchema,
    AttendanceCreateSchema,
    AttendanceResponseSchema,
    PointsVisitedResponseSchema,
    RouteComparisonsResponseSchema
)

def create_planned_route_controller(
    route_data: PlannedRouteCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedRouteResponseSchema:
    '''
        Controller to create a new planned route with all its points.
    '''
    message = f'Attempting to create a new planned route for user: {route_data.user_id}'
    logger.info(message)
    try:
        new_route = create_planned_route_with_points(db, route_data)
        return PlannedRouteResponseSchema.model_validate(new_route)
    except RegisterAlreadyExistsError as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Failed to create planned route: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def get_planned_route_controller(
    planned_route_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedRouteResponseSchema:
    '''
        Controller to get details of a planned route by its ID.
    '''
    message = f'Fetching planned route with ID: {planned_route_id}'
    logger.info(message)
    try:
        # Eager load points to avoid multiple queries
        route = get_record(db, PlannedRoute, planned_route_id, eager_load_options=['points'])
        return PlannedRouteResponseSchema.model_validate(route)
    except RegisterNotFoundError as e:
        message = f'Planned route {planned_route_id} not found.'
        logger.warning(message)
        raise e
    except Exception as e:
        error_msg = f'Failed to fetch planned route {planned_route_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def create_executed_route_controller(
    route_data: ExecutedRouteCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> ExecutedRouteResponseSchema:
    '''
        Controller to create a new executed route instance.
    '''
    message = f'Attempting to create a new executed route for user: {route_data.user_id}'
    logger.info(message)
    try:
        db_record = ExecutedRoute(**route_data.model_dump())
        db.add(db_record)
        db.commit()
        db.refresh(db_record)
        return ExecutedRouteResponseSchema.model_validate(db_record)
    except IntegrityError as e:
        db.rollback()
        error_msg = f'Database integrity error when creating executed route: {e}'
        logger.error(error_msg, exc_info = True)
        raise RegisterAlreadyExistsError(
            detail = 'An error occurred due to a data conflict when creating the executed route.'
        ) from e
    except Exception as e:
        db.rollback()
        error_msg = f'Failed to create executed route: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def register_executed_point_controller(
    point_data: ExecutedPointCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> ExecutedPointResponseSchema:
    '''
        Controller to register a new executed point for a specific executed route.
    '''
    message = f'Registering executed point for executed route ID: {point_data.executed_route_id}'
    logger.info(message)
    try:
        # Verify the executed route exists first
        executed_route = get_record(db, ExecutedRoute, point_data.executed_route_id)

        db_record = ExecutedPoint(**point_data.model_dump())
        db.add(db_record)

        # Update end_time of the executed route
        executed_route.end_time = datetime.now()
        db.add(executed_route)

        db.commit()
        db.refresh(db_record)
        return ExecutedPointResponseSchema.model_validate(db_record)
    except RegisterNotFoundError as e:
        db.rollback()
        message = f'Executed route {point_data.executed_route_id} not found.'
        logger.warning(message)
        raise e
    except IntegrityError as e:
        db.rollback()
        error_msg = f'Database integrity error when registering executed point: {e}'
        logger.error(error_msg, exc_info = True)
        raise InvalidInputError(
            detail='An error occurred due to a data conflict when registering the point.'
        ) from e
    except Exception as e:
        db.rollback()
        error_msg = f'Failed to register executed point: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def get_stats_points_visited_controller(
    user_id: int = Path(..., description='ID of the user.'),
    start_date: datetime = Query(
        ...,
        description='Start date and time (ISO 8601 format, e.g., "2024-01-01T00:00:00").'
    ),
    end_date: datetime = Query(
        ...,
        description='End date and time (ISO 8601 format, e.g., "2024-01-31T23:59:59").'
    ),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PointsVisitedResponseSchema:
    '''
        Controller to get statistics on points visited by a user within a date range.
    '''
    message = f'Fetching points visited stats for user {user_id} from {start_date} to {end_date}.'
    logger.info(message)
    try:
        stats = get_statistics_user_points(db, user_id, start_date, end_date)
        return PointsVisitedResponseSchema(**stats)
    except Exception as e:
        error_msg = f'Failed to get stats for user {user_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def get_route_comparisons_controller(
    planned_route_id: int = Path(..., description='ID of the planned route.'),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> RouteComparisonsResponseSchema:
    '''
        Controller to compare a planned route with its associated executed routes.
    '''
    message = f'Fetching route comparisons for planned route ID: {planned_route_id}'
    logger.info(message)
    try:
        comparison_data = get_route_comparisons(db, planned_route_id)
        return RouteComparisonsResponseSchema(**comparison_data)
    except RegisterNotFoundError as e:
        message = f'Planned route {planned_route_id} not found.'
        logger.warning(message)
        raise e
    except Exception as e:
        error_msg = f'Failed to get route comparisons for route {planned_route_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def register_attendance_controller(
    attendance_data: AttendanceCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> AttendanceResponseSchema:
    '''
        Controller to register or update an attendance record.
    '''
    message = f'''Registering attendance for user {attendance_data.user_id}
            at point {attendance_data.planned_point_id}.'''
    logger.info(message)
    try:
        attendance = register_attendance(db, attendance_data)
        return AttendanceResponseSchema.model_validate(attendance)
    except (RegisterAlreadyExistsError, InvalidInputError) as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Failed to register attendance: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
