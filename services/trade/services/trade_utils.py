'''
    Utility functions for Trade Microservice.
'''
import math
from sqlalchemy.orm import Session
from models.pos import PointOfSale, PointOfSaleStatus
from models.trade import Attendance, TradePlanning
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.logger_config import custom_logger as logger

# Geofencing Parameters
EARTH_RADIUS_KM = 6371

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
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

def validate_geofence(
    user_lat: float,
    user_lon: float,
    pos: PointOfSale,
    action_name: str = 'Check-In'
) -> float:
    '''
        Validates if the user is within the allowed distance from the Point of Sale.
        Returns the calculated distance.
        Raises InvalidInputError if the distance exceeds the limit.
    '''
    distance = calculate_distance(user_lat, user_lon, float(pos.latitude), float(pos.longitude))

    if distance > pos.max_checkin_distance:
        error_msg = (f"Cannot perform {action_name}. Distance from POS is {distance:.2f} meters, "
                     f"exceeding the limit of {pos.max_checkin_distance} meters.")
        logger.warning(error_msg)
        raise InvalidInputError(detail = error_msg)

    return distance

def validate_active_attendance(
    db: Session,
    attendance_id: int,
    company_id: int,
    pos_id: int = None
) -> Attendance:
    '''
        Validates that the attendance is active (no check-out) and belongs to the company.
        Optionally validates that it corresponds to the specific POS.
    '''
    attendance = db.query(Attendance).filter(
        Attendance.id == attendance_id,
        Attendance.company_id == company_id
    ).first()

    if not attendance:
        raise RegisterNotFoundError(detail = f'Attendance record {attendance_id} not found.')

    if attendance.check_out_time:
        raise InvalidInputError(detail = f'Attendance {attendance_id
                            } is already closed (Check-Out performed).')

    planning = db.query(TradePlanning).filter(TradePlanning.id == attendance.trade_planning_id
                                            ).first()

    if pos_id and planning.point_of_sale_id != pos_id:
        raise InvalidInputError(detail = f'Attendance {attendance_id
                            } does not belong to POS {pos_id}.')

    # Also validate POS status through planning
    pos = db.query(PointOfSale).filter(PointOfSale.id == planning.point_of_sale_id).first()
    if pos.status != PointOfSaleStatus.ACTIVE:
        error_msg = f"Point of Sale {pos.code} is not ACTIVE. Current status: {pos.status.value}"
        logger.warning(error_msg)
        raise InvalidInputError(detail = error_msg)

    return attendance
