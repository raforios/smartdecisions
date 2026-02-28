'''
    Localization: routes handler
'''
from typing import List, Optional
from fastapi import APIRouter, Body, Depends, Header, Path, Request, status, Query
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
    get_executed_point_ids_by_planned_routes_controller,
    get_executed_routes_by_planned_route_id_controller,
    get_full_route_comparison_controller,
    get_last_known_locations_controller,
    get_planned_route_controller,
    create_executed_route_controller,
    register_executed_point_controller,
    get_stats_points_visited_controller,
    get_route_comparisons_controller,
    update_executed_route_end_time_controller,
    update_planned_point_controller,
    update_planned_route_controller,
    update_planned_route_status_controller,
    bulk_upload_planned_routes_controller
)
from schemas.localization import (
    ExecutedRouteUpdateSchema,
    GroupLastKnownLocationsResponseSchema,
    PlannedPointCreateSchema,
    PlannedPointResponseSchema,
    PlannedPointUpdateSchema,
    PlannedRouteCreateSchema,
    PlannedRouteFilterRequestSchema,
    PlannedRouteListResponseSchema,
    PlannedRouteResponseSchema,
    ExecutedRouteCreateSchema,
    ExecutedRouteResponseSchema,
    ExecutedPointCreateSchema,
    ExecutedPointResponseSchema,
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
async def create_planned_route_endpoint(
    request: Request,
    route_data: PlannedRouteCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new planned route.
    '''
    message = f'User: {current_user}. Received request to create planned route for company: {
            route_data.company_id}'
    logger.info(message)
    return await create_planned_route_controller(
        route_data = route_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/routes/planned',
    response_model = List[PlannedRouteListResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Get all planned routes',
    description = 'Retrieves a list of all planned routes.'
)
async def get_all_planned_routes_endpoint(
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve all planned routes.
    '''
    message = f'User: {current_user}. Received request to get all planned routes.'
    logger.info(message)
    return await get_all_planned_routes_controller(
        db = db,
        request = request,
        current_user = current_user
    )

@router.post(
    '/routes/planned/filter',
    response_model = List[PlannedRouteListResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Filter planned routes',
    description = '''Retrieves a list of planned routes filtered by route_code,
                name, status, or a list of IDs.'''
)
async def get_or_filter_planned_routes_endpoint(
    request: Request,
    filters: PlannedRouteFilterRequestSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> List[PlannedRouteListResponseSchema]:
    '''
        Endpoint to filter planned routes.
    '''
    message = f'User: {current_user
            }. Received request to filter planned routes with parameters: planned_route_ids = {
            filters.planned_route_ids}, route_code = {
            filters.route_code}, route_name = {filters.route_name}, status = {
            filters.route_status}, company_id = {filters.company_id}'
    logger.info(message)
    return await filter_planned_routes_controller(
        db = db,
        filters = filters,
        request = request,
        current_user = current_user
    )

@router.get(
    '/routes/executed-points/filter',
    response_model = List[int],
    status_code = status.HTTP_200_OK,
    summary = 'Filter executed points by planned route IDs',
    description = '''Retrieves a list of executed point IDs associated with a
                given list of planned route IDs.'''
)
async def get_executed_point_ids_by_planned_routes_endpoint(
    request: Request,
    planned_route_ids: List[int] = Query(
        ...,
        description='List of planned route IDs to filter by.'
    ),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> List[int]:
    '''
        Endpoint to get executed point IDs from a list of planned route IDs.
    '''
    message = f'User: {current_user
    }. Received request to get executed points for planned routes: {planned_route_ids}'
    logger.info(message)

    executed_points = await get_executed_point_ids_by_planned_routes_controller(
        db = db,
        planned_route_ids = planned_route_ids,
        request = request,
        current_user = current_user
    )

    return list(executed_points)

@router.get(
    '/routes/executed/last-location',
    response_model = GroupLastKnownLocationsResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get the last known location for multiple users',
    description = '''Retrieves the absolute last recorded location
    (latitude, longitude, and timestamp) for a list of user IDs. Essential for real-time
    tracking dashboards. Now includes an **optional** filter by service ID.'''
)
async def get_last_known_locations_endpoint(
    request: Request,
    user_ids: List[int] = Query(...,
        description = 'List of User IDs to track. Example: user_ids=1&user_ids=5&user_ids=8'),
    service_id: Optional[int] = Query(None,
        description = 'Optional ID of the service to filter locations by.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> GroupLastKnownLocationsResponseSchema:
    '''
        Endpoint to get the last known location for a group of users.
    '''
    message = f'User: {current_user
            }. Received request for last known location for user IDs: {
            user_ids} and service ID: {service_id}.'
    logger.info(message)
    return await get_last_known_locations_controller(
        db = db,
        user_ids = user_ids,
        service_id = service_id,
        request = request,
        current_user = current_user
    )

@router.get(
    '/routes/planned/{planned_route_id}',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get a planned route by ID',
    description = 'Retrieves a single planned route and its points by its unique ID.'
)
async def get_planned_route_endpoint(
    request: Request,
    planned_route_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a specific planned route.
    '''
    message = f'User: {current_user}. Received request to get planned route with ID: {
            planned_route_id}'
    logger.info(message)
    return await get_planned_route_controller(
        db = db,
        planned_route_id = planned_route_id,
        request = request,
        current_user = current_user
    )

@router.patch(
    '/routes/planned/{planned_route_id}/status',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update the status of a planned route',
    description = '''Changes the status of a planned route.
                Valid statuses: "ACTIVE", "INACTIVE", "IN CREATION".'''
)
async def update_planned_route_status_endpoint(
    request: Request,
    planned_route_id: int,
    status_data: PlannedRouteUpdateStatusSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update the status of a planned route.
    '''
    message = f'User: {current_user}. Received request to update status for planned route {
            planned_route_id} to {status_data.status}'
    logger.info(message)
    return await update_planned_route_status_controller(
        db = db,
        planned_route_id = planned_route_id,
        status_data = status_data,
        request = request,
        current_user = current_user
    )

@router.patch(
    '/routes/planned/{planned_route_id}',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update a planned route',
    description = 'Updates specific fields of an existing planned route.'
)
async def update_planned_route_endpoint(
    request: Request,
    planned_route_id: int,
    route_data: PlannedRouteUpdateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update specific fields of a planned route.
    '''
    message = f'User: {current_user}. Received request to update planned route {
            planned_route_id}.'
    logger.info(message)
    return await update_planned_route_controller(
        db = db,
        planned_route_id = planned_route_id,
        route_data = route_data,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/routes/planned/{planned_route_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a planned route',
    description = '''Deletes a planned route and its points. This is only
                allowed if the route is in the "IN CREATION" status.'''
)
async def delete_planned_route_endpoint(
    request: Request,
    planned_route_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a planned route.
    '''
    message = f'User: {current_user}. Received request to delete planned route {
            planned_route_id}.'
    logger.info(message)
    return await delete_planned_route_controller(
        db = db,
        planned_route_id = planned_route_id,
        request = request,
        current_user = current_user
    )

@router.post(
    '/routes/planned/{planned_route_id}/points',
    response_model = PlannedPointResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Add a point to a planned route',
    description = '''Adds a new point to a planned route.
                This is only allowed if the route is in the "IN CREATION" status.'''
)
async def add_planned_point_endpoint(
    request: Request,
    planned_route_id: int,
    point_data: PlannedPointCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to add a point to a planned route.
    '''
    message = f'User: {current_user}. Received request to add a point to planned route {
            planned_route_id}.'
    logger.info(message)
    return await add_planned_point_controller(
        db = db,
        planned_route_id = planned_route_id,
        point_data = point_data,
        request = request,
        current_user = current_user
    )

@router.patch(
    '/routes/planned/{planned_route_id}/points/{planned_point_id}',
    response_model = PlannedPointResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update planned point',
    description = '''Allows updating a specific planned point of a route,
                identified by its planned route ID and point ID.'''
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def update_planned_point_endpoint(
    request: Request,
    planned_route_id: int = Path(..., description = 'The ID of the planned route.'),
    planned_point_id: int = Path(..., description = 'The ID of the planned point to update.'),
    point_data: PlannedPointUpdateSchema = Body(...,
                                        description = 'Data to update the planned point.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update a scheduled point.
    '''
    message = f'User: {current_user}. Received request to update planned point {
            planned_point_id} on route {planned_route_id}.'
    logger.info(message)

    return await update_planned_point_controller(
        db = db,
        planned_route_id = planned_route_id,
        planned_point_id = planned_point_id,
        point_data = point_data,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/routes/planned/{planned_route_id}/points/{planned_point_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a point from a planned route',
    description = '''Deletes a specific point from a planned route.
                This is only allowed if the route is in the "IN CREATION" status.'''
)
async def delete_planned_point_endpoint(
    request: Request,
    planned_route_id: int,
    planned_point_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a point from a planned route.
    '''
    message = f'User: {current_user}. Received request to delete point {
            planned_point_id} from planned route {planned_route_id}.'
    logger.info(message)
    return await delete_planned_point_controller(
        db = db,
        planned_route_id = planned_route_id,
        planned_point_id = planned_point_id,
        request = request,
        current_user = current_user
    )

@router.post(
    '/routes/executed',
    response_model = ExecutedRouteResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new executed route instance',
    description = '''Initializes a new executed route instance for a user, optionally linking
                it to a planned route.'''
)
async def create_executed_route_endpoint(
    request: Request,
    route_data: ExecutedRouteCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create an executed route.
    '''
    message = f'User: {current_user}. Received request to create executed route for user: {
            route_data.user_id}'
    logger.info(message)
    return await create_executed_route_controller(
        db = db,
        route_data = route_data,
        request = request,
        current_user = current_user
    )

@router.post(
    '/routes/executed/points',
    response_model = ExecutedPointResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register a new point for an executed route',
    description = 'Records a new geographical point for a specific executed route instance.'
)
async def register_executed_point_endpoint(
    request: Request,
    point_data: ExecutedPointCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register a point for an executed route.
    '''
    message = f'User: {current_user}. Received request to register executed point for route: {
            point_data.executed_route_id}'
    logger.info(message)
    return await register_executed_point_controller(
        db = db,
        point_data = point_data,
        request = request,
        current_user = current_user
    )

@router.patch(
    '/routes/executed/{executed_route_id}',
    response_model = ExecutedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update end time for an executed route',
    description = '''Updates the end time for a specific executed route instance,
                marking it as finished.'''
)
async def update_executed_route_end_time_endpoint(
    request: Request,
    update_data: ExecutedRouteUpdateSchema,
    executed_route_id: int = Path(..., description = 'ID of the executed route.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update the end time of an executed route.
    '''
    message = f'User: {current_user}. Received request to update end_time for executed route: {
            executed_route_id}'
    logger.info(message)
    return await update_executed_route_end_time_controller(
        db = db,
        executed_route_id = executed_route_id,
        update_data = update_data,
        request = request,
        current_user = current_user
    )

@router.get(
    '/statistics/users/{user_id}/points-visited',
    response_model = PointsVisitedResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get points visited statistics',
    description = '''Retrieves a count of all executed points and attendance records
    for a user within a given date range. Now includes an **optional** filter by service ID.'''
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_stats_points_visited_endpoint(
    request: Request,
    user_id: int,
    start_date: str,
    end_date: str,
    service_id: Optional[int] = Query(None,
        description = 'Optional ID of the service to filter statistics by.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve user point visit statistics.
    '''
    message = f'User: {current_user}. Received request to get stats for user {
        user_id} and service ID: {service_id}.'
    logger.info(message)
    return await get_stats_points_visited_controller(
        db = db,
        user_id = user_id,
        start_date = start_date,
        end_date = end_date,
        service_id = service_id,
        request = request,
        current_user = current_user
    )

@router.get(
    '/routes/executed/by-planned/{planned_route_id}',
    response_model = List[ExecutedRouteResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Retrieve executed routes by planned route ID',
    description = '''Retrieves a list of all executed routes associated with a specific
    planned route ID. This is used by the frontend to determine if the
    route is currently open (end_time is NULL) or closed. Now includes an **optional**
    filter by service ID.'''
)
async def get_executed_routes_by_planned_route_id_endpoint(
    request: Request,
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    service_id: Optional[int] = Query(None,
        description = 'Optional ID of the service to filter executed routes by.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> List[ExecutedRouteResponseSchema]:
    '''
        Endpoint to retrieve executed routes based on a planned route ID.
    '''
    message = f'User: {current_user
    }. Received request to get executed routes for planned route: {
        planned_route_id} and service ID: {service_id}'
    logger.info(message)
    return await get_executed_routes_by_planned_route_id_controller(
        db = db,
        planned_route_id = planned_route_id,
        service_id = service_id,
        request = request,
        current_user = current_user
    )

@router.get(
    '/statistics/route-comparisons/{planned_route_id}',
    response_model = RouteComparisonsResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Compare planned vs. executed routes',
    description = '''Compares a planned route with its associated executed routes to
    get statistical data. Now includes an **optional** filter by service ID.'''
)
async def get_route_comparisons_endpoint(
    request: Request,
    planned_route_id: int,
    service_id: Optional[int] = Query(None,
        description = 'Optional ID of the service to filter executed routes by.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to compare routes.
    '''
    message = f'User: {current_user}. Received request to compare routes for planned route {
            planned_route_id} and service ID: {service_id}.'
    logger.info(message)
    return await get_route_comparisons_controller(
        db = db,
        planned_route_id = planned_route_id,
        service_id = service_id,
        request = request,
        current_user = current_user
    )

@router.get(
    '/routes/comparison/{planned_route_id}',
    response_model = RouteComparisonFullResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get a complete comparison between a planned and executed routes',
    description = '''Retrieves a planned route, its points, and all associated
    executed routes and their points for detailed comparison.
    Now includes an **optional** date range filter (start_date, end_date)
    and **service ID** filter.'''
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_full_route_comparison_endpoint(
    request: Request,
    planned_route_id: int = Path(...,
        description = 'ID of the planned route to compare.'),
    start_date: Optional[str] = Query(None,
        description = 'Optional start date (YYYY-MM-DD) to filter executed routes by start_time.'),
    end_date: Optional[str] = Query(None,
        description = 'Optional end date (YYYY-MM-DD) to filter executed routes by start_time.'),
    service_id: Optional[int] = Query(None,
        description = 'Optional ID of the service to filter executed routes by.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to get a full comparison of planned vs executed routes.
    '''
    message = f'User: {current_user
            }. Received request for full route comparison for planned route ID: {
            planned_route_id}. Filters: start_date = {start_date}, end_date = {end_date
            }, service_id={service_id}.'
    logger.info(message)

    return await get_full_route_comparison_controller(
        db = db,
        planned_route_id = planned_route_id,
        start_date = start_date,
        end_date = end_date,
        service_id = service_id,
        request = request,
        current_user = current_user
    )

@router.post(
    '/routes/planned/bulk-upload',
    response_model = BulkUploadResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Bulk upload planned routes from a CSV file',
    description = '''Processes a CSV file from the FILES microservice to create planned routes
                 and their associated points in a single, atomic operation.'''
)

# pylint: disable=too-many-arguments, too-many-positional-arguments
async def bulk_upload_planned_routes_endpoint(
    request: Request,
    file_name: str = Query(..., description = 'Name of the CSV file to process.'),
    delimiter: Optional[str] = Query(
        ',', description = 'The delimiter used in the CSV file. Defaults to a comma (,).'
    ),
    db: Session = Depends(GET_DB_DEPENDENCY),
    auth_token: str = Header(..., alias = 'Authorization'),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to trigger a bulk upload of planning data from a CSV file.
    '''
    message = f'User: {current_user}. Received request for bulk upload from file: {file_name}'
    logger.info(message)
    return await bulk_upload_planned_routes_controller(
        db = db,
        file_name = file_name,
        delimiter = delimiter,
        auth_token = auth_token,
        request = request,
        current_user = current_user
    )
