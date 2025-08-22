'''
    Localization Controllers
'''
from datetime import datetime
from typing import List, Optional
from fastapi import Depends, Path, Query
from sqlalchemy.orm import Session
from services.crud import get_record
from services.db_connection import GET_DB_DEPENDENCY
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
    filter_planned_routes
)
from services.utils import handle_controller_call
from models.localization import PlannedPoint, PlannedRoute
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
    RouteComparisonsResponseSchema
)

def create_planned_route_controller(
    route_data: PlannedRouteCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedRouteResponseSchema:
    '''
        Controller to create a new planned route with all its points.
    '''
    return handle_controller_call(
        create_planned_route_with_points,
        'create a new planned route',
        response_model = PlannedRouteResponseSchema,
        db = db,
        route_data = route_data
    )

def get_planned_route_controller(
    planned_route_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedRouteResponseSchema:
    '''
        Controller to get details of a planned route by its ID.
    '''
    return handle_controller_call(
        get_record,
        'fetch planned route by ID',
        response_model = PlannedRouteResponseSchema,
        db = db,
        model = PlannedRoute,
        record_id = planned_route_id,
        eager_load_options = ['points']
    )

def get_all_planned_routes_controller(
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> List[PlannedRouteListResponseSchema]:
    '''
        Controller to get all planned routes with their details.
    '''
    routes = handle_controller_call(
        get_all_planned_routes,
        'fetch all planned routes',
        db = db
    )
    return [PlannedRouteListResponseSchema.model_validate(route) for route in routes]

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
    routes = handle_controller_call(
        filter_planned_routes,
        'filter planned routes',
        db = db,
        route_code = route_code,
        route_name = route_name,
        status = status,
        company_id = company_id
    )
    return [PlannedRouteListResponseSchema.model_validate(route) for route in routes]

def update_planned_route_status_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    status_data: PlannedRouteUpdateStatusSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedRouteResponseSchema:
    '''
        Controller to update the status of a planned route.
    '''
    return handle_controller_call(
        update_planned_route_status,
        'update planned route status',
        response_model = PlannedRouteResponseSchema,
        db = db,
        planned_route_id = planned_route_id,
        status_data = status_data
    )

def update_planned_route_controller(
    planned_route_id: int,
    route_data: PlannedRouteUpdateSchema,
    db: Session
) -> PlannedRouteResponseSchema:
    '''
        Controller to update specific fields of a planned route.
    '''
    return handle_controller_call(
        update_planned_route_service,
        f'update planned route with ID {planned_route_id}',
        response_model = PlannedRouteResponseSchema,
        db = db,
        planned_route_id = planned_route_id,
        route_data = route_data
    )

def delete_planned_route_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route to delete.'),
    db: Session = Depends(GET_DB_DEPENDENCY)
):
    '''
        Controller to delete a planned route.
    '''
    handle_controller_call(
        delete_planned_route,
        'delete a planned route',
        db = db,
        planned_route_id = planned_route_id
    )
    return MessageSchema(message=f'Planned route {planned_route_id} deleted successfully.')

def add_planned_point_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    point_data: PlannedPointCreateSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> PlannedPoint:
    '''
        Controller to add a point to a planned route.
    '''
    return handle_controller_call(
        add_planned_point,
        'add a new planned point',
        response_model = PlannedPointResponseSchema,
        db = db,
        planned_route_id = planned_route_id,
        point_data = point_data
    )

def delete_planned_point_controller(
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    planned_point_id: int = Path(..., description = 'ID of the planned point to delete.'),
    db: Session = Depends(GET_DB_DEPENDENCY)
):
    '''
        Controller to delete a point from a planned route.
    '''
    handle_controller_call(
        delete_planned_point,
        'delete a planned point',
        db = db,
        planned_route_id = planned_route_id,
        planned_point_id = planned_point_id
    )
    return MessageSchema(message=f'Planned point {planned_point_id} deleted successfully.')

def create_executed_route_controller(
    route_data: ExecutedRouteCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> ExecutedRouteResponseSchema:
    '''
        Controller to create a new executed route instance.
    '''
    return handle_controller_call(
        create_executed_route,
        'create a new executed route',
        response_model = ExecutedRouteResponseSchema,
        db = db,
        route_data = route_data
    )

def register_executed_point_controller(
    point_data: ExecutedPointCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> ExecutedPointResponseSchema:
    '''
        Controller to register a new executed point for a specific executed route.
    '''
    return handle_controller_call(
        register_executed_point,
        'register a new executed point',
        response_model = ExecutedPointResponseSchema,
        db = db,
        point_data = point_data
    )

def update_executed_route_end_time_controller(
    executed_route_id: int,
    update_data: ExecutedRouteUpdateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> ExecutedRouteResponseSchema:
    '''
        Controller to update the end_time for an executed route.
    '''
    return handle_controller_call(
        update_executed_route_end_time,
        'update executed route end time',
        response_model = ExecutedRouteResponseSchema,
        db = db,
        executed_route_id = executed_route_id,
        update_data = update_data
    )

def update_attendance_checkout_time_controller(
    attendance_id: int = Path(..., description='ID of the attendance record to update.'),
    update_data: AttendanceUpdateSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> AttendanceResponseSchema:
    '''
        Controller to update the check-out time of an attendance record.
    '''
    return handle_controller_call(
        update_attendance_checkout_time,
        'update attendance check-out time',
        response_model = AttendanceResponseSchema,
        db = db,
        attendance_id = attendance_id,
        update_data = update_data
    )

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
    return handle_controller_call(
        get_statistics_user_points,
        'get user points statistics',
        response_model = PointsVisitedResponseSchema,
        db = db,
        user_id = user_id,
        start_date = start_date,
        end_date = end_date
    )

def get_route_comparisons_controller(
    planned_route_id: int = Path(..., description='ID of the planned route.'),
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> RouteComparisonsResponseSchema:
    '''
        Controller to compare a planned route with its associated executed routes.
    '''
    return handle_controller_call(
        get_route_comparisons,
        'get route comparisons',
        response_model = RouteComparisonsResponseSchema,
        db = db,
        planned_route_id = planned_route_id
    )

def register_attendance_controller(
    attendance_data: AttendanceCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> AttendanceResponseSchema:
    '''
        Controller to register or update an attendance record.
    '''
    return handle_controller_call(
        register_attendance,
        'register or update attendance',
        response_model = AttendanceResponseSchema,
        db = db,
        attendance_data = attendance_data
    )

def get_full_route_comparison_controller(
    planned_route_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY)
) -> RouteComparisonFullResponseSchema:
    '''
        Controller to get a complete comparison between a planned and executed routes.
    '''
    return handle_controller_call(
        get_full_route_comparison,
        'get full route comparison',
        response_model = RouteComparisonFullResponseSchema,
        db = db,
        planned_route_id = planned_route_id
    )
