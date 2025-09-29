'''
    Business logic services for the Localization Microservice.
'''
import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import desc, func
from services.exceptions import (
    RegisterNotFoundError,
    RegisterAlreadyExistsError,
    InvalidInputError
)
from services.logger_config import custom_logger as logger
from services.crud import (
    create_record, get_record, update_record, delete_record
)
from services.utils import (
    _handle_files_service, audit_event,
    handle_service_errors, perform_bulk_upload,
    sqlalchemy_object_as_dict
)
from models.localization import (
    PlannedRoute, PlannedPoint, Attendance,
    ExecutedRoute, ExecutedPoint
)
from schemas.localization import (
    AttendanceCreateSchema,
    ExecutedRouteComparisonSchema,
    PlannedPointUpdateSchema,
    PlannedRouteBulkCreateSchema,
    PlannedRouteComparisonSchema,
    PlannedRouteCreateSchema,
    PlannedRouteFilterSchema,
    PlannedRouteStatusEnum,
    PlannedRouteUpdateSchema,
    PlannedRouteUpdateStatusSchema,
    AttendanceUpdateSchema,
    ExecutedRouteUpdateSchema,
    ExecutedRouteCreateSchema,
    ExecutedPointCreateSchema,
    PlannedPointCreateSchema,
    RouteComparisonFullResponseSchema
)

# Geofencing Parameters
EARTH_RADIUS_KM = 6371

def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    '''
    Calculates the distance between two coordinates in meters using the Haversine formula.
    '''
    # Convert latitude and longitude from degrees to radians
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    # Haversine formula
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    a = math.sin(delta_lat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * \
        math.sin(delta_lon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distance in kilometers
    distance_km = EARTH_RADIUS_KM * c

    # Return distance in meters
    return distance_km * 1000

def _check_geofence_start_point(
    db: Session,
    planned_route_id: int,
    user_latitude: float,
    user_longitude: float,
    max_distance: float
):
    '''
        Checks if the user's current location is within the geofence of the planned route's
        starting point.
    '''
    # Find the starting point of the planned route (the one with secuencial=1)
    start_point = db.query(PlannedPoint).filter(
        PlannedPoint.planned_route_id == planned_route_id,
        PlannedPoint.secuencial == 1
    ).first()

    if not start_point:
        raise RegisterNotFoundError(
            detail = f'Starting point not found for planned route {planned_route_id}.'
        )

    distance = _calculate_distance(
        user_latitude, user_longitude, start_point.latitude, start_point.longitude
    )

    if distance > max_distance:
        raise InvalidInputError(
            detail = f'Distance: {distance:.2f} meters. Limit: {max_distance:.2f} meters.'
        )

def _process_localization_csv_data(
    rows: List[Dict[str, Any]],
    bulk_schema: PlannedRouteBulkCreateSchema
) -> Dict[str, Any]:
    '''
        Processes raw data from a CSV to group planned routes and their points.
    '''
    routes_data = {}
    for row in rows:
        try:
            row_data = bulk_schema(**row)
            route_key = (
                row_data.route_code,
                row_data.company_id
            )
            if route_key not in routes_data:
                routes_data[route_key] = {
                    'route_data': row_data.model_dump(
                        exclude = {
                            'point_name',
                            'secuencial',
                            'latitude',
                            'longitude',
                            'reference_data'
                        }),
                    'points_data': []
                }
            routes_data[route_key]['points_data'].append(
                row_data.model_dump(
                    exclude = {
                        'company_id',
                        'app_id',
                        'city_id',
                        'route_code',
                        'route_name'
                    })
            )
        except (ValueError, TypeError) as e:
            raise InvalidInputError(
                detail = f'Invalid data format in row: {row}. Error: {e}'
            ) from e
    return routes_data


async def _perform_atomic_db_insertion_for_localization(
    db: Session,
    routes_to_create: Dict[str, Any],
    file_name: str,
    auth_token: str
) -> Dict[str, int]:
    '''
        Performs atomic database insertion for planned routes and points.
    '''
    routes_created = 0
    points_created = 0
    with db.begin_nested():
        for route_key, data in routes_to_create.items():
            if db.query(PlannedRoute).filter_by(
                route_code = data['route_data']['route_code'],
                company_id = data['route_data']['company_id']
            ).first():
                await _handle_files_service(
                    action = 'delete',
                    file_name = file_name,
                    auth_token = auth_token
                )
                raise RegisterAlreadyExistsError(
                    detail = f'''Planned route with code {route_key[0]
                        } already exists for company ID {route_key[1]}.'''
                )

            planned_route = PlannedRoute(**data['route_data'])
            db.add(planned_route)
            db.flush()
            details = [
                PlannedPoint(planned_route_id = planned_route.id, **detail)
                for detail in data['points_data']
            ]
            db.add_all(details)
            routes_created += 1
            points_created += len(details)

    return {'routes_created': routes_created, 'points_created': points_created}

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'PlannedRoute', 'CREATE')
async def create_planned_route_with_points(
    db: Session,
    route_data: PlannedRouteCreateSchema
) -> PlannedRoute:
    '''
        Creates a new planned route along with its associated planned points.
    '''
    existing_route = db.query(PlannedRoute).filter(
        PlannedRoute.route_code == route_data.route_code
    ).first()
    if existing_route:
        raise RegisterAlreadyExistsError(
            detail = f'Route with code {route_data.route_code} already exists.'
        )

    message = f'Creating planned route with code: {route_data.route_code}'
    logger.debug(message)
    planned_route_data = route_data.model_dump(
        exclude = {'points'}
    )
    db_route = PlannedRoute(**planned_route_data)

    db.add(db_route)
    db.flush()
    db.refresh(db_route)

    points_data = [
        PlannedPoint(**point_data.model_dump(), planned_route_id=db_route.id)
        for point_data in route_data.points
    ]
    db.add_all(points_data)
    db.commit()
    db.refresh(db_route)

    message = f'Planned route {db_route.id} created successfully.'
    logger.info(message)
    return db_route

@handle_service_errors('LOCALIZATION')
async def get_all_planned_routes(
    db: Session
) -> List[PlannedRoute]:
    '''
        Retrieves all planned routes from the database.
    '''
    message = 'Fetching all planned routes.'
    logger.debug(message)
    return db.query(PlannedRoute).all()

@handle_service_errors('LOCALIZATION')
async def filter_planned_routes(
    db: Session,
    filter_params: PlannedRouteFilterSchema
) -> List[PlannedRoute]:
    '''
        Filters planned routes based on various optional parameters using a Pydantic schema.
    '''
    message = 'Filtering planned routes.'
    logger.debug(message)

    query = db.query(PlannedRoute)

    # Priority filters: company_id, city_id, and route_status
    if filter_params.company_id:
        query = query.filter(PlannedRoute.company_id == filter_params.company_id)

    if filter_params.city_id:
        query = query.filter(PlannedRoute.city_id == filter_params.city_id)

    if filter_params.route_status:
        query = query.filter(PlannedRoute.status == filter_params.route_status)

    # Secondary filters: route_code and route_name
    if filter_params.route_code:
        query = query.filter(PlannedRoute.route_code == filter_params.route_code)

    if filter_params.route_name:
        query = query.filter(PlannedRoute.route_name.ilike(f'%{filter_params.route_name}%'))

    return query.all()

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'ExecutedRoute', 'CREATE')
async def create_executed_route(
    db: Session,
    route_data: ExecutedRouteCreateSchema
) -> ExecutedRoute:
    '''
        Creates a new executed route record and saves it to the database.
    '''
    message = f'Creating new executed route for user: {route_data.user_id}'
    logger.debug(message)

    if route_data.planned_route_id:
        planned_route = get_record(db, PlannedRoute, route_data.planned_route_id)
        if planned_route.status != PlannedRouteStatusEnum.ACTIVE:
            raise InvalidInputError(
                detail = f'''Cannot start a route. Planned route with ID {
                    planned_route.id} is not in ACTIVE status.'''
            )
        # Check if the user is at the starting point of the route
        _check_geofence_start_point(
            db,
            planned_route_id = route_data.planned_route_id,
            user_latitude = route_data.start_latitude,
            user_longitude = route_data.start_longitude,
            max_distance = route_data.max_distance_start_point
        )

    new_route = create_record(db, ExecutedRoute, route_data)
    db.commit()
    db.refresh(new_route)

    message = f'Executed route {new_route.id} created successfully.'
    logger.info(message)
    return new_route

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'ExecutedPoint', 'CREATE')
async def register_executed_point(
    db: Session,
    point_data: ExecutedPointCreateSchema
) -> ExecutedPoint:
    '''
        Registers a new executed point and updates the executed route's end time.
    '''
    message = f'Registering executed point for route ID: {point_data.executed_route_id}'
    logger.debug(message)
    executed_route = get_record(db, ExecutedRoute, point_data.executed_route_id)

    new_point = create_record(db, ExecutedPoint, point_data)
    db.add(executed_route)
    db.commit()
    db.refresh(new_point)
    message = f'Executed point {new_point.id} registered successfully.'
    logger.info(message)
    return new_point

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'PlannedRoute', 'UPDATE_STATUS')
async def update_planned_route_status(
    db: Session,
    planned_route_id: int,
    status_data: PlannedRouteUpdateStatusSchema
) -> Tuple[PlannedRoute, Dict]:
    '''
        Updates the status of a planned route.
    '''
    message = f'Updating status for route {planned_route_id} to {status_data.status}'
    logger.debug(message)

    db_route = get_record(db, PlannedRoute, planned_route_id)
    old_values = sqlalchemy_object_as_dict(db_route)

    current_status = db_route.status
    new_status = status_data.status

    if (
        current_status == PlannedRouteStatusEnum.IN_CREATION
        and new_status != PlannedRouteStatusEnum.ACTIVE
    ):
        raise InvalidInputError(
            detail = f'''Routes in {PlannedRouteStatusEnum.IN_CREATION
            } status can only be changed to {PlannedRouteStatusEnum.ACTIVE}.'''
        )

    if (
        current_status == PlannedRouteStatusEnum.ACTIVE
        and new_status not in [PlannedRouteStatusEnum.INACTIVE]
    ) or (
        current_status == PlannedRouteStatusEnum.INACTIVE
        and new_status not in [PlannedRouteStatusEnum.ACTIVE]
    ):
        raise InvalidInputError(
            detail = f'Invalid status transition from {current_status} to {new_status}.'
        )

    updated_route = update_record(db, db_route, status_data)
    db.commit()
    db.refresh(updated_route)
    message = f'Status for planned route {planned_route_id} updated to {status_data.status}.'
    logger.info(message)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(updated_route)
    }

    return updated_route, auditable_data

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'PlannedRoute', 'UPDATE')
async def update_planned_route_service(
    db: Session,
    planned_route_id: int,
    route_data: PlannedRouteUpdateSchema
) -> Tuple[PlannedRoute, Dict]:
    '''
        Service to update specific fields of a planned route.
    '''
    db_planned_route = get_record(db, PlannedRoute, planned_route_id)
    old_values = sqlalchemy_object_as_dict(db_planned_route)
    update_data: Dict[str, Any] = route_data.model_dump(exclude_unset = True)

    if not update_data:
        return db_planned_route, old_values

    for key, value in update_data.items():
        if key != 'points':
            setattr(db_planned_route, key, value)

    if 'points' in update_data:
        db_planned_route.points = update_data['points']
        flag_modified(db_planned_route, 'points')

    db.commit()
    db.refresh(db_planned_route)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_planned_route)
    }

    return db_planned_route, auditable_data

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'PlannedRoute', 'DELETE')
async def delete_planned_route(
    db: Session,
    planned_route_id: int
) -> Tuple[int, Dict]:
    '''
        Deletes a planned route and its associated points.
    '''
    message = f'Deleting planned route with ID: {planned_route_id}'
    logger.debug(message)

    db_route = get_record(db, PlannedRoute, planned_route_id)

    if db_route.status != PlannedRouteStatusEnum.IN_CREATION:
        raise InvalidInputError(
            detail = 'Only routes in "IN CREATION" status can be deleted.'
        )

    old_values = sqlalchemy_object_as_dict(db_route)

    delete_record(db, PlannedRoute, planned_route_id)
    db.commit()
    message = f'Planned route {planned_route_id} and its points deleted.'
    logger.info(message)

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return planned_route_id, auditable_data

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'PlannedPoint', 'CREATE')
async def add_planned_point(
    db: Session,
    planned_route_id: int,
    point_data: PlannedPointCreateSchema
) -> PlannedPoint:
    '''
        Adds a new point to a planned route.
    '''
    message = f'Adding point to planned route {planned_route_id}'
    logger.debug(message)
    db_route = get_record(db, PlannedRoute, planned_route_id)

    if db_route.status != PlannedRouteStatusEnum.IN_CREATION:
        raise InvalidInputError(
            detail = 'Cannot add points to a route that is not in "IN CREATION" status.'
        )

    # Check for sequential number existence
    existing_point = db.query(PlannedPoint).filter(
        PlannedPoint.planned_route_id == planned_route_id,
        PlannedPoint.secuencial == point_data.secuencial
    ).first()
    if existing_point:
        raise RegisterAlreadyExistsError(
            detail = f'Sequential number {point_data.secuencial} already exists for this route.'
        )

    point_data_dict = point_data.model_dump()
    point_data_dict['planned_route_id'] = db_route.id
    new_point = PlannedPoint(**point_data_dict)
    db.add(new_point)
    db.commit()
    db.refresh(new_point)
    message = f'Point {new_point.id} added to planned route {planned_route_id}.'
    logger.info(message)
    return new_point

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'PlannedPoint', 'UPDATE')
async def update_planned_point(
    db: Session,
    planned_route_id: int,
    planned_point_id: int,
    point_data: PlannedPointUpdateSchema
) -> Tuple[PlannedPoint, Dict]:
    '''
        Updates the fields of an existing planned point.
    '''
    message = f'''Updating planned point {planned_point_id} on route {
            planned_route_id}.'''
    logger.debug(message)

    db_route = get_record(db, PlannedRoute, planned_route_id)

    if db_route.status != PlannedRouteStatusEnum.IN_CREATION:
        raise InvalidInputError(
            detail = 'Points cannot be updated on a route that is not in "IN CREATION" status.'
        )

    db_point = db.query(PlannedPoint).filter(
        PlannedPoint.id == planned_point_id,
        PlannedPoint.planned_route_id == planned_route_id
    ).first()

    if not db_point:
        raise RegisterNotFoundError(
            detail = f'Point {planned_point_id} not found on planned route {planned_route_id}.'
        )

    old_values = sqlalchemy_object_as_dict(db_point)

    if point_data.secuencial is not None and point_data.secuencial != db_point.secuencial:
        existing_point_with_seq = db.query(PlannedPoint).filter(
            PlannedPoint.planned_route_id == planned_route_id,
            PlannedPoint.secuencial == point_data.secuencial
        ).first()
        if existing_point_with_seq:
            raise RegisterAlreadyExistsError(
                detail = f'''The sequence number {point_data.secuencial
                } already exists for this route.'''
            )

    updated_point = update_record(db, db_point, point_data)
    db.commit()
    db.refresh(updated_point)
    message = f'Point {planned_point_id} successfully updated.'
    logger.info(message)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(updated_point)
    }

    return updated_point, auditable_data

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'PlannedPoint', 'DELETE')
async def delete_planned_point(
    db: Session,
    planned_route_id: int,
    planned_point_id: int
) -> Tuple[int, Dict]:
    '''
        Deletes a specific planned point from a route.
    '''
    message = f'Deleting point {planned_point_id} from route {planned_route_id}'
    logger.debug(message)
    db_route = get_record(db, PlannedRoute, planned_route_id)

    if db_route.status != PlannedRouteStatusEnum.IN_CREATION:
        raise InvalidInputError(
            detail = 'Cannot delete points from a route that is not in "IN CREATION" status.'
        )

    db_point = db.query(PlannedPoint).filter(
        PlannedPoint.id == planned_point_id,
        PlannedPoint.planned_route_id == planned_route_id
    ).first()

    if not db_point:
        raise RegisterNotFoundError(
            detail = f'Point {planned_point_id} not found in planned route {planned_route_id}.'
        )

    old_values = sqlalchemy_object_as_dict(db_point)

    delete_record(db, PlannedPoint, planned_point_id)
    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return planned_point_id, auditable_data

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'ExecutedRoute', 'UPDATE')
async def update_executed_route_end_time(
    db: Session,
    executed_route_id: int,
    update_data: ExecutedRouteUpdateSchema
) -> Tuple[ExecutedRoute, Dict]:
    '''
        Updates the end_time for an executed route.
    '''
    message = f'Updating end_time for executed route {executed_route_id}.'
    logger.debug(message)

    db_record = get_record(db, ExecutedRoute, executed_route_id)
    old_values = sqlalchemy_object_as_dict(db_record)

    planned_route_id = db_record.planned_route_id
    last_planned_point = db.query(PlannedPoint).filter(
        PlannedPoint.planned_route_id == planned_route_id
    ).order_by(PlannedPoint.secuencial.desc()).first()

    if last_planned_point and update_data.max_distance_end_point is not None:
        distance = _calculate_distance(
            lat1 = last_planned_point.latitude,
            lon1 = last_planned_point.longitude,
            lat2 = update_data.end_latitude,
            lon2 = update_data.end_longitude
        )

        if distance > update_data.max_distance_end_point:
            raise InvalidInputError(
                detail = f'Distance: {distance:.2f} meters. Limit: {
                    update_data.max_distance_end_point:.2f} meters.'
            )

    updated_record = update_record(db, db_record, update_data)
    db.commit()
    db.refresh(updated_record)
    message = f'End time for executed route {executed_route_id} updated.'
    logger.info(message)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(updated_record)
    }

    return updated_record, auditable_data

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'Attendance', 'UPDATE')
async def update_attendance_checkout_time(
    db: Session,
    attendance_id: int,
    update_data: AttendanceUpdateSchema
) -> Tuple[Attendance, Dict]:
    '''
        Updates the check-out time of an attendance record.
    '''
    message = f'Updating check-out time for attendance {attendance_id}.'
    logger.debug(message)
    db_record = get_record(db, Attendance, attendance_id)
    old_values = sqlalchemy_object_as_dict(db_record)
    updated_record = update_record(db, db_record, update_data)
    db.commit()
    db.refresh(updated_record)
    message = f'Check-out time for attendance {attendance_id} updated.'
    logger.info(message)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(updated_record)
    }

    return updated_record, auditable_data

@handle_service_errors('LOCALIZATION')
async def get_statistics_user_points(
    db: Session,
    user_id: int,
    start_date: datetime,
    end_date: datetime
) -> Dict[str, Any]:
    '''
        Retrieves statistics on points visited by a user within a date range.
    '''
    # Get executed points within the date range
    executed_points = (
        db.query(ExecutedPoint)
        .join(ExecutedRoute)
        .filter(ExecutedRoute.user_id == user_id)
        .filter(ExecutedPoint.timestamp.between(start_date, end_date))
        .all()
    )

    # Get attendance points within the date range
    attendance_points = (
        db.query(Attendance)
        .filter(Attendance.user_id == user_id)
        .filter(Attendance.check_in_time.between(start_date, end_date))
        .all()
    )

    # Simple aggregation for now, more complex logic can be added later
    total_points_visited = len(executed_points) + len(attendance_points)
    message = f'''User {user_id} visited {total_points_visited
        } points between {start_date} and {end_date}.'''
    logger.info(message)

    # Compile a list of details for all visited points
    points_details = []
    for p in executed_points:
        points_details.append({
            'id': p.id,
            'type': 'executed_point',
            'timestamp': p.timestamp,
            'latitude': p.latitude,
            'longitude': p.longitude
        })
    for a in attendance_points:
        points_details.append({
            'id': a.id,
            'type': 'attendance',
            'check_in_time': a.check_in_time,
            'check_out_time': a.check_out_time,
            'planned_point_id': a.planned_point_id
        })

    return {
        'user_id': user_id,
        'total_points_visited': total_points_visited,
        'executed_points_count': len(executed_points),
        'attendance_points_count': len(attendance_points),
        'points_details': points_details
    }

@handle_service_errors('LOCALIZATION')
async def get_route_comparisons(
    db: Session,
    planned_route_id: int
) -> Dict[str, Any]:
    '''
        Compares a planned route with its associated executed routes.
    '''
    message = f'Getting comparisons for planned route {planned_route_id}.'
    logger.debug(message)
    planned_route = get_record(
        db, PlannedRoute, planned_route_id, eager_load_options = ['points']
    )
    executed_routes = db.query(ExecutedRoute).filter(
        ExecutedRoute.planned_route_id == planned_route_id
    ).order_by(
        desc(ExecutedRoute.start_time)
    ).all()

    comparisons_list = []
    for er in executed_routes:
        match_percentage = 0.0

        comparisons_list.append({
            'planned_route_id': planned_route.id,
            'planned_route_name': planned_route.route_name,
            'executed_route_id': er.id,
            'match_percentage': match_percentage,
            'points_visited_count': len(er.points)
        })

    return {
        'comparisons': comparisons_list
    }

@handle_service_errors('LOCALIZATION')
@audit_event('LOCALIZATION', 'Attendance', 'CREATE')
async def register_attendance(
    db: Session,
    attendance_data: AttendanceCreateSchema
) -> Attendance:
    '''
        Registers or updates an attendance record based on user and point.
    '''
    message = f'''Registering attendance for user {attendance_data.user_id
        } at point {attendance_data.planned_point_id}.'''
    logger.debug(message)

    planned_point = get_record(db, PlannedPoint, attendance_data.planned_point_id)

    planned_route = get_record(db, PlannedRoute, planned_point.planned_route_id)

    if planned_route.status != PlannedRouteStatusEnum.ACTIVE:
        raise InvalidInputError(
            detail = f'''Cannot register attendance. The planned route {
                planned_route.id} is not in ACTIVE status.'''
        )

    existing_attendance = db.query(Attendance).filter(
        Attendance.planned_point_id == attendance_data.planned_point_id,
        Attendance.user_id == attendance_data.user_id,
        Attendance.check_out_time.is_(None)
    ).first()

    if existing_attendance:
        raise InvalidInputError(
            detail = 'An open attendance record already exists for this point.'
        )

    db_attendance = create_record(db, Attendance, attendance_data)
    db.commit()
    db.refresh(db_attendance)
    message = f'''Attendance for user {attendance_data.user_id} at point {
            attendance_data.planned_point_id} created successfully.'''
    logger.info(message)
    return db_attendance

@handle_service_errors('LOCALIZATION')
async def get_full_route_comparison(
    db: Session,
    planned_route_id: int,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None
) -> RouteComparisonFullResponseSchema:
    '''
        Retrieves a planned route and all its executed routes for comparison,
        optionally filtered by the start_time of the executed route.
    '''
    message = f'Getting full comparison data for planned route {
        planned_route_id}. Filters: start_dt={start_dt}, end_dt={end_dt}.'
    logger.debug(message)

    planned_route = db.query(PlannedRoute).options(
        joinedload(PlannedRoute.points)
    ).filter(
        PlannedRoute.id == planned_route_id
    ).first()

    if not planned_route:
        raise RegisterNotFoundError(
            detail = f'Planned route with ID {planned_route_id} not found.'
        )

    executed_routes_query = db.query(ExecutedRoute).options(
        joinedload(ExecutedRoute.points)
    ).filter(
        ExecutedRoute.planned_route_id == planned_route_id
    )

    # Aplicar el filtro de fecha de inicio (si existe)
    # Filtramos por el start_time, ya que la ruta debe haber iniciado DENTRO del rango.
    if start_dt:
        executed_routes_query = executed_routes_query.filter(
            ExecutedRoute.start_time >= start_dt
        )

    # Aplicar el filtro de fecha de fin (si existe)
    if end_dt:
        # Aquí filtramos las rutas que INICIARON antes o en la fecha de fin.
        # Esto incluye rutas que:
        # 1. Iniciaron y terminaron dentro del rango.
        # 2. Iniciaron dentro del rango y aún están abiertas (end_time is NULL).
        executed_routes_query = executed_routes_query.filter(
            ExecutedRoute.start_time <= end_dt
        )

    executed_routes = executed_routes_query.all()

    planned_route_data = PlannedRouteComparisonSchema.model_validate(
        planned_route,
        from_attributes = True
    )

    executed_routes_data = [
        ExecutedRouteComparisonSchema.model_validate(er, from_attributes = True)
        for er in executed_routes
    ]

    response_data = {
        'planned_route': planned_route_data,
        'executed_routes': executed_routes_data
    }

    message = f'Successfully retrieved comparison data for planned route {planned_route_id}.'
    logger.info(message)

    return RouteComparisonFullResponseSchema(**response_data)

async def bulk_create_planned_routes(
    db: Session,
    file_name: str,
    delimiter: str,
    auth_token: str,
) -> Dict[str, Any]:
    '''
        Service function to handle the bulk upload of planned routes.
        It uses a generic utility to process the file and insert data.
    '''
    logger.info('Starting bulk upload process...')

    result = await perform_bulk_upload(
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        bulk_schema = PlannedRouteBulkCreateSchema,
        processor_func = _process_localization_csv_data,
        inserter_func = _perform_atomic_db_insertion_for_localization,
        delimiter = delimiter
    )

    return result

@handle_service_errors('LOCALIZATION-SERVICE')
async def get_executed_point_ids_by_planned_routes(
    db: Session,
    planned_route_ids: List[int]
) -> Set[int]:
    '''
        Retrieves a set of executed point IDs for a given list of planned route IDs.
    '''
    executed_points = db.query(
        ExecutedPoint.id
    ).join(
        ExecutedRoute, ExecutedPoint.executed_route_id == ExecutedRoute.id
    ).filter(
        ExecutedRoute.planned_route_id.in_(planned_route_ids)
    ).all()

    if not executed_points:
        return set()

    # Extraer los IDs de los objetos de punto y convertirlos a un set.
    return {point_id for point_id, in executed_points}

@handle_service_errors('LOCALIZATION-SERVICE')
async def get_executed_routes_by_planned_route_id_service(
    db: Session,
    planned_route_id: int
) -> List[ExecutedRoute]:
    '''
        Retrieve all executed routes associated with a specific planned route ID.

        Parameters:
        - db: SQLAlchemy database session.
        - planned_route_id: ID of the planned route to filter by.

        Returns:
        - A list of ExecutedRoute model objects.
    '''
    message = f'Attempting to retrieve executed routes for planned_route_id: {planned_route_id}'
    logger.info(message)
    executed_routes = (
        db.query(ExecutedRoute)
        .filter(ExecutedRoute.planned_route_id == planned_route_id)
        .all()
    )
    message = f'Found {len(executed_routes)} executed routes for planned_route_id: {
        planned_route_id}'
    logger.info(message)
    return executed_routes

@handle_service_errors('LOCALIZATION-SERVICE')
async def get_last_known_locations_service(
    db: Session,
    user_ids: List[int]
) -> List[dict]:
    '''
        Retrieves the absolute last recorded ExecutedPoint for a given list of user IDs.

        This query uses a subquery to find the MAX(timestamp) per user within their
        executed routes and then joins back to ExecutedPoint to get the full record.
    '''
    message = f'Fetching last known location for user IDs: {user_ids}'
    logger.info(message)

    # 1. Definir la CTE (Common Table Expression) con la función de ventana
    # Rankea los puntos ejecutados por timestamp descendente, particionado por user_id.
    latest_points_cte = (
        db.query(
            ExecutedRoute.user_id,
            ExecutedPoint.latitude.label('last_latitude'),
            ExecutedPoint.longitude.label('last_longitude'),
            ExecutedPoint.timestamp.label('last_timestamp'),
            # Asigna un rango (1 para el más reciente) dentro de cada user_id
            # pylint: disable=not-callable
            func.rank().over(
                order_by = ExecutedPoint.timestamp.desc(),
                partition_by = ExecutedRoute.user_id
            ).label('rank_number')
        )
        .join(ExecutedRoute, ExecutedRoute.id == ExecutedPoint.executed_route_id)
        .filter(ExecutedRoute.user_id.in_(user_ids))
        .cte('latest_points_cte')
    )

    # 2. Seleccionar solo el registro con rank_number = 1 (el último)
    results = (
        db.query(
            latest_points_cte.c.user_id,
            latest_points_cte.c.last_latitude,
            latest_points_cte.c.last_longitude,
            latest_points_cte.c.last_timestamp
        )
        .filter(latest_points_cte.c.rank_number == 1)
        .all()
    )

    # Mapear a una lista de diccionarios
    locations = [
        {
            'user_id': r[0],
            'last_latitude': float(r[1]),
            'last_longitude': float(r[2]),
            'last_timestamp': r[3]
        }
        for r in results
    ]
    message = f'Retrieved {len(locations)} last known locations.'
    logger.info(message)
    return locations
