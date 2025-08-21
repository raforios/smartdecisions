'''
    Localization Controllers
'''
from datetime import datetime
from typing import List, Optional
from fastapi import Depends, Path, Query
from sqlalchemy.orm import Session
from services.crud import get_record
from services.db_connection import GET_DB_DEPENDENCY
from services.exceptions import (
    RegisterNotFoundError,
    RegisterAlreadyExistsError,
    InvalidInputError
)
from services.logger_config import custom_logger as logger
from services.localization import (
    add_planned_point,
    create_planned_route_with_points,
    delete_planned_point,
    delete_planned_route,
    get_full_route_comparison,
    get_route_comparisons,
    get_statistics_user_points,
    register_attendance,
    update_attendance_checkout_time,
    update_executed_route_end_time,
    update_planned_route_status,
    create_executed_route,
    register_executed_point,
    get_all_planned_routes,
    filter_planned_routes
)
from models.localization import PlannedPoint, PlannedRoute
from schemas.localization import (
    AttendanceUpdateSchema,
    ExecutedRouteUpdateSchema,
    MessageSchema,
    PlannedPointCreateSchema,
    PlannedRouteCreateSchema,
    PlannedRouteListResponseSchema,
    PlannedRouteResponseSchema,
    ExecutedRouteCreateSchema,
    ExecutedRouteResponseSchema,
    ExecutedPointCreateSchema,
    ExecutedPointResponseSchema,
    AttendanceCreateSchema,
    AttendanceResponseSchema,
    PlannedRouteUpdateStatusSchema,
    PointsVisitedResponseSchema,
    RouteComparisonFullResponseSchema,
    RouteComparisonsResponseSchema
)

def create_planned_route_controller(
    route_data: PlannedRouteCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedRouteResponseSchema:
    '''
        Controller to create a new planned route with all its points.
    '''
    message = f'Attempting to create a new planned route for company: {route_data.company_id}'
    logger.info(message)
    try:
        new_route = create_planned_route_with_points(db, route_data)
        return PlannedRouteResponseSchema.model_validate(new_route)
    except RegisterAlreadyExistsError as e:
        raise e
    except Exception as e:
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
        route = get_record(db, PlannedRoute, planned_route_id, eager_load_options = ['points'])
        return PlannedRouteResponseSchema.model_validate(route)
    except RegisterNotFoundError as e:
        message = f'Planned route {planned_route_id} not found.'
        logger.warning(message)
        raise e
    except Exception as e:
        error_msg = f'Failed to fetch planned route {planned_route_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def get_all_planned_routes_controller(
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> List[PlannedRouteListResponseSchema]:
    '''
        Controller to get all planned routes with their details.
    '''
    message = 'Fetching all planned routes.'
    logger.info(message)
    try:
        routes = get_all_planned_routes(db)
        return [PlannedRouteListResponseSchema.model_validate(route) for route in routes]
    except Exception as e:
        error_msg = f'Failed to fetch all planned routes: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def filter_planned_routes_controller(
    db: Session = Depends(GET_DB_DEPENDENCY),
    route_code: Optional[str] = None,
    route_name: Optional[str] = None,
    status: Optional[str] = None,
    company_id: Optional[int] = None
) -> List[PlannedRouteListResponseSchema]:
    '''
        Controller to filter planned routes by various parameters.
    '''
    message = f'''Filtering planned routes with parameters: route_code = {route_code},
            route_name = {route_name}, status = {status}, user_id = {company_id}'''
    logger.info(message)
    try:
        routes = filter_planned_routes(db, route_code, route_name, status, company_id)
        return [PlannedRouteListResponseSchema.model_validate(route) for route in routes]
    except Exception as e:
        error_msg = f'Failed to filter planned routes: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def update_planned_route_status_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    status_data: PlannedRouteUpdateStatusSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedRouteResponseSchema:
    '''
        Controller to update the status of a planned route.
    '''
    message = f'''Attempting to update status for planned route {planned_route_id}
            to {status_data.status}.'''
    logger.info(message)
    try:
        updated_route = update_planned_route_status(db, planned_route_id, status_data)
        return PlannedRouteResponseSchema.model_validate(updated_route)
    except (RegisterNotFoundError, InvalidInputError) as e:
        raise e
    except Exception as e:
        error_msg = f'Failed to update status for planned route {planned_route_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def delete_planned_route_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route to delete.'),
    db: Session = Depends(GET_DB_DEPENDENCY)
):
    '''
        Controller to delete a planned route.
    '''
    message = f'Attempting to delete planned route with ID: {planned_route_id}.'
    logger.info(message)
    try:
        delete_planned_route(db, planned_route_id)
        return MessageSchema(
            message = f'Planned route {planned_route_id} deleted successfully.'
        )
    except RegisterNotFoundError as e:
        raise e
    except Exception as e:
        error_msg = f'Failed to delete planned route {planned_route_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def add_planned_point_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    point_data: PlannedPointCreateSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedPoint:
    '''
        Controller to add a point to a planned route.
    '''
    message = f'Attempting to add point to planned route {planned_route_id}.'
    logger.info(message)
    try:
        new_point = add_planned_point(db, planned_route_id, point_data)
        return new_point
    except RegisterNotFoundError as e:
        raise e
    except Exception as e:
        error_msg = f'Failed to add point to planned route {planned_route_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def delete_planned_point_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    planned_point_id: int = Path(..., description = 'ID of the planned point to delete.'),
    db: Session = Depends(GET_DB_DEPENDENCY)
):
    '''
        Controller to delete a point from a planned route.
    '''
    message = f'''Attempting to delete point {planned_point_id}
            from planned route {planned_route_id}.'''
    logger.info(message)
    try:
        delete_planned_point(db, planned_route_id, planned_point_id)
        return MessageSchema(
            message = f'Planned point {planned_point_id} deleted successfully.'
        )
    except RegisterNotFoundError as e:
        raise e
    except Exception as e:
        error_msg = f'Failed to delete point {planned_point_id}: {e}'
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
        new_route = create_executed_route(db, route_data)
        return ExecutedRouteResponseSchema.model_validate(new_route)
    except RegisterAlreadyExistsError as e:
        raise e
    except Exception as e:
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
        new_point = register_executed_point(db, point_data)
        return ExecutedPointResponseSchema.model_validate(new_point)
    except RegisterNotFoundError as e:
        raise e
    except Exception as e:
        error_msg = f'Failed to register executed point: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def update_executed_route_end_time_controller(
    executed_route_id: int,
    update_data: ExecutedRouteUpdateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> ExecutedRouteResponseSchema:
    '''
        Controller to update the end_time for an executed route.
    '''
    message = f'Attempting to update end_time for executed route ID: {executed_route_id}'
    logger.info(message)
    try:
        updated_route = update_executed_route_end_time(db, executed_route_id, update_data)
        return ExecutedRouteResponseSchema.model_validate(updated_route)
    except RegisterNotFoundError as e:
        raise e
    except Exception as e:
        error_msg = f'Failed to update end_time for executed route {executed_route_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def update_attendance_checkout_time_controller(
    attendance_id: int = Path(..., description = 'ID of the attendance record to update.'),
    update_data: AttendanceUpdateSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> AttendanceResponseSchema:
    '''
        Controller to update the check-out time of an attendance record.
    '''
    message = f'Attempting to update check-out time for attendance ID: {attendance_id}'
    logger.info(message)
    try:
        updated_attendance = update_attendance_checkout_time(db, attendance_id, update_data)
        return AttendanceResponseSchema.model_validate(updated_attendance)
    except RegisterNotFoundError as e:
        raise e
    except Exception as e:
        error_msg = f'Failed to update check-out time for attendance {attendance_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def get_stats_points_visited_controller(
    user_id: int = Path(..., description = 'ID of the user.'),
    start_date: datetime = Query(
        ...,
        description = 'Start date and time (ISO 8601 format, e.g., "2024-01-01T00:00:00").'
    ),
    end_date: datetime = Query(
        ...,
        description = 'End date and time (ISO 8601 format, e.g., "2024-01-31T23:59:59").'
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
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
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
        raise e
    except Exception as e:
        error_msg = f'Failed to register attendance: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

def get_full_route_comparison_controller(
    planned_route_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> RouteComparisonFullResponseSchema:
    '''
        Controller to get a complete comparison between a planned and executed routes.
    '''
    message = f'Fetching full route comparison for planned route ID: {planned_route_id}'
    logger.info(message)
    try:
        comparison_data = get_full_route_comparison(db, planned_route_id)
        return comparison_data
    except Exception as e:
        error_msg = f'Failed to get full route comparison for route {planned_route_id}: {e}'
        logger.error(error_msg, exc_info=True)
        raise e
