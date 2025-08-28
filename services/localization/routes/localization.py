'''
    Localization: routes handler
'''
from typing import Any, List
from fastapi import APIRouter, Depends, Header, Path, status, Query
from sqlalchemy.orm import Session
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.localization import (
    add_planned_point_controller,
    create_planned_route_controller,
    delete_planned_point_controller,
    delete_planned_route_controller,
    filter_planned_routes_controller,
    get_all_planned_routes_controller,
    get_full_route_comparison_controller,
    get_planned_route_controller,
    create_executed_route_controller,
    register_executed_point_controller,
    get_stats_points_visited_controller,
    get_route_comparisons_controller,
    register_attendance_controller,
    update_attendance_checkout_time_controller,
    update_executed_route_end_time_controller,
    update_planned_route_controller,
    update_planned_route_status_controller,
    bulk_upload_planned_routes_controller
)
from schemas.localization import (
    AttendanceUpdateSchema,
    ExecutedRouteUpdateSchema,
    MessageSchema,
    PlannedPointCreateSchema,
    PlannedPointResponseSchema,
    PlannedRouteCreateSchema,
    PlannedRouteFilterSchema,
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

router = APIRouter(prefix = '/v1/localization', tags = ['Localization'])

@router.post(
    '/routes/planned',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new planned route',
    description = 'Creates a new planned route with a list of associated geographical points.'
)
def create_planned_route_endpoint(
    route_data: PlannedRouteCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new planned route.
    '''
    message = f'''User: {current_user}. Received request to create planned route for company:
            {route_data.company_id}'''
    logger.info(message)
    return create_planned_route_controller(route_data, db)

@router.get(
    '/routes/planned',
    response_model = List[PlannedRouteListResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Get all planned routes',
    description = 'Retrieves a list of all planned routes.'
)
def get_all_planned_routes_endpoint(
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve all planned routes.
    '''
    message = f'User: {current_user}. Received request to get all planned routes.'
    logger.info(message)
    return get_all_planned_routes_controller(db)

@router.get(
    '/routes/planned/filter',
    response_model = List[PlannedRouteListResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Filter planned routes',
    description = '''Retrieves a list of planned routes filtered by route_code,
                name, status, or user ID.'''
)
def get_or_filter_planned_routes_endpoint(
    filters: PlannedRouteFilterSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to filter planned routes.
    '''
    message = f'''User: {current_user}. Received request to filter planned routes
            with parameters: route_code = {filters.route_code}, route_name = {filters.route_name},
            status = {filters.route_status}, company_id = {filters.company_id}'''
    logger.info(message)
    return filter_planned_routes_controller(
        db,
        filters.route_code,
        filters.route_name,
        filters.route_status,
        filters.company_id
    )

@router.get(
    '/routes/planned/{planned_route_id}',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get a planned route by ID',
    description = 'Retrieves a single planned route and its points by its unique ID.'
)
def get_planned_route_endpoint(
    planned_route_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a specific planned route.
    '''
    message = f'''User: {current_user}. Received request to get planned
            route with ID: {planned_route_id}'''
    logger.info(message)
    return get_planned_route_controller(planned_route_id, db)

@router.patch(
    '/routes/planned/{planned_route_id}/status',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update the status of a planned route',
    description = '''Changes the status of a planned route.
                Valid statuses: "ACTIVE", "INACTIVE", "IN CREATION".'''
)
def update_planned_route_status_endpoint(
    planned_route_id: int,
    status_data: PlannedRouteUpdateStatusSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update the status of a planned route.
    '''
    message = f'''User: {current_user}. Received request to update status for planned
            route {planned_route_id} to {status_data.status}'''
    logger.info(message)
    return update_planned_route_status_controller(planned_route_id, status_data, db)

@router.patch(
    '/routes/planned/{planned_route_id}',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update a planned route',
    description = 'Updates specific fields of an existing planned route.'
)
def update_planned_route_endpoint(
    planned_route_id: int,
    route_data: PlannedRouteUpdateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> Any:
    '''
        Endpoint to update specific fields of a planned route.
    '''
    message = f'''User: {current_user}. Received request to update planned route
            {planned_route_id}.'''
    logger.info(message)
    return update_planned_route_controller(
        planned_route_id,
        route_data,
        db
    )

@router.delete(
    '/routes/planned/{planned_route_id}',
    response_model = MessageSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Delete a planned route',
    description = '''Deletes a planned route and its points. This is only
                allowed if the route is in the "IN CREATION" status.'''
)
def delete_planned_route_endpoint(
    planned_route_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a planned route.
    '''
    message = f'''User: {current_user}. Received request to delete planned
            route {planned_route_id}.'''
    logger.info(message)
    return delete_planned_route_controller(planned_route_id, db)

@router.post(
    '/routes/planned/{planned_route_id}/points',
    response_model = PlannedPointResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Add a point to a planned route',
    description = '''Adds a new point to a planned route.
                This is only allowed if the route is in the "IN CREATION" status.'''
)
def add_planned_point_endpoint(
    planned_route_id: int,
    point_data: PlannedPointCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to add a point to a planned route.
    '''
    message = f'''User: {current_user}. Received request to add a point to planned
            route {planned_route_id}.'''
    logger.info(message)
    return add_planned_point_controller(planned_route_id, point_data, db)

@router.delete(
    '/routes/planned/{planned_route_id}/points/{planned_point_id}',
    response_model = MessageSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Delete a point from a planned route',
    description = '''Deletes a specific point from a planned route.
                This is only allowed if the route is in the "IN CREATION" status.'''
)
def delete_planned_point_endpoint(
    planned_route_id: int,
    planned_point_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a point from a planned route.
    '''
    message = f'''User: {current_user}. Received request to delete point {planned_point_id}
            from planned route {planned_route_id}.'''
    logger.info(message)
    return delete_planned_point_controller(planned_route_id, planned_point_id, db)

@router.post(
    '/routes/executed',
    response_model = ExecutedRouteResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new executed route instance',
    description = '''Initializes a new executed route instance for a user, optionally linking
                it to a planned route.'''
)
def create_executed_route_endpoint(
    route_data: ExecutedRouteCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create an executed route.
    '''
    message = f'''User: {current_user}. Received request to create executed route
            for user: {route_data.user_id}'''
    logger.info(message)
    return create_executed_route_controller(route_data, db)

@router.post(
    '/routes/executed/points',
    response_model = ExecutedPointResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register a new point for an executed route',
    description = 'Records a new geographical point for a specific executed route instance.'
)
def register_executed_point_endpoint(
    point_data: ExecutedPointCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register a point for an executed route.
    '''
    message = f'''User: {current_user}. Received request to register executed point for route:
            {point_data.executed_route_id}'''
    logger.info(message)
    return register_executed_point_controller(point_data, db)

@router.patch(
    '/routes/executed/{executed_route_id}',
    response_model = ExecutedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update end time for an executed route',
    description = '''Updates the end time for a specific executed route instance,
                marking it as finished.'''
)
def update_executed_route_end_time_endpoint(
    update_data: ExecutedRouteUpdateSchema,
    executed_route_id: int = Path(..., description = 'ID of the executed route.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update the end time of an executed route.
    '''
    message = f'''User: {current_user}. Received request to update end_time for executed route:
            {executed_route_id}'''
    logger.info(message)
    return update_executed_route_end_time_controller(executed_route_id, update_data, db)

@router.get(
    '/statistics/users/{user_id}/points-visited',
    response_model = PointsVisitedResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get points visited statistics',
    description = '''Retrieves a count of all executed points and attendance records
                for a user within a given date range.'''
)
def get_stats_points_visited_endpoint(
    user_id: int,
    start_date: str,
    end_date: str,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve user point visit statistics.
    '''
    message = f'User: {current_user}. Received request to get stats for user {user_id}.'
    logger.info(message)
    return get_stats_points_visited_controller(user_id, start_date, end_date, db)

@router.get(
    '/statistics/route-comparisons/{planned_route_id}',
    response_model = RouteComparisonsResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Compare planned vs. executed routes',
    description = '''Compares a planned route with its associated executed routes to
                get statistical data.'''
)
def get_route_comparisons_endpoint(
    planned_route_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to compare routes.
    '''
    message = f'''User: {current_user}. Received request to compare routes for planned
            route {planned_route_id}.'''
    logger.info(message)
    return get_route_comparisons_controller(planned_route_id, db)

@router.post(
    '/attendances',
    response_model = AttendanceResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register or update attendance',
    description = '''Registers a new attendance (check-in) or updates an existing one
                with a check-out time.'''
)
def register_attendance_endpoint(
    attendance_data: AttendanceCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register or update attendance.
    '''
    message = f'''User: {current_user}. Received request to register attendance for user:
            {attendance_data.user_id}'''
    logger.info(message)
    return register_attendance_controller(attendance_data, db)

@router.patch(
    '/attendances/{attendance_id}',
    response_model = AttendanceResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update check-out time for an attendance record',
    description = '''Updates an existing attendance record with a check-out time.'''
)
def update_attendance_checkout_time_endpoint(
    update_data: AttendanceUpdateSchema,
    attendance_id: int = Path(..., description='ID of the attendance record to update.'),
    current_user: str = Depends(get_current_user),
    db: Session = Depends(GET_DB_DEPENDENCY),
):
    '''
        Endpoint to update the check-out time of an attendance record.
    '''
    message = f'''User: {current_user}. Received request to update check-out time for
            attendance {attendance_id}.'''
    logger.info(message)
    return update_attendance_checkout_time_controller(attendance_id, update_data, db)

@router.get(
    '/routes/comparison/{planned_route_id}',
    response_model = RouteComparisonFullResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get a complete comparison between a planned and executed routes',
    description = '''Retrieves a planned route, its points, and all associated
                executed routes and their points for detailed comparison.
                This is a resource-intensive endpoint, intended for detailed
                visualization on the frontend.'''
)
def get_full_route_comparison_endpoint(
    planned_route_id: int = Path(..., description='ID of the planned route to compare.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to get a full comparison of planned vs executed routes.
    '''
    message = f'''User: {current_user}. Received request for full route comparison
            for planned route ID: {planned_route_id}.'''
    logger.info(message)
    return get_full_route_comparison_controller(planned_route_id, db)

@router.post(
    '/routes/planned/bulk-upload',
    response_model = BulkUploadResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Bulk upload planned routes from a CSV file',
    description = '''Processes a CSV file from the FILES microservice to create planned routes
                 and their associated points in a single, atomic operation.'''
)
async def bulk_upload_planned_routes_endpoint(
    file_name: str = Query(..., description='Name of the CSV file to process.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    auth_token: str = Header(..., alias = 'Authorization'),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to trigger a bulk upload of planned routes from a CSV file.
    '''
    message = f'''User: {current_user}. Received request for bulk upload from file:
            {file_name}'''
    logger.info(message)
    return await bulk_upload_planned_routes_controller(
        file_name = file_name,
        db = db,
        auth_token = auth_token
    )
