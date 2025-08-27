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
    InvalidInputError,
    ResourceNotFoundError
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
    update_planned_route_service,
    update_planned_route_status,
    create_executed_route,
    register_executed_point,
    get_all_planned_routes,
    filter_planned_routes,
    bulk_create_planned_routes
)
from models.localization import PlannedRoute
from schemas.localization import (
    AttendanceUpdateSchema,
    ExecutedRouteUpdateSchema,
    MessageSchema,
    PlannedPointCreateSchema,
    PlannedPointResponseSchema,
    PlannedRouteCreateSchema,
    PlannedRouteListResponseSchema,
    PlannedRouteResponseSchema,
    ExecutedRouteCreateSchema,
    ExecutedRouteResponseSchema,
    ExecutedPointCreateSchema,
    ExecutedPointResponseSchema,
    AttendanceCreateSchema,
    AttendanceResponseSchema,
    PlannedRouteUpdateSchema,
    PlannedRouteUpdateStatusSchema,
    PointsVisitedResponseSchema,
    RouteComparisonFullResponseSchema,
    RouteComparisonsResponseSchema,
    BulkUploadResponseSchema
)

def create_planned_route_controller(
    route_data: PlannedRouteCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedRouteResponseSchema:
    '''
        Controller to create a new planned route with all its points.
    '''
    try:
        message = 'Starting controller operation: create a new planned route'
        logger.info(message)
        result = create_planned_route_with_points(db = db, route_data = route_data)
        return PlannedRouteResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterAlreadyExistsError, InvalidInputError) as e:
        error_msg = f'Failed to create a new planned route: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during create a new planned route: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def get_planned_route_controller(
    planned_route_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedRouteResponseSchema:
    '''
        Controller to get details of a planned route by its ID.
    '''
    try:
        message = f'Starting controller operation: fetch planned route with ID {planned_route_id}'
        logger.info(message)
        result = get_record(
            db = db,
            model = PlannedRoute,
            record_id = planned_route_id,
            eager_load_options = ['points']
        )
        return PlannedRouteResponseSchema.model_validate(result, from_attributes = True)
    except RegisterNotFoundError as e:
        error_msg = f'Failed to fetch planned route by ID: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during fetch planned route by ID: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def get_all_planned_routes_controller(
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> List[PlannedRouteListResponseSchema]:
    '''
        Controller to get all planned routes with their details.
    '''
    try:
        message = 'Starting controller operation: fetch all planned routes'
        logger.info(message)
        routes = get_all_planned_routes(db = db)
        return [PlannedRouteListResponseSchema.model_validate(route) for route in routes]
    except Exception as e:
        error_msg = f'Unexpected error during fetch all planned routes: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


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
    try:
        message = 'Starting controller operation: filter planned routes'
        logger.info(message)
        routes = filter_planned_routes(
            db = db,
            route_code = route_code,
            route_name = route_name,
            status = status,
            company_id = company_id
        )
        return [PlannedRouteListResponseSchema.model_validate(route) for route in routes]
    except Exception as e:
        error_msg = f'Unexpected error during filter planned routes: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def update_planned_route_status_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    status_data: PlannedRouteUpdateStatusSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedRouteResponseSchema:
    '''
        Controller to update the status of a planned route.
    '''
    try:
        message = f'''Starting controller operation: update planned route status
                for ID {planned_route_id}'''
        logger.info(message)
        result = update_planned_route_status(
            db = db,
            planned_route_id = planned_route_id,
            status_data = status_data
        )
        return PlannedRouteResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to update planned route status: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during update planned route status: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def update_planned_route_controller(
    planned_route_id: int,
    route_data: PlannedRouteUpdateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedRouteResponseSchema:
    '''
        Controller to update specific fields of a planned route.
    '''
    try:
        message = f'Starting controller operation: update planned route with ID {planned_route_id}'
        logger.info(message)
        result = update_planned_route_service(
            db = db,
            planned_route_id = planned_route_id,
            route_data = route_data
        )
        return PlannedRouteResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to update planned route with ID {planned_route_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during update planned route with ID {planned_route_id}: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def delete_planned_route_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route to delete.'),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> MessageSchema:
    '''
        Controller to delete a planned route.
    '''
    try:
        message = f'Starting controller operation: delete planned route with ID {planned_route_id}'
        logger.info(message)
        delete_planned_route(db = db, planned_route_id = planned_route_id)
        return MessageSchema(message = f'Planned route {planned_route_id} deleted successfully.')
    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to delete a planned route: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during delete a planned route: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def add_planned_point_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    point_data: PlannedPointCreateSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedPointResponseSchema:
    '''
        Controller to add a point to a planned route.
    '''
    try:
        message = f'''Starting controller operation: add a new planned point
                to route {planned_route_id}'''
        logger.info(message)
        result = add_planned_point(
            db = db,
            planned_route_id = planned_route_id,
            point_data = point_data
        )
        return PlannedPointResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterAlreadyExistsError, RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to add a new planned point: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during add a new planned point: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def delete_planned_point_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    planned_point_id: int = Path(..., description = 'ID of the planned point to delete.'),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> MessageSchema:
    '''
        Controller to delete a point from a planned route.
    '''
    try:
        message = f'''Starting controller operation: delete planned point
                {planned_point_id} from route {planned_route_id}'''
        logger.info(message)
        delete_planned_point(
            db = db,
            planned_route_id = planned_route_id,
            planned_point_id = planned_point_id
        )
        return MessageSchema(message = f'Planned point {planned_point_id} deleted successfully.')
    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to delete a planned point: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during delete a planned point: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def create_executed_route_controller(
    route_data: ExecutedRouteCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> ExecutedRouteResponseSchema:
    '''
        Controller to create a new executed route instance.
    '''
    try:
        message = f'''Starting controller operation: create a new executed route
                for user {route_data.user_id}'''
        logger.info(message)
        result = create_executed_route(db = db, route_data = route_data)
        return ExecutedRouteResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterAlreadyExistsError, RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to create a new executed route: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during create a new executed route: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def register_executed_point_controller(
    point_data: ExecutedPointCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> ExecutedPointResponseSchema:
    '''
        Controller to register a new executed point for a specific executed route.
    '''
    try:
        message = f'''Starting controller operation: register a new executed point
                for route {point_data.executed_route_id}'''
        logger.info(message)
        result = register_executed_point(db = db, point_data = point_data)
        return ExecutedPointResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to register a new executed point: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during register a new executed point: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def update_executed_route_end_time_controller(
    executed_route_id: int,
    update_data: ExecutedRouteUpdateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> ExecutedRouteResponseSchema:
    '''
        Controller to update the end_time for an executed route.
    '''
    try:
        message = f'''Starting controller operation: update executed route end time
                for ID {executed_route_id}'''
        logger.info(message)
        result = update_executed_route_end_time(
            db = db,
            executed_route_id = executed_route_id,
            update_data = update_data
        )
        return ExecutedRouteResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to update executed route end time: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during update executed route end time: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def update_attendance_checkout_time_controller(
    attendance_id: int = Path(..., description='ID of the attendance record to update.'),
    update_data: AttendanceUpdateSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> AttendanceResponseSchema:
    '''
        Controller to update the check-out time of an attendance record.
    '''
    try:
        message = f'''Starting controller operation: update attendance check-out time
                for ID {attendance_id}'''
        logger.info(message)
        result = update_attendance_checkout_time(
            db = db,
            attendance_id = attendance_id,
            update_data = update_data
        )
        return AttendanceResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to update attendance check-out time: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during update attendance check-out time: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


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
    try:
        message = f'Starting controller operation: get user points statistics for user {user_id}'
        logger.info(message)
        result = get_statistics_user_points(
            db = db,
            user_id = user_id,
            start_date = start_date,
            end_date = end_date
        )
        return PointsVisitedResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to get user points statistics: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during get user points statistics: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def get_route_comparisons_controller(
    planned_route_id: int = Path(..., description='ID of the planned route.'),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> RouteComparisonsResponseSchema:
    '''
        Controller to compare a planned route with its associated executed routes.
    '''
    try:
        message = f'''Starting controller operation: get route comparisons for
                planned route {planned_route_id}'''
        logger.info(message)
        result = get_route_comparisons(db = db, planned_route_id = planned_route_id)
        return RouteComparisonsResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to get route comparisons: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during get route comparisons: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def register_attendance_controller(
    attendance_data: AttendanceCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> AttendanceResponseSchema:
    '''
        Controller to register or update an attendance record.
    '''
    try:
        message = f'''Starting controller operation: register or update attendance
                for user {attendance_data.user_id}'''
        logger.info(message)
        result = register_attendance(db = db, attendance_data = attendance_data)
        return AttendanceResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to register or update attendance: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during register or update attendance: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


def get_full_route_comparison_controller(
    planned_route_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> RouteComparisonFullResponseSchema:
    '''
        Controller to get a complete comparison between a planned and executed routes.
    '''
    try:
        message = f'''Starting controller operation: get full route comparison
                for planned route {planned_route_id}'''
        logger.info(message)
        result = get_full_route_comparison(db = db, planned_route_id = planned_route_id)
        return RouteComparisonFullResponseSchema.model_validate(result, from_attributes = True)
    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'Failed to get full route comparison: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during get full route comparison: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e


async def bulk_upload_planned_routes_controller(
    auth_token: str,
    file_name: str,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> BulkUploadResponseSchema:
    '''
        Controller to handle the bulk upload of planned routes from a CSV file.
    '''
    try:
        message = f'Starting controller operation: bulk upload from file {file_name}'
        logger.info(message)
        result = await bulk_create_planned_routes(
            db = db,
            file_name = file_name,
            auth_token = auth_token
        )
        return BulkUploadResponseSchema.model_validate(result, from_attributes = True)
    except (
        RegisterAlreadyExistsError,
        RegisterNotFoundError,
        InvalidInputError,
        ResourceNotFoundError
    ) as e:
        error_msg = f'Failed to bulk upload from file {file_name}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error during bulk upload from file {file_name}: {e}'
        logger.critical(error_msg, exc_info = True)
        raise RuntimeError('An unexpected internal error occurred.') from e
