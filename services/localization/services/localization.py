'''
    Localization Service
'''
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from services.exceptions import (
    RegisterNotFoundError,
    RegisterAlreadyExistsError,
    InvalidInputError
)
from services.logger_config import custom_logger as logger
from services.crud import (
    create_record,
    get_record,
    update_record,
    delete_record
)
from services.utils import handle_service_errors
from models.localization import (
    PlannedRoute,
    PlannedPoint,
    Attendance,
    ExecutedRoute,
    ExecutedPoint
)
from schemas.localization import (
    AttendanceCreateSchema,
    ExecutedRouteComparisonSchema,
    PlannedRouteComparisonSchema,
    PlannedRouteCreateSchema,
    PlannedRouteStatusEnum,
    PlannedRouteUpdateStatusSchema,
    AttendanceUpdateSchema,
    ExecutedRouteUpdateSchema,
    ExecutedRouteCreateSchema,
    ExecutedPointCreateSchema,
    PlannedPointCreateSchema,
    RouteComparisonFullResponseSchema
)

@handle_service_errors
def create_planned_route_with_points(
    db: Session,
    route_data: PlannedRouteCreateSchema
) -> PlannedRoute:
    '''
        Creates a new planned route along with its associated planned points.

        Args:
            db (Session): The database session.
            route_data (PlannedRouteCreateSchema): Pydantic schema
                with route and point data.

        Returns:
            PlannedRoute: The newly created planned route record.
    '''
    existing_route = db.query(PlannedRoute).filter(
        PlannedRoute.route_code == route_data.route_code
    ).first()
    if existing_route:
        raise RegisterAlreadyExistsError(
            detail = f'Route with code "{route_data.route_code}" already exists.'
        )

    message = f'Creating planned route with code: {route_data.route_code}'
    logger.debug(message)
    planned_route_data = route_data.model_dump(
        # exclude = {'points', 'user_id'}
        exclude = {'points'}
    )
    # planned_route_data['user_id'] = route_data.user_id # Ensure user_id is included
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

@handle_service_errors
def get_all_planned_routes(
    db: Session
) -> List[PlannedRoute]:
    '''
        Retrieves all planned routes from the database.
    '''
    message = 'Fetching all planned routes.'
    logger.debug(message)
    return db.query(PlannedRoute).all()

@handle_service_errors
def filter_planned_routes(
    db: Session,
    route_code: Optional[str] = None,
    route_name: Optional[str] = None,
    status: Optional[str] = None,
    company_id: Optional[int] = None
) -> List[PlannedRoute]:
    '''
        Filters planned routes based on various optional parameters.
    '''
    message = 'Filtering planned routes.'
    logger.debug(message)

    query = db.query(PlannedRoute)

    if company_id:
        query = query.filter(PlannedRoute.company_id == company_id)
    if route_code:
        query = query.filter(PlannedRoute.route_code == route_code)
    if status:
        query = query.filter(PlannedRoute.status == status)
    if route_name:
        query = query.filter(PlannedRoute.route_name.ilike(f'%{route_name}%'))

    return query.all()

@handle_service_errors
def create_executed_route(
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
                detail = f'''Cannot start a route. Planned route with ID {planned_route.id}
                        is not in ACTIVE status.'''
            )

    new_route = create_record(db, ExecutedRoute, route_data)
    db.commit()
    db.refresh(new_route)

    message = f'Executed route {new_route.id} created successfully.'
    logger.info(message)
    return new_route

@handle_service_errors
def register_executed_point(
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

    # executed_route.end_time = datetime.now()
    db.add(executed_route)

    db.commit()
    db.refresh(new_point)
    message = f'Executed point {new_point.id} registered successfully.'
    logger.info(message)
    return new_point

@handle_service_errors
def update_planned_route_status(
    db: Session,
    planned_route_id: int,
    status_data: PlannedRouteUpdateStatusSchema
) -> PlannedRoute:
    '''
        Updates the status of a planned route.
    '''
    message = f'Updating status for route {planned_route_id} to {status_data.status}'
    logger.debug(message)

    db_route = get_record(db, PlannedRoute, planned_route_id)

    # Retrieve the current and new status values for validation
    current_status = db_route.status
    new_status = status_data.status

    # Validate the transition of statuses based on the business logic
    # 1. A route can only transition from IN_CREATION to ACTIVE.
    if (
        current_status == PlannedRouteStatusEnum.IN_CREATION
        and new_status != PlannedRouteStatusEnum.ACTIVE
    ):
        raise InvalidInputError(
            detail = f'''Routes in {PlannedRouteStatusEnum.IN_CREATION} status can only
                    be changed to {PlannedRouteStatusEnum.ACTIVE}.'''
        )

    # 2. A route can transition from ACTIVE to INACTIVE and vice versa.
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
    return updated_route

@handle_service_errors
def delete_planned_route(
    db: Session,
    planned_route_id: int
):
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

    delete_record(db, PlannedRoute, planned_route_id)
    db.commit()
    message = f'Planned route {planned_route_id} and its points deleted.'
    logger.info(message)

@handle_service_errors
def add_planned_point(
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

    point_data_dict = point_data.model_dump()
    point_data_dict['planned_route_id'] = db_route.id
    new_point = PlannedPoint(**point_data_dict)
    db.add(new_point)
    db.commit()
    db.refresh(new_point)
    message = f'Point {new_point.id} added to planned route {planned_route_id}.'
    logger.info(message)
    return new_point

@handle_service_errors
def delete_planned_point(
    db: Session,
    planned_route_id: int,
    planned_point_id: int
):
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

    db.delete(db_point)
    db.commit()
    message = f'Point {planned_point_id} deleted from planned route {planned_route_id}.'
    logger.info(message)

@handle_service_errors
def update_executed_route_end_time(
    db: Session,
    executed_route_id: int,
    update_data: ExecutedRouteUpdateSchema
) -> ExecutedRoute:
    '''
        Updates the end_time for an executed route.
    '''
    message = f'Updating end_time for executed route {executed_route_id}.'
    logger.debug(message)
    db_record = get_record(db, ExecutedRoute, executed_route_id)
    updated_record = update_record(db, db_record, update_data)
    db.commit()
    db.refresh(updated_record)
    message = f'End time for executed route {executed_route_id} updated.'
    logger.info(message)
    return updated_record

@handle_service_errors
def update_attendance_checkout_time(
    db: Session,
    attendance_id: int,
    update_data: AttendanceUpdateSchema
) -> Attendance:
    '''
        Updates the check-out time of an attendance record.
    '''
    message = f'Updating check-out time for attendance {attendance_id}.'
    logger.debug(message)
    db_record = get_record(db, Attendance, attendance_id)
    updated_record = update_record(db, db_record, update_data)
    db.commit()
    db.refresh(updated_record)
    message = f'Check-out time for attendance {attendance_id} updated.'
    logger.info(message)
    return updated_record

@handle_service_errors
def get_statistics_user_points(
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
    message = f'''User {user_id} visited {total_points_visited} points between
            {start_date} and {end_date}.'''
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

@handle_service_errors
def get_route_comparisons(
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

@handle_service_errors
def register_attendance(
    db: Session,
    attendance_data: AttendanceCreateSchema
) -> Attendance:
    '''
        Registers or updates an attendance record based on user and point.
    '''
    message = f'''Registering attendance for user {attendance_data.user_id}
            at point {attendance_data.planned_point_id}.'''
    logger.debug(message)

    planned_point = get_record(db, PlannedPoint, attendance_data.planned_point_id)

    planned_route = get_record(db, PlannedRoute, planned_point.planned_route_id)

    if planned_route.status != PlannedRouteStatusEnum.ACTIVE:
        raise InvalidInputError(
            detail = f'''Cannot register attendance. The planned route {planned_route.id}
                    is not in ACTIVE status.'''
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
    message = f'''Attendance for user {attendance_data.user_id}
            at point {attendance_data.planned_point_id} created successfully.'''
    logger.info(message)
    return db_attendance

@handle_service_errors
def get_full_route_comparison(
    db: Session,
    planned_route_id: int
) -> RouteComparisonFullResponseSchema:
    '''
        Retrieves a planned route and all its executed routes for comparison.

        Args:
            db (Session): The database session.
            planned_route_id (int): The ID of the planned route to compare.

        Returns:
            RouteComparisonFullResponseSchema: A complete object with all data
                for the comparison.
    '''
    message = f'Getting full comparison data for planned route {planned_route_id}.'
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

    executed_routes = db.query(ExecutedRoute).options(
        joinedload(ExecutedRoute.points)
    ).filter(
        ExecutedRoute.planned_route_id == planned_route_id
    ).all()

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
