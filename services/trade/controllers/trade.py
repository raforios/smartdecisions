'''
    Trade Controllers — Planned Routes, Planned Points, Trade Planning,
    Planning Detail, and Attendances.
'''
from typing import Any, Dict, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from schemas.trade import (
    AttendanceCheckInSchema,
    AttendanceCheckOutSchema,
    AttendanceResponseSchema,
    PlannedPointCreateSchema,
    PlannedPointResponseSchema,
    PlannedPointUpdateSchema,
    PlannedRouteCreateSchema,
    PlannedRouteFilterSchema,
    PlannedRouteListResponseSchema,
    PlannedRouteResponseSchema,
    PlannedRouteUpdateSchema,
    TradePlanningCreateSchema,
    TradePlanningDetailCreateSchema,
    TradePlanningDetailResponseSchema,
    TradePlanningFilterSchema,
    TradePlanningListResponseSchema,
    TradePlanningResponseSchema,
    TradePlanningUpdateSchema
)
from services.trade import (
    bulk_create_planned_routes_service,
    bulk_create_trade_planning_service,
    create_planned_point_service,
    create_planned_route_service,
    create_planning_detail_service,
    create_trade_planning_service,
    delete_planned_point_service,
    delete_planned_route_service,
    delete_planning_detail_service,
    delete_trade_planning_service,
    get_planned_route_by_id_service,
    get_planned_routes_list_service,
    get_trade_planning_by_id_service,
    get_trade_planning_list_service,
    register_attendance_check_in,
    register_attendance_check_out,
    update_planned_point_service,
    update_planned_route_service,
    update_trade_planning_service
)
from services.utils import generic_bulk_controller_wrapper, handle_service_errors


# --- PLANNED ROUTE ---
@handle_service_errors('TRADE')
async def create_planned_route_controller(
    route_data: PlannedRouteCreateSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Controller to create a planned route with optional inline points.
    '''
    db_route = await create_planned_route_service(db = db, route_data = route_data)
    return PlannedRouteResponseSchema.model_validate(db_route, from_attributes = True)


@handle_service_errors('TRADE')
async def get_planned_route_controller(
    route_id: int,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Controller to retrieve a planned route by ID.
    '''
    db_route = await get_planned_route_by_id_service(db = db, route_id = route_id)
    return PlannedRouteResponseSchema.model_validate(db_route, from_attributes = True)


@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def list_planned_routes_controller(
    filters: PlannedRouteFilterSchema,
    skip: int,
    limit: int,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> PlannedRouteListResponseSchema:
    '''
        Controller to list planned routes with pagination and filters.
    '''
    items, total = await get_planned_routes_list_service(
        db = db, filters = filters, skip = skip, limit = limit
    )
    serialized = [
        PlannedRouteResponseSchema.model_validate(item, from_attributes = True)
        for item in items
    ]
    return PlannedRouteListResponseSchema(items = serialized, total = total)


@handle_service_errors('TRADE')
async def update_planned_route_controller(
    route_id: int,
    update_data: PlannedRouteUpdateSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Controller to update a planned route master record.
    '''
    db_route = await update_planned_route_service(
        db = db, route_id = route_id, update_data = update_data
    )
    return PlannedRouteResponseSchema.model_validate(db_route, from_attributes = True)


@handle_service_errors('TRADE')
async def delete_planned_route_controller(
    route_id: int,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller to delete a planned route (cascades to points).
    '''
    deleted_id = await delete_planned_route_service(db = db, route_id = route_id)
    return {
        'message': f'Planned route {deleted_id} deleted successfully.',
        'id': deleted_id
    }


# --- PLANNED POINT ---
@handle_service_errors('TRADE')
async def create_planned_point_controller(
    route_id: int,
    point_data: PlannedPointCreateSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> PlannedPointResponseSchema:
    '''
        Controller to add a planned point to an existing route.
    '''
    db_point = await create_planned_point_service(
        db = db, route_id = route_id, point_data = point_data
    )
    return PlannedPointResponseSchema.model_validate(db_point, from_attributes = True)


@handle_service_errors('TRADE')
async def update_planned_point_controller(
    point_id: int,
    update_data: PlannedPointUpdateSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> PlannedPointResponseSchema:
    '''
        Controller to update a planned point.
    '''
    db_point = await update_planned_point_service(
        db = db, point_id = point_id, update_data = update_data
    )
    return PlannedPointResponseSchema.model_validate(db_point, from_attributes = True)


@handle_service_errors('TRADE')
async def delete_planned_point_controller(
    point_id: int,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller to delete a planned point.
    '''
    deleted_id = await delete_planned_point_service(db = db, point_id = point_id)
    return {
        'message': f'Planned point {deleted_id} deleted successfully.',
        'id': deleted_id
    }


# --- TRADE PLANNING ---
@handle_service_errors('TRADE')
async def create_trade_planning_controller(
    planning_data: TradePlanningCreateSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> TradePlanningResponseSchema:
    '''
        Controller to create a planning campaign with optional inline details.
    '''
    db_planning = await create_trade_planning_service(db = db, planning_data = planning_data)
    return TradePlanningResponseSchema.model_validate(db_planning, from_attributes = True)


@handle_service_errors('TRADE')
async def get_trade_planning_controller(
    planning_id: int,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> TradePlanningResponseSchema:
    '''
        Controller to retrieve a planning campaign by ID.
    '''
    db_planning = await get_trade_planning_by_id_service(db = db, planning_id = planning_id)
    return TradePlanningResponseSchema.model_validate(db_planning, from_attributes = True)


@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def list_trade_planning_controller(
    filters: TradePlanningFilterSchema,
    skip: int,
    limit: int,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> TradePlanningListResponseSchema:
    '''
        Controller to list planning campaigns with pagination and filters.
    '''
    items, total = await get_trade_planning_list_service(
        db = db, filters = filters, skip = skip, limit = limit
    )
    serialized = [
        TradePlanningResponseSchema.model_validate(item, from_attributes = True)
        for item in items
    ]
    return TradePlanningListResponseSchema(items = serialized, total = total)


@handle_service_errors('TRADE')
async def update_trade_planning_controller(
    planning_id: int,
    update_data: TradePlanningUpdateSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> TradePlanningResponseSchema:
    '''
        Controller to update a planning campaign master record.
    '''
    db_planning = await update_trade_planning_service(
        db = db, planning_id = planning_id, update_data = update_data
    )
    return TradePlanningResponseSchema.model_validate(db_planning, from_attributes = True)


@handle_service_errors('TRADE')
async def delete_trade_planning_controller(
    planning_id: int,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller to delete a planning campaign.
    '''
    deleted_id = await delete_trade_planning_service(db = db, planning_id = planning_id)
    return {
        'message': f'Trade planning {deleted_id} deleted successfully.',
        'id': deleted_id
    }


# --- PLANNING DETAIL (subresource) ---
@handle_service_errors('TRADE')
async def create_planning_detail_controller(
    planning_id: int,
    detail_data: TradePlanningDetailCreateSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> TradePlanningDetailResponseSchema:
    '''
        Controller to add a detail row (route + day) to a planning campaign.
    '''
    db_detail = await create_planning_detail_service(
        db = db, planning_id = planning_id, detail_data = detail_data
    )
    return TradePlanningDetailResponseSchema.model_validate(db_detail, from_attributes = True)


@handle_service_errors('TRADE')
async def delete_planning_detail_controller(
    detail_id: int,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller to delete a planning detail row.
    '''
    deleted_id = await delete_planning_detail_service(db = db, detail_id = detail_id)
    return {
        'message': f'Planning detail {deleted_id} deleted successfully.',
        'id': deleted_id
    }


# --- BULK CONTROLLERS ---
@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments, duplicate-code
async def bulk_upload_planned_routes_controller(
    db: Session,
    request: Request,
    current_user: str,
    file_name: str,
    delimiter: Optional[str] = ',',
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Bulk-upload of planned routes + their points from CSV. The schema
        validation lives inside `bulk_create_planned_routes_service` (it calls
        `perform_bulk_upload(bulk_schema=PlannedRouteBulkItemSchema, ...)`),
        so the controller-level wrapper does not receive it.
    '''
    return await generic_bulk_controller_wrapper(
        db = db,
        request = request,
        current_user = current_user,
        file_name = file_name,
        microservice_name = 'TRADE',
        entity_name = 'PlannedRoute',
        service_func = bulk_create_planned_routes_service,
        delimiter = delimiter,
        auth_token = auth_token
    )


@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments, duplicate-code
async def bulk_upload_trade_planning_controller(
    db: Session,
    request: Request,
    current_user: str,
    file_name: str,
    delimiter: Optional[str] = ',',
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Bulk-upload of planning campaigns + day-by-day route assignments. The
        schema validation is encapsulated in
        `bulk_create_trade_planning_service` via `perform_bulk_upload`.
    '''
    return await generic_bulk_controller_wrapper(
        db = db,
        request = request,
        current_user = current_user,
        file_name = file_name,
        microservice_name = 'TRADE',
        entity_name = 'TradePlanning',
        service_func = bulk_create_trade_planning_service,
        delimiter = delimiter,
        auth_token = auth_token
    )


# --- ATTENDANCES ---
@handle_service_errors('TRADE')
async def attendance_check_in_controller(
    payload: AttendanceCheckInSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> AttendanceResponseSchema:
    '''
        Controller for the check-in endpoint.
    '''
    db_attendance = await register_attendance_check_in(db = db, payload = payload)
    return AttendanceResponseSchema.model_validate(db_attendance, from_attributes = True)


@handle_service_errors('TRADE')
async def attendance_check_out_controller(
    attendance_id: int,
    payload: AttendanceCheckOutSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> AttendanceResponseSchema:
    '''
        Controller for the check-out endpoint.
    '''
    db_attendance = await register_attendance_check_out(
        db = db, attendance_id = attendance_id, payload = payload
    )
    return AttendanceResponseSchema.model_validate(db_attendance, from_attributes = True)
