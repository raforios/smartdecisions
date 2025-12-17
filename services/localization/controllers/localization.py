'''
    Localization Controllers
'''
from datetime import datetime
import asyncio
import json
import time
from typing import Any, Dict, List, Optional, Set
from fastapi import Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session, joinedload
from services.utils import (
    UsageLogData,
    handle_service_errors,
    send_audit_event,
    send_usage_log
)
from services.crud import get_record
from services.logger_config import custom_logger as logger
from services.localization import (
    add_planned_point,
    create_planned_route_with_points,
    delete_planned_point,
    delete_planned_route,
    get_executed_point_ids_by_planned_routes,
    get_executed_routes_by_planned_route_id_service,
    get_full_route_comparison,
    get_last_known_locations_service,
    get_route_comparisons,
    get_statistics_user_points,
    register_attendance,
    search_attendances_service,
    update_attendance_checkout_time,
    update_executed_route_end_time,
    update_planned_point,
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
    AttendanceSearchItemSchema,
    AttendanceSearchRequestSchema,
    AttendanceUpdateSchema,
    ExecutedRouteUpdateSchema,
    GroupLastKnownLocationsResponseSchema,
    LastKnownLocationResponseSchema,
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
    AttendanceCreateSchema,
    AttendanceResponseSchema,
    PlannedRouteUpdateSchema,
    PlannedRouteUpdateStatusSchema,
    PointsVisitedResponseSchema,
    RouteComparisonFullResponseSchema,
    RouteComparisonsResponseSchema
)

@handle_service_errors('LOCALIZATION')
async def create_planned_route_controller(
    db: Session,
    route_data: PlannedRouteCreateSchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Controller to create a new planned route with all its points.
    '''
    message = 'Starting controller operation: create a new planned route'
    logger.info(message)
    result = await create_planned_route_with_points(db = db, route_data = route_data)
    return PlannedRouteResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
async def get_planned_route_controller(
    db: Session,
    planned_route_id: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Controller to get details of a planned route by its ID.
    '''
    message = f'Starting controller operation: fetch planned route with ID {planned_route_id}'
    logger.info(message)

    eager_options = [
        joinedload(PlannedRoute.points)
    ]

    result = get_record(
        db = db,
        model = PlannedRoute,
        record_id = planned_route_id,
        eager_load_options = eager_options
    )
    return PlannedRouteResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
async def get_all_planned_routes_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> List[PlannedRouteListResponseSchema]:
    '''
        Controller to get all planned routes with their details.
    '''
    message = 'Starting controller operation: fetch all planned routes'
    logger.info(message)
    routes = await get_all_planned_routes(db = db)
    return [PlannedRouteListResponseSchema.model_validate(route) for route in routes]


@handle_service_errors('LOCALIZATION')
async def filter_planned_routes_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    filters: PlannedRouteFilterRequestSchema
) -> List[PlannedRouteListResponseSchema]:
    '''
        Controller to filter planned routes by various parameters.
    '''
    message = 'Starting controller operation: filter planned routes'
    logger.info(message)
    routes = await filter_planned_routes(db = db, filter_params = filters)
    return [PlannedRouteListResponseSchema.model_validate(route) for route in routes]


@handle_service_errors('LOCALIZATION')
async def update_planned_route_status_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    status_data: PlannedRouteUpdateStatusSchema = Depends()
) -> PlannedRouteResponseSchema:
    '''
        Controller to update the status of a planned route.
    '''
    message = f'Starting controller operation: update planned route status for ID {
        planned_route_id}'
    logger.info(message)

    result = await update_planned_route_status(
        db = db,
        planned_route_id = planned_route_id,
        status_data=status_data
    )

    return PlannedRouteResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
async def update_planned_route_controller(
    db: Session,
    planned_route_id: int,
    route_data: PlannedRouteUpdateSchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Controller to update specific fields of a planned route.
    '''
    message = f'Starting controller operation: update planned route with ID {planned_route_id}'
    logger.info(message)
    result = await update_planned_route_service(
        db = db,
        planned_route_id = planned_route_id,
        route_data = route_data
    )

    return PlannedRouteResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
async def delete_planned_route_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    planned_route_id: int = Path(..., description = 'ID of the planned route to delete.')
) -> dict:
    '''
        Controller to delete a planned route.
    '''
    message = f'Starting controller operation: delete planned route with ID {planned_route_id}'
    logger.info(message)

    result = await delete_planned_route(
        db = db,
        planned_route_id = planned_route_id
    )

    return {
        'message': f'Planned route {planned_route_id} deleted successfully.',
        'id': result
    }


@handle_service_errors('LOCALIZATION')
async def add_planned_point_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    point_data: PlannedPointCreateSchema = Depends()
) -> PlannedPointResponseSchema:
    '''
        Controller to add a point to a planned route.
    '''
    message = f'Starting controller operation: add a new planned point to route {planned_route_id}'
    logger.info(message)
    result = await add_planned_point(
        db = db,
        planned_route_id = planned_route_id,
        point_data = point_data
    )
    return PlannedPointResponseSchema.model_validate(result, from_attributes = True)


# pylint: disable=too-many-arguments, too-many-positional-arguments
@handle_service_errors('LOCALIZATION')
async def update_planned_point_controller(
    db: Session,
    planned_route_id: int,
    planned_point_id: int,
    point_data: PlannedPointUpdateSchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PlannedPointResponseSchema:
    '''
        Controller to update a scheduled point.
    '''
    message = f'Starting controller operation: Update planned point {planned_point_id
            } on route {planned_route_id}'
    logger.info(message)
    result = await update_planned_point(
        db = db,
        planned_route_id = planned_route_id,
        planned_point_id = planned_point_id,
        point_data = point_data
    )

    return PlannedPointResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
async def delete_planned_point_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    planned_point_id: int = Path(..., description = 'ID of the planned point to delete.')
) -> dict:
    '''
        Controller to delete a point from a planned route.
    '''
    message = f'Starting controller operation: delete planned point {planned_point_id
            } from route {planned_route_id}'
    logger.info(message)
    result = await delete_planned_point(
        db = db,
        planned_route_id = planned_route_id,
        planned_point_id = planned_point_id
    )

    return {
        'message': f'Planning with ID {result} deleted successfully.',
        'id': result
    }


@handle_service_errors('LOCALIZATION')
async def create_executed_route_controller(
    db: Session,
    route_data: ExecutedRouteCreateSchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ExecutedRouteResponseSchema:
    '''
        Controller to create a new executed route instance.
    '''
    message = f'Starting controller operation: create a new executed route for user {
            route_data.user_id}'
    logger.info(message)

    result = await create_executed_route(db = db, route_data = route_data)
    return ExecutedRouteResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
async def register_executed_point_controller(
    db: Session,
    point_data: ExecutedPointCreateSchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ExecutedPointResponseSchema:
    '''
        Controller to register a new executed point for a specific executed route.
    '''
    message = f'Starting controller operation: register a new executed point for route {
            point_data.executed_route_id}'
    logger.info(message)
    result = await register_executed_point(db = db, point_data = point_data)
    return ExecutedPointResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
async def update_executed_route_end_time_controller(
    db: Session,
    executed_route_id: int,
    update_data: ExecutedRouteUpdateSchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ExecutedRouteResponseSchema:
    '''
        Controller to update the end_time for an executed route.
    '''
    message = f'Starting controller operation: update executed route end time for ID {
        executed_route_id}'
    logger.info(message)
    result = await update_executed_route_end_time(
        db = db,
        executed_route_id = executed_route_id,
        update_data = update_data
    )

    return ExecutedRouteResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
async def update_attendance_checkout_time_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    attendance_id: int = Path(..., description = 'ID of the attendance record to update.'),
    update_data: AttendanceUpdateSchema = Depends()
) -> AttendanceResponseSchema:
    '''
        Controller to update the check-out time of an attendance record.
    '''
    message = f'Starting controller operation: update attendance check-out time for ID {
        attendance_id}'
    logger.info(message)

    result = await update_attendance_checkout_time(
        db = db,
        attendance_id=attendance_id,
        update_data = update_data
    )

    return AttendanceResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
async def get_stats_points_visited_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    user_id: int = Path(..., description = 'ID of the user.'),
    start_date: datetime = Query(...,
            description = 'Start date and time (ISO 8601 format, e.g., "2024-01-01T00:00:00").'),
    end_date: datetime = Query(...,
            description = 'End date and time (ISO 8601 format, e.g., "2024-01-31T23:59:59").'),
    service_id: Optional[int] = None
) -> PointsVisitedResponseSchema:
    '''
        Controller to get statistics on points visited by a user within a date range.
    '''
    message = f'Starting controller operation: get user points statistics for user {user_id}'
    logger.info(message)
    result = await get_statistics_user_points(
        db = db,
        user_id = user_id,
        start_date = start_date,
        end_date = end_date,
        service_id = service_id
    )
    return PointsVisitedResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
async def get_route_comparisons_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    planned_route_id: int = Path(..., description = 'ID of the planned route.'),
    service_id: Optional[int] = None
) -> RouteComparisonsResponseSchema:
    '''
        Controller to compare a planned route with its associated executed routes.
    '''
    message = f'Starting controller operation: get route comparisons for planned route {
            planned_route_id}'
    logger.info(message)

    result = await get_route_comparisons(
        db = db,
        planned_route_id = planned_route_id,
        service_id = service_id
    )
    return RouteComparisonsResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
async def register_attendance_controller(
    db: Session,
    attendance_data: AttendanceCreateSchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> AttendanceResponseSchema:
    '''
        Controller to register or update an attendance record.
    '''
    message = f'Starting controller operation: register or update attendance for user {
            attendance_data.user_id}'
    logger.info(message)
    result = await register_attendance(db = db, attendance_data = attendance_data)
    return AttendanceResponseSchema.model_validate(result, from_attributes = True)


@handle_service_errors('LOCALIZATION')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_full_route_comparison_controller(
    db: Session,
    planned_route_id: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    service_id: Optional[int] = None
) -> RouteComparisonFullResponseSchema:
    '''
        Controller to get a complete comparison between a planned and executed routes.
    '''
    message = f'Starting controller operation: get full route comparison for planned route {
            planned_route_id} with optional filters: start_date={start_date}, end_date={end_date}'
    logger.info(message)

    start_dt = None
    end_dt = None

    if start_date:
        # Convierte la fecha de inicio a datetime, asumiendo el inicio del día (00:00:00)
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')

    if end_date:
        # Convierte la fecha de fin a datetime, asumiendo el final del día (23:59:59)
        # Esto asegura que las ejecuciones de ese mismo día sean incluidas
        end_dt = datetime.strptime(end_date, '%Y-%m-%d').replace(hour = 23,
                                                        minute = 59, second = 59)

    result = await get_full_route_comparison(
        db = db,
        planned_route_id = planned_route_id,
        start_dt = start_dt,
        end_dt = end_dt,
        service_id = service_id
    )
    return RouteComparisonFullResponseSchema.model_validate(result, from_attributes = True)

# pylint: disable=too-many-arguments, too-many-positional-arguments
async def bulk_upload_planned_routes_controller(
    request: Request,
    db: Session,
    file_name: str,
    current_user: str,
    delimiter: Optional[str] = ',',
    auth_token: str = None,
) -> Dict[str, Any]:
    '''
        Controller to handle the bulk upload of planning data from a CSV file.
    '''
    message = f'Starting bulk upload for file: {file_name}'
    logger.info(message)

    start_time = time.perf_counter()
    status_code = 201
    result: Dict[str, Any] = {}

    try:
        result = await bulk_create_planned_routes(
            db = db,
            file_name = file_name,
            delimiter = delimiter,
            auth_token = auth_token
        )

        audit_event_data = {
            'microservice': 'LOCALIZATION',
            'entity_name': 'PlannedRoute',
            'entity_id': 0,
            'action': 'BULK_CREATE',
            'user_id': 'usr_test',
            'old_values': None,
            'new_values': json.dumps(result)
        }
        asyncio.create_task(send_audit_event(audit_event_data))

    except HTTPException as e:
        status_code = e.status_code
        result = {'detail': str(e.detail)}
        raise e

    finally:
        end_time = time.perf_counter()
        log_data = UsageLogData(
            microservice = 'LOCALIZATION',
            endpoint = request.url.path,
            method = request.method,
            status_code = status_code,
            ip_address = request.client.host,
            user_app = current_user,
            request_body = {'file_name': file_name},
            response_body = result,
            response_time_ms = int((end_time - start_time) * 1000)
        )
        asyncio.create_task(send_usage_log(log_data.model_dump()))

    return result

async def get_executed_point_ids_by_planned_routes_controller(
    db: Session,
    planned_route_ids: List[int],
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Set[int]:
    '''
        Controller to retrieve executed point IDs based on planned route IDs.
    '''
    executed_point_ids = await get_executed_point_ids_by_planned_routes(
        db = db,
        planned_route_ids = planned_route_ids
    )

    return executed_point_ids

async def get_executed_routes_by_planned_route_id_controller(
    db: Session,
    planned_route_id: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    service_id: Optional[int] = None
) -> List[ExecutedRouteResponseSchema]:
    '''
        Controller for retrieving executed routes based on a planned route ID.
    '''

    executed_routes = await get_executed_routes_by_planned_route_id_service(
        db = db,
        planned_route_id = planned_route_id,
        service_id = service_id
    )

    return executed_routes

@handle_service_errors('LOCALIZATION')
async def get_last_known_locations_controller(
    db: Session,
    user_ids: List[int],
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    service_id: Optional[int] = None
) -> GroupLastKnownLocationsResponseSchema:
    '''
        Controller for retrieving the last recorded location for a list of users.
    '''
    message = f'Starting controller operation: get last known locations for users {
            user_ids} and service ID: {service_id}'
    logger.info(message)

    locations_data = await get_last_known_locations_service(
        db = db,
        user_ids = user_ids,
        service_id = service_id
    )

    # Mapear los diccionarios a los schemas individuales
    locations = [
        LastKnownLocationResponseSchema(**data) for data in locations_data
    ]

    return GroupLastKnownLocationsResponseSchema(locations = locations)

# --- INTEGRATION CONTROLLERS ---

@handle_service_errors('LOCALIZATION')
async def search_attendances_controller(
    search_data: AttendanceSearchRequestSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> List[AttendanceSearchItemSchema]:
    '''
        Controller to search attendances by a list of IDs.
    '''
    attendances = await search_attendances_service(
        db = db,
        search_data = search_data
    )

    # Pydantic se encarga de mapear planned_point_id -> point_of_sale_id
    # gracias al 'validation_alias' definido en el Schema.
    return [AttendanceSearchItemSchema.model_validate(att, from_attributes=True) \
        for att in attendances]
