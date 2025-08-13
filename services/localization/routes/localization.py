'''
    API Routes for Localization Microservice
'''
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.localization import (
    create_planned_route_controller,
    get_planned_route_controller,
    create_executed_route_controller,
    register_executed_point_controller,
    get_stats_points_visited_controller,
    get_route_comparisons_controller,
    register_attendance_controller
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
    message = f'''User: {current_user}. Received request to create planned route for user:
            {route_data.user_id}'''
    logger.info(message)
    return create_planned_route_controller(route_data, db)

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
