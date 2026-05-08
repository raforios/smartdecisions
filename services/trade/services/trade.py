'''
    Business Logic for Trade — Planned Routes, Planned Points, Trade Planning,
    Planning Detail, and Attendances.
'''
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from models.pos import PointOfSale, PointOfSaleStatus
from models.trade import (
    Attendance,
    PlannedPoint,
    PlannedRoute,
    TradePlanning,
    TradePlanningDetail
)
from schemas.trade import (
    AttendanceCheckInSchema,
    AttendanceCheckOutSchema,
    PlannedPointCreateSchema,
    PlannedPointUpdateSchema,
    PlannedRouteBulkItemSchema,
    PlannedRouteCreateSchema,
    PlannedRouteFilterSchema,
    PlannedRouteUpdateSchema,
    TradePlanningBulkItemSchema,
    TradePlanningCreateSchema,
    TradePlanningDetailCreateSchema,
    TradePlanningFilterSchema,
    TradePlanningUpdateSchema
)
from services.crud import (
    create_record,
    delete_record,
    get_record,
    update_record
)
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from services.logger_config import custom_logger as logger
from services.utils import (
    audit_event,
    generic_bulk_processor,
    get_current_time_gmt,
    handle_service_errors,
    perform_bulk_upload,
    sqlalchemy_object_as_dict
)

from .trade_utils import validate_geofence


# ====================================================================
# PLANNED ROUTE
# ====================================================================
def _validate_pos_for_company(
    db: Session, pos_id: int, company_id: int
) -> None:
    '''
        Ensures a POS exists for the given company before letting MySQL hit
        a FK violation. Translates the boundary error into a 404.
    '''
    exists = db.query(PointOfSale.id).filter(
        PointOfSale.id == pos_id,
        PointOfSale.company_id == company_id
    ).first()
    if not exists:
        raise RegisterNotFoundError(
            detail = (
                f'Point of sale {pos_id} does not exist for company {company_id}.'
            )
        )


@handle_service_errors('TRADE')
@audit_event('TRADE', 'PlannedRoute', 'CREATE')
async def create_planned_route_service(
    db: Session,
    route_data: PlannedRouteCreateSchema
) -> Tuple[PlannedRoute, Dict[str, Any]]:
    '''
        Creates a planned route along with its inline points (if any).

        Args:
            db (Session): The database session.
            route_data (PlannedRouteCreateSchema): The route + inline points.

        Returns:
            Tuple[PlannedRoute, Dict[str, Any]]: The persisted route and audit data.
    '''
    if db.query(PlannedRoute).filter_by(
        company_id = route_data.company_id, route_code = route_data.route_code
    ).first():
        raise RegisterAlreadyExistsError(
            detail = (
                f'Planned route with code {route_data.route_code} '
                f'already exists for company {route_data.company_id}.'
            )
        )

    # Validate every inline point's POS up-front so we surface a 404 instead
    # of a generic 500 from a FK violation at flush time.
    for point in route_data.points:
        _validate_pos_for_company(db, point.point_of_sale_id, route_data.company_id)

    db_route = PlannedRoute(
        company_id = route_data.company_id,
        route_name = route_data.route_name,
        route_code = route_data.route_code,
        description = route_data.description
    )
    db_route.points = [
        PlannedPoint(**point.model_dump()) for point in route_data.points
    ]
    db.add(db_route)
    db.commit()
    db.refresh(db_route)
    return db_route, {'old_values': None, 'new_values': sqlalchemy_object_as_dict(db_route)}


@handle_service_errors('TRADE')
async def get_planned_route_by_id_service(
    db: Session,
    route_id: int
) -> PlannedRoute:
    '''
        Retrieves a planned route by ID with its points eager-loaded.
    '''
    return get_record(
        db, PlannedRoute, route_id,
        eager_load_options = ['points']
    )


@handle_service_errors('TRADE')
async def get_planned_routes_list_service(
    db: Session,
    filters: PlannedRouteFilterSchema,
    skip: int,
    limit: int
) -> Tuple[List[PlannedRoute], int]:
    '''
        Lists planned routes with pagination and optional filters.
    '''
    query = db.query(PlannedRoute).filter(PlannedRoute.company_id == filters.company_id)
    if filters.route_code:
        query = query.filter(PlannedRoute.route_code == filters.route_code)
    if filters.route_name:
        query = query.filter(PlannedRoute.route_name.ilike(f'%{filters.route_name}%'))
    total = query.count()
    items = query.options(joinedload(PlannedRoute.points)).offset(skip).limit(limit).all()
    return items, total


@handle_service_errors('TRADE')
@audit_event('TRADE', 'PlannedRoute', 'UPDATE')
async def update_planned_route_service(
    db: Session,
    route_id: int,
    update_data: PlannedRouteUpdateSchema
) -> Tuple[PlannedRoute, Dict[str, Any]]:
    '''
        Updates planned route master fields. Points are managed separately.
    '''
    db_route = get_record(db, PlannedRoute, route_id)
    old_values = sqlalchemy_object_as_dict(db_route)
    db_route = update_record(db, db_route, update_data)
    db.commit()
    db.refresh(db_route)
    return db_route, {'old_values': old_values, 'new_values': sqlalchemy_object_as_dict(db_route)}


@handle_service_errors('TRADE')
@audit_event('TRADE', 'PlannedRoute', 'DELETE')
async def delete_planned_route_service(
    db: Session,
    route_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a planned route (cascades to its points).
    '''
    db_route = get_record(db, PlannedRoute, route_id)
    old_values = sqlalchemy_object_as_dict(db_route)
    delete_record(db, PlannedRoute, route_id)
    db.commit()
    return route_id, {'old_values': old_values, 'new_values': None}


# ====================================================================
# PLANNED POINT (subresource of a route)
# ====================================================================
@handle_service_errors('TRADE')
@audit_event('TRADE', 'PlannedPoint', 'CREATE')
async def create_planned_point_service(
    db: Session,
    route_id: int,
    point_data: PlannedPointCreateSchema
) -> Tuple[PlannedPoint, Dict[str, Any]]:
    '''
        Adds a planned point (visit) to an existing planned route.
    '''
    # Ensure parent route exists. Use it to scope the POS validation to the
    # same company, since planned points cannot reference POS from a different
    # company than their owning route.
    db_route = get_record(db, PlannedRoute, route_id)
    _validate_pos_for_company(db, point_data.point_of_sale_id, db_route.company_id)

    if db.query(PlannedPoint).filter_by(
        planned_route_id = route_id, sequence = point_data.sequence
    ).first():
        raise RegisterAlreadyExistsError(
            detail = (
                f'Sequence {point_data.sequence} is already taken on route {route_id}.'
            )
        )

    db_point = PlannedPoint(
        planned_route_id = route_id,
        **point_data.model_dump()
    )
    db.add(db_point)
    db.commit()
    db.refresh(db_point)
    return db_point, {'old_values': None, 'new_values': sqlalchemy_object_as_dict(db_point)}


@handle_service_errors('TRADE')
@audit_event('TRADE', 'PlannedPoint', 'UPDATE')
async def update_planned_point_service(
    db: Session,
    point_id: int,
    update_data: PlannedPointUpdateSchema
) -> Tuple[PlannedPoint, Dict[str, Any]]:
    '''
        Updates a planned point.
    '''
    db_point = get_record(db, PlannedPoint, point_id)
    old_values = sqlalchemy_object_as_dict(db_point)
    db_point = update_record(db, db_point, update_data)
    db.commit()
    db.refresh(db_point)
    return db_point, {'old_values': old_values, 'new_values': sqlalchemy_object_as_dict(db_point)}


@handle_service_errors('TRADE')
@audit_event('TRADE', 'PlannedPoint', 'DELETE')
async def delete_planned_point_service(
    db: Session,
    point_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a planned point.
    '''
    db_point = get_record(db, PlannedPoint, point_id)
    old_values = sqlalchemy_object_as_dict(db_point)
    delete_record(db, PlannedPoint, point_id)
    db.commit()
    return point_id, {'old_values': old_values, 'new_values': None}


# ====================================================================
# TRADE PLANNING (campaign master + detail)
# ====================================================================
def _validate_planning_dates(start_date: date, end_date: date) -> None:
    if start_date > end_date:
        raise InvalidInputError(
            detail = 'Planning start_date must be earlier than or equal to end_date.'
        )


def _validate_detail_in_range(
    detail_date: date, start_date: date, end_date: date
) -> None:
    if not start_date <= detail_date <= end_date:
        raise InvalidInputError(
            detail = (
                f'Detail date {detail_date} is outside the planning '
                f'window [{start_date} .. {end_date}].'
            )
        )


@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePlanning', 'CREATE')
async def create_trade_planning_service(
    db: Session,
    planning_data: TradePlanningCreateSchema
) -> Tuple[TradePlanning, Dict[str, Any]]:
    '''
        Creates a planning campaign with optional inline detail rows.
    '''
    _validate_planning_dates(planning_data.start_date, planning_data.end_date)

    db_planning = TradePlanning(
        company_id = planning_data.company_id,
        planning_name = planning_data.planning_name,
        description = planning_data.description,
        team_id = planning_data.team_id,
        start_date = planning_data.start_date,
        end_date = planning_data.end_date,
        status = planning_data.status or 'DRAFT'
    )

    for detail in planning_data.details:
        _validate_detail_in_range(
            detail.date_of_day, planning_data.start_date, planning_data.end_date
        )
        # Confirm the route exists for this company.
        route = db.query(PlannedRoute).filter(
            PlannedRoute.id == detail.planned_route_id,
            PlannedRoute.company_id == planning_data.company_id
        ).first()
        if not route:
            raise RegisterNotFoundError(
                detail = (
                    f'Planned route {detail.planned_route_id} not found for '
                    f'company {planning_data.company_id}.'
                )
            )
        db_planning.details.append(TradePlanningDetail(**detail.model_dump()))

    db.add(db_planning)
    db.commit()
    db.refresh(db_planning)
    return db_planning, {
        'old_values': None,
        'new_values': sqlalchemy_object_as_dict(db_planning)
    }


@handle_service_errors('TRADE')
async def get_trade_planning_by_id_service(
    db: Session,
    planning_id: int
) -> TradePlanning:
    '''
        Retrieves a planning campaign with its details eager-loaded.
    '''
    return get_record(
        db, TradePlanning, planning_id, eager_load_options = ['details']
    )


@handle_service_errors('TRADE')
async def get_trade_planning_list_service(
    db: Session,
    filters: TradePlanningFilterSchema,
    skip: int,
    limit: int
) -> Tuple[List[TradePlanning], int]:
    '''
        Lists planning campaigns with pagination and optional filters.
    '''
    query = db.query(TradePlanning).filter(TradePlanning.company_id == filters.company_id)
    if filters.team_id is not None:
        query = query.filter(TradePlanning.team_id == filters.team_id)
    if filters.status:
        query = query.filter(TradePlanning.status == filters.status)
    if filters.date_from:
        query = query.filter(TradePlanning.end_date >= filters.date_from)
    if filters.date_to:
        query = query.filter(TradePlanning.start_date <= filters.date_to)
    total = query.count()
    items = query.options(joinedload(TradePlanning.details)).offset(skip).limit(limit).all()
    return items, total


@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePlanning', 'UPDATE')
async def update_trade_planning_service(
    db: Session,
    planning_id: int,
    update_data: TradePlanningUpdateSchema
) -> Tuple[TradePlanning, Dict[str, Any]]:
    '''
        Updates planning master fields.
    '''
    db_planning = get_record(db, TradePlanning, planning_id)
    old_values = sqlalchemy_object_as_dict(db_planning)

    new_start = update_data.start_date or db_planning.start_date
    new_end = update_data.end_date or db_planning.end_date
    _validate_planning_dates(new_start, new_end)

    db_planning = update_record(db, db_planning, update_data)
    db.commit()
    db.refresh(db_planning)
    return db_planning, {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_planning)
    }


@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePlanning', 'DELETE')
async def delete_trade_planning_service(
    db: Session,
    planning_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a planning campaign and cascades to its details.
    '''
    db_planning = get_record(db, TradePlanning, planning_id)
    old_values = sqlalchemy_object_as_dict(db_planning)
    delete_record(db, TradePlanning, planning_id)
    db.commit()
    return planning_id, {'old_values': old_values, 'new_values': None}


# ====================================================================
# TRADE PLANNING DETAIL (subresource)
# ====================================================================
@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePlanningDetail', 'CREATE')
async def create_planning_detail_service(
    db: Session,
    planning_id: int,
    detail_data: TradePlanningDetailCreateSchema
) -> Tuple[TradePlanningDetail, Dict[str, Any]]:
    '''
        Adds a detail row (route + day) to an existing planning campaign.
    '''
    db_planning = get_record(db, TradePlanning, planning_id)
    _validate_detail_in_range(
        detail_data.date_of_day, db_planning.start_date, db_planning.end_date
    )
    if db.query(TradePlanningDetail).filter_by(
        planning_id = planning_id,
        planned_route_id = detail_data.planned_route_id,
        date_of_day = detail_data.date_of_day
    ).first():
        raise RegisterAlreadyExistsError(
            detail = (
                f'Detail already exists for planning {planning_id} '
                f'with route {detail_data.planned_route_id} on {detail_data.date_of_day}.'
            )
        )

    db_detail = TradePlanningDetail(
        planning_id = planning_id,
        **detail_data.model_dump()
    )
    db.add(db_detail)
    db.commit()
    db.refresh(db_detail)
    return db_detail, {'old_values': None, 'new_values': sqlalchemy_object_as_dict(db_detail)}


@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePlanningDetail', 'DELETE')
async def delete_planning_detail_service(
    db: Session,
    detail_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Removes a detail row from a planning campaign.
    '''
    db_detail = get_record(db, TradePlanningDetail, detail_id)
    old_values = sqlalchemy_object_as_dict(db_detail)
    delete_record(db, TradePlanningDetail, detail_id)
    db.commit()
    return detail_id, {'old_values': old_values, 'new_values': None}


# ====================================================================
# BULK SERVICES
# ====================================================================
def _bulk_route_target(
    db: Session,
    cache: Dict[Tuple[int, str], PlannedRoute],
    item: PlannedRouteBulkItemSchema
) -> PlannedRoute:
    '''
        Returns (or creates) the PlannedRoute that owns the bulk row.
        Caches results per (company_id, route_code) to avoid duplicate
        SELECTs across rows in the same batch.
    '''
    cache_key = (item.company_id, item.route_code)
    if cache_key in cache:
        return cache[cache_key]

    route = db.query(PlannedRoute).filter_by(
        company_id = item.company_id, route_code = item.route_code
    ).first()
    if not route:
        route = PlannedRoute(
            company_id = item.company_id,
            route_code = item.route_code,
            route_name = item.route_name,
            description = item.route_description
        )
        db.add(route)
        db.flush()
    cache[cache_key] = route
    return route


async def _insert_planned_routes_bulk_data(
    db: Session,
    processed_data: List[PlannedRouteBulkItemSchema],
    file_name: str,  # pylint: disable=unused-argument
    auth_token: str  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Inserter step for the planned-routes bulk pipeline. Receives already
        validated rows and persists them in a single transaction.
    '''
    routes_seen: Dict[Tuple[int, str], PlannedRoute] = {}
    points_created = 0
    routes_created = 0

    for item in processed_data:
        route = _bulk_route_target(db, routes_seen, item)
        if route.id is None:
            routes_created += 1
        # Skip if the same sequence already exists for the route.
        existing = db.query(PlannedPoint).filter_by(
            planned_route_id = route.id,
            sequence = item.sequence
        ).first()
        if existing:
            error_msg = (
                f'Skipping bulk row: sequence {item.sequence} already exists '
                f'on route {item.route_code} (company {item.company_id}).'
            )
            logger.warning(error_msg)
            continue

        db.add(PlannedPoint(
            planned_route_id = route.id,
            sequence = item.sequence,
            point_of_sale_id = item.point_of_sale_id,
            planned_workload_minutes = item.planned_workload_minutes,
            is_adhoc = item.is_adhoc,
            justification = item.justification,
            status = item.point_status or 'PENDING',
            comments = item.point_comments
        ))
        points_created += 1

    db.flush()
    return {
        'created_records': points_created,
        'routes_created': routes_created,
        'routes_touched': len(routes_seen)
    }


async def _insert_trade_planning_bulk_data(
    db: Session,
    processed_data: List[TradePlanningBulkItemSchema],
    file_name: str,  # pylint: disable=unused-argument
    auth_token: str  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Inserter step for the trade-planning bulk pipeline. Routes are
        referenced by their human-friendly route_code.
    '''
    plannings_seen: Dict[Tuple[int, str, int], TradePlanning] = {}
    routes_seen: Dict[Tuple[int, str], Optional[PlannedRoute]] = {}
    details_created = 0
    plannings_created = 0

    for item in processed_data:
        planning_key = (item.company_id, item.planning_name, item.team_id)
        planning = plannings_seen.get(planning_key)
        if planning is None:
            planning = db.query(TradePlanning).filter_by(
                company_id = item.company_id,
                planning_name = item.planning_name,
                team_id = item.team_id
            ).first()
        if planning is None:
            _validate_planning_dates(item.start_date, item.end_date)
            planning = TradePlanning(
                company_id = item.company_id,
                planning_name = item.planning_name,
                description = item.description,
                team_id = item.team_id,
                start_date = item.start_date,
                end_date = item.end_date,
                status = item.status or 'DRAFT'
            )
            db.add(planning)
            db.flush()
            plannings_created += 1
        plannings_seen[planning_key] = planning

        route_key = (item.company_id, item.planned_route_code)
        route = routes_seen.get(route_key)
        if route is None:
            route = db.query(PlannedRoute).filter_by(
                company_id = item.company_id, route_code = item.planned_route_code
            ).first()
            routes_seen[route_key] = route
        if route is None:
            error_msg = (
                f'Skipping planning bulk row: route_code {item.planned_route_code} '
                f'not found for company {item.company_id}.'
            )
            logger.warning(error_msg)
            continue

        _validate_detail_in_range(item.date_of_day, planning.start_date, planning.end_date)
        if db.query(TradePlanningDetail).filter_by(
            planning_id = planning.id,
            planned_route_id = route.id,
            date_of_day = item.date_of_day
        ).first():
            continue
        db.add(TradePlanningDetail(
            planning_id = planning.id,
            planned_route_id = route.id,
            date_of_day = item.date_of_day
        ))
        details_created += 1

    db.flush()
    return {
        'created_records': details_created,
        'plannings_created': plannings_created,
        'plannings_touched': len(plannings_seen)
    }


@handle_service_errors('TRADE')
async def bulk_create_planned_routes_service(
    db: Session,
    file_name: str,
    delimiter: str,
    auth_token: str
) -> Dict[str, Any]:
    '''
        Top-level bulk service registered with the FORMS-style bulk pipeline.
        Reads the CSV from FILES, validates rows against
        `PlannedRouteBulkItemSchema` and delegates persistence to the inserter.
    '''
    return await perform_bulk_upload(
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        bulk_schema = PlannedRouteBulkItemSchema,
        processor_func = generic_bulk_processor,
        inserter_func = _insert_planned_routes_bulk_data,
        delimiter = delimiter
    )


@handle_service_errors('TRADE')
async def bulk_create_trade_planning_service(
    db: Session,
    file_name: str,
    delimiter: str,
    auth_token: str
) -> Dict[str, Any]:
    '''
        Top-level bulk service for planning campaigns. Reads + validates the
        CSV and delegates persistence to `_insert_trade_planning_bulk_data`.
    '''
    return await perform_bulk_upload(
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        bulk_schema = TradePlanningBulkItemSchema,
        processor_func = generic_bulk_processor,
        inserter_func = _insert_trade_planning_bulk_data,
        delimiter = delimiter
    )


# ====================================================================
# ATTENDANCE — Check-In / Check-Out against a Planned Point
# ====================================================================
def _resolve_pos_for_point(db: Session, planned_point: PlannedPoint) -> PointOfSale:
    pos = db.query(PointOfSale).filter(
        PointOfSale.id == planned_point.point_of_sale_id
    ).first()
    if not pos:
        raise RegisterNotFoundError(
            detail = f'POS {planned_point.point_of_sale_id} not found.'
        )
    if pos.status != PointOfSaleStatus.ACTIVE:
        raise InvalidInputError(
            detail = (
                f'POS {pos.code} is not ACTIVE. Current status: {pos.status.value}'
            )
        )
    return pos


@handle_service_errors('TRADE')
@audit_event('TRADE', 'Attendance', 'CREATE')
async def register_attendance_check_in(
    db: Session,
    payload: AttendanceCheckInSchema
) -> Tuple[Attendance, Dict[str, Any]]:
    '''
        Registers a check-in event against a planned point.
    '''
    planned_point = get_record(db, PlannedPoint, payload.trade_planned_point_id)
    pos = _resolve_pos_for_point(db, planned_point)

    distance = validate_geofence(
        payload.check_in_latitude, payload.check_in_longitude, pos, action_name = 'Check-In'
    )

    db_attendance = Attendance(
        company_id = payload.company_id,
        user_id = payload.user_id,
        trade_planned_point_id = planned_point.id,
        check_in_time = get_current_time_gmt(),
        check_in_latitude = payload.check_in_latitude,
        check_in_longitude = payload.check_in_longitude,
        check_in_distance_error = distance
    )
    db.add(db_attendance)
    db.flush()
    planned_point.status = 'IN_PROGRESS'
    db.add(planned_point)
    db.commit()
    db.refresh(db_attendance)
    return db_attendance, {
        'old_values': None,
        'new_values': sqlalchemy_object_as_dict(db_attendance)
    }


@handle_service_errors('TRADE')
@audit_event('TRADE', 'Attendance', 'UPDATE')
async def register_attendance_check_out(
    db: Session,
    attendance_id: int,
    payload: AttendanceCheckOutSchema
) -> Tuple[Attendance, Dict[str, Any]]:
    '''
        Registers a check-out event and computes duration + workload delta.
    '''
    db_attendance = get_record(db, Attendance, attendance_id)
    if db_attendance.check_out_time:
        raise InvalidInputError(
            detail = f'Attendance {attendance_id} is already closed.'
        )

    planned_point = get_record(db, PlannedPoint, db_attendance.trade_planned_point_id)
    pos = _resolve_pos_for_point(db, planned_point)
    distance = validate_geofence(
        payload.check_out_latitude, payload.check_out_longitude, pos, action_name = 'Check-Out'
    )

    old_values = sqlalchemy_object_as_dict(db_attendance)
    now = get_current_time_gmt()
    delta_seconds = (now - db_attendance.check_in_time).total_seconds()
    duration_minutes = max(0, int(delta_seconds // 60))

    db_attendance.check_out_time = now
    db_attendance.check_out_latitude = payload.check_out_latitude
    db_attendance.check_out_longitude = payload.check_out_longitude
    db_attendance.check_out_distance_error = distance
    db_attendance.duration_minutes = duration_minutes

    planned_point.actual_workload_minutes = duration_minutes
    planned_point.workload_difference_minutes = (
        duration_minutes - planned_point.planned_workload_minutes
    )
    planned_point.status = 'DONE'
    if payload.comments is not None:
        planned_point.comments = payload.comments

    db.add(db_attendance)
    db.add(planned_point)
    db.commit()
    db.refresh(db_attendance)
    return db_attendance, {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_attendance)
    }
