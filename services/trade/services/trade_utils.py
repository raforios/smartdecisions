'''
    Utility functions for Trade Microservice.
'''
import math
from typing import List, Type
from pydantic import BaseModel
from sqlalchemy.orm import Session, DeclarativeBase
from models.pos import PointOfSale, PointOfSaleStatus
from models.trade import Attendance, PlannedPoint
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.products import (
    create_bulk_items_from_skus,
    get_product_id_by_sku,
    validate_product_assigned_to_pos,
)

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
    company_id: int,  # pylint: disable=unused-argument
    pos_id: int = None
) -> Attendance:
    '''
        Validates that the attendance exists, is still open (no check-out)
        and (optionally) matches the POS provided. 2026-05-20 (Binaria):
        the company filter was dropped — the attendance stores the
        EXECUTOR company while the downstream transactions ship the
        CLIENT company, so equality never held. The frontend keeps the
        contracts consistent.
    '''
    attendance = db.query(Attendance).filter(
        Attendance.id == attendance_id
    ).first()

    if not attendance:
        raise RegisterNotFoundError(detail = f'Attendance record {attendance_id} not found.')

    if attendance.check_out_time:
        raise InvalidInputError(detail = f'Attendance {attendance_id
                            } is already closed (Check-Out performed).')

    planned_point = db.query(PlannedPoint).filter(
        PlannedPoint.id == attendance.trade_planned_point_id
    ).first()

    if pos_id and planned_point.point_of_sale_id != pos_id:
        raise InvalidInputError(detail = f'Attendance {attendance_id
                            } does not belong to POS {pos_id}.')

    # Validate POS status through the planned point's POS reference.
    pos = db.query(PointOfSale).filter(PointOfSale.id == planned_point.point_of_sale_id).first()
    if pos.status != PointOfSaleStatus.ACTIVE:
        error_msg = f"Point of Sale {pos.code} is not ACTIVE. Current status: {pos.status.value}"
        logger.warning(error_msg)
        raise InvalidInputError(detail = error_msg)

    return attendance


async def create_visit_items(
    db: Session,
    attendance_id: int,
    payload: BaseModel,
    model_class: Type[DeclarativeBase],
    extra_fields: dict = None
) -> List[DeclarativeBase]:
    '''
        Shared visit-item creation flow used by the inventory / reception
        create services: validates the active attendance, checks each item's
        SKU is assigned to the POS and bulk-creates the rows.

        `payload` must expose company_id, pos_id and items[*].product_sku.
    '''
    validate_active_attendance(
        db = db,
        attendance_id = attendance_id,
        company_id = payload.company_id,
        pos_id = payload.pos_id
    )
    # Binaria 2026-08-03: SKU + POS-assortment ownership live on the CLIENT
    # company side (owner of the products/POS). The executor `company_id` is the
    # fallback for legacy payloads that only ship the executor tenant.
    catalog_company_id = getattr(payload, 'client_company_id', None) or payload.company_id
    for item in payload.items:
        product_id = get_product_id_by_sku(db, catalog_company_id, item.product_sku)
        validate_product_assigned_to_pos(
            db, catalog_company_id, payload.pos_id, product_id
        )
    return await create_bulk_items_from_skus(
        db = db,
        attendance_id = attendance_id,
        company_id = payload.company_id,
        items_list = payload.items,
        model_class = model_class,
        extra_fields = extra_fields
    )


def filter_query_by_attendance(query, filters):
    '''
        Applies the company_id / pos_id / user_id filters that live on the
        visit Attendance to a query already joined to Attendance. Shared by the
        impulse and replenishment inventory listings.
    '''
    if filters.company_id is not None:
        query = query.filter(Attendance.company_id == filters.company_id)
    if filters.pos_id is not None:
        query = query.filter(Attendance.point_of_sale_id == filters.pos_id)
    if filters.user_id is not None:
        query = query.filter(Attendance.user_id == filters.user_id)
    return query


def attach_visit_fields(row, attendance: Attendance | None):
    '''
        Binaria 2026-07-08: attaches the company_id / pos_id / user_id that live
        on a visit Attendance onto an ORM row instance, so Pydantic
        `from_attributes` exposes them in the response without dropping the
        row's own relationships (details / photos). company_id is only filled
        when the row does not already carry its own (e.g. reports keep theirs).
    '''
    row.pos_id = attendance.point_of_sale_id if attendance else None
    row.user_id = attendance.user_id if attendance else None
    if getattr(row, 'company_id', None) is None:
        row.company_id = attendance.company_id if attendance else None
    return row
