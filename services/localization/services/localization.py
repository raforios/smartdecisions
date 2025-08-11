'''
    Localization Service
'''
from datetime import datetime
from sqlalchemy.orm import Session
from services.crud import get_record
from services.exceptions import (
    RegisterNotFoundError,
    RegisterAlreadyExistsError,
    InvalidInputError
)
from services.logger_config import custom_logger as logger
from models.localization import (
    PlannedRoute,
    PlannedPoint,
    ExecutedPoint,
    Attendance,
    ExecutedRoute
)
from schemas.localization import (
    PlannedRouteCreateSchema,
    AttendanceCreateSchema
)

def create_planned_route_with_points(
    db: Session,
    route_data: PlannedRouteCreateSchema
) -> PlannedRoute:
    '''
        Creates a planned route and all its associated points in a single transaction.

        Args:
            db (Session): The database session.
            route_data (PlannedRouteCreateSchema): The schema containing route and point data.

        Returns:
            PlannedRoute: The newly created PlannedRoute model instance.
    '''
    try:
        # Create the PlannedRoute record first
        route_dict = route_data.model_dump(exclude={'points'})
        planned_route = PlannedRoute(**route_dict)
        db.add(planned_route)
        db.flush()
        message = f'PlannedRoute created with ID: {planned_route.id}'
        logger.info(message)

        # Iterate through points and create PlannedPoint records
        for point_data in route_data.points:
            point_dict = point_data.model_dump()
            planned_point = PlannedPoint(
                **point_dict, planned_route_id=planned_route.id
            )
            db.add(planned_point)
            db.flush()
            message = f'PlannedPoint created with ID: {planned_point.id}'
            logger.debug(message)

        db.commit()
        db.refresh(planned_route)
        return planned_route
    except Exception as e:
        db.rollback()
        error_msg = f'Error creating planned route with points: {e}'
        logger.error(error_msg, exc_info=True)
        # Assuming unique constraint on route_name is possible
        if 'IntegrityError' in str(e):
            raise RegisterAlreadyExistsError(
                detail = f'''Planned route with name {route_data.route_name}
                        already exists'''
            ) from e
        raise

def get_statistics_user_points(
    db: Session,
    user_id: int,
    start_date: datetime,
    end_date: datetime
) -> dict:
    '''
        Retrieves statistics for points visited by a user.

        Args:
            db (Session): The database session.
            user_id (int): The ID of the user.
            start_date (datetime): The start date for the search.
            end_date (datetime): The end date for the search.

        Returns:
            dict: A dictionary with user statistics, including a list of visited points.
    '''
    try:
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
    except Exception as e:
        error_msg = f'Error getting user points statistics for user {user_id}: {e}'
        logger.error(error_msg, exc_info=True)
        raise

def get_route_comparisons(db: Session, planned_route_id: int) -> dict:
    '''
        Compares a planned route with its associated executed routes.

        Args:
            db (Session): The database session.
            planned_route_id (int): The ID of the planned route to compare.

        Returns:
            dict: A dictionary with comparison data.
    '''
    # Complex logic for geometric comparison would go here.
    # For now, we'll return a placeholder.
    try:
        planned_route = get_record(db, PlannedRoute, planned_route_id)
        executed_routes = (
            db.query(ExecutedRoute)
            .filter(ExecutedRoute.planned_route_id == planned_route_id)
            .all()
        )

        comparisons = []
        for executed_route in executed_routes:
            # Placeholder for comparison logic
            match_percentage = 85.5 # Example value
            points_visited_count = len(executed_route.points)

            comparison_data = {
                'planned_route_id': planned_route.id,
                'planned_route_name': planned_route.route_name,
                'executed_route_id': executed_route.id,
                'match_percentage': match_percentage,
                'points_visited_count': points_visited_count,
            }
            comparisons.append(comparison_data)

        message = f'Generated comparison for planned route ID {planned_route_id} ' \
                  f'with {len(comparisons)} executed routes.'
        logger.info(message)

        return {'comparisons': comparisons}
    except RegisterNotFoundError as e:
        raise e
    except Exception as e:
        error_msg = f'Error getting route comparisons for route {planned_route_id}: {e}'
        logger.error(error_msg, exc_info=True)
        raise


def register_attendance(db: Session, attendance_data: AttendanceCreateSchema) -> Attendance:
    '''
        Registers or updates an attendance record.

        Args:
            db (Session): The database session.
            attendance_data (AttendanceCreateSchema): The schema for the attendance record.

        Returns:
            Attendance: The created or updated attendance record.
    '''
    try:
        # Check if an existing attendance record for a user and point exists
        existing_attendance = (
            db.query(Attendance)
            .filter(Attendance.user_id == attendance_data.user_id)
            .filter(Attendance.planned_point_id == attendance_data.planned_point_id)
            .first()
        )

        if existing_attendance and attendance_data.check_out_time:
            # Update existing record with check-out time
            update_data = {'check_out_time': attendance_data.check_out_time}
            for key, value in update_data.items():
                setattr(existing_attendance, key, value)
            db.flush()
            db.commit()
            message = f'Updated attendance record {existing_attendance.id} with check-out time.'
            logger.info(message)
            return existing_attendance
        if existing_attendance:
            raise InvalidInputError('User already checked in at this point. '
                                    'Provide check_out_time to update.')

        # Create a new record
        new_attendance = Attendance(**attendance_data.model_dump())
        db.add(new_attendance)
        db.commit()
        db.refresh(new_attendance)
        message = f'New attendance record {new_attendance.id} created for user ' \
                  f'{attendance_data.user_id} at point {attendance_data.planned_point_id}.'
        logger.info(message)
        return new_attendance

    except Exception as e:
        db.rollback()
        error_msg = f'Error registering attendance: {e}'
        logger.error(error_msg, exc_info=True)
        raise
