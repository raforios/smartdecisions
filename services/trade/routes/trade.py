'''
    Trade routes — Planned Routes, Planned Points, Planning, Planning Detail,
    Bulk uploads and Attendances.
'''
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Form, Header, Query, Request, status
from sqlalchemy.orm import Session

from controllers.trade import (
    attendance_check_in_controller,
    attendance_check_out_controller,
    bulk_upload_planned_routes_controller,
    bulk_upload_trade_planning_controller,
    create_planned_point_controller,
    create_planned_route_controller,
    create_planning_detail_controller,
    create_trade_planning_controller,
    delete_planned_point_controller,
    delete_planned_route_controller,
    delete_planning_detail_controller,
    delete_trade_planning_controller,
    get_planned_route_controller,
    get_trade_planning_controller,
    list_planned_routes_controller,
    list_trade_planning_controller,
    update_planned_point_controller,
    update_planned_route_controller,
    update_trade_planning_controller
)
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
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user

router = APIRouter(prefix = '/v1/trade', tags = ['Trade'])


# --- PLANNED ROUTES ---
@router.post(
    '/routes',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a planned route'
)
async def create_planned_route_endpoint(
    route_data: PlannedRouteCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> PlannedRouteResponseSchema:
    '''Create a planned route with optional inline points.'''
    return await create_planned_route_controller(
        route_data = route_data, db = db,
        request = request, current_user = current_user
    )


@router.get(
    '/routes',
    response_model = PlannedRouteListResponseSchema,
    summary = 'List planned routes'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def list_planned_routes_endpoint(
    request: Request,
    filters: PlannedRouteFilterSchema = Depends(),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, gt = 0, le = 500),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> PlannedRouteListResponseSchema:
    '''Paginated list of planned routes with filters.'''
    return await list_planned_routes_controller(
        filters = filters, skip = skip, limit = limit,
        db = db, request = request, current_user = current_user
    )


@router.get(
    '/routes/{route_id}',
    response_model = PlannedRouteResponseSchema,
    summary = 'Get a planned route by ID'
)
async def get_planned_route_endpoint(
    route_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> PlannedRouteResponseSchema:
    '''Retrieve a planned route by ID with its points.'''
    return await get_planned_route_controller(
        route_id = route_id, db = db,
        request = request, current_user = current_user
    )


@router.put(
    '/routes/{route_id}',
    response_model = PlannedRouteResponseSchema,
    summary = 'Update a planned route master record'
)
async def update_planned_route_endpoint(
    route_id: int,
    update_data: PlannedRouteUpdateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> PlannedRouteResponseSchema:
    '''Update planned route master fields.'''
    return await update_planned_route_controller(
        route_id = route_id, update_data = update_data,
        db = db, request = request, current_user = current_user
    )


@router.delete(
    '/routes/{route_id}',
    response_model = Dict[str, Any],
    summary = 'Delete a planned route'
)
async def delete_planned_route_endpoint(
    route_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    '''Delete a planned route (cascades to its points).'''
    return await delete_planned_route_controller(
        route_id = route_id, db = db,
        request = request, current_user = current_user
    )


# --- PLANNED POINTS (subresource of a route) ---
@router.post(
    '/routes/{route_id}/points',
    response_model = PlannedPointResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Add a planned point to a route'
)
async def create_planned_point_endpoint(
    route_id: int,
    point_data: PlannedPointCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> PlannedPointResponseSchema:
    '''Append a planned point to an existing route.'''
    return await create_planned_point_controller(
        route_id = route_id, point_data = point_data,
        db = db, request = request, current_user = current_user
    )


@router.put(
    '/points/{point_id}',
    response_model = PlannedPointResponseSchema,
    summary = 'Update a planned point'
)
async def update_planned_point_endpoint(
    point_id: int,
    update_data: PlannedPointUpdateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> PlannedPointResponseSchema:
    '''Update a planned point.'''
    return await update_planned_point_controller(
        point_id = point_id, update_data = update_data,
        db = db, request = request, current_user = current_user
    )


@router.delete(
    '/points/{point_id}',
    response_model = Dict[str, Any],
    summary = 'Delete a planned point'
)
async def delete_planned_point_endpoint(
    point_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    '''Delete a planned point.'''
    return await delete_planned_point_controller(
        point_id = point_id, db = db,
        request = request, current_user = current_user
    )


# --- TRADE PLANNING (campaigns) ---
@router.post(
    '/planning',
    response_model = TradePlanningResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a planning campaign'
)
async def create_trade_planning_endpoint(
    planning_data: TradePlanningCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> TradePlanningResponseSchema:
    '''Create a planning campaign with optional inline detail rows.'''
    return await create_trade_planning_controller(
        planning_data = planning_data, db = db,
        request = request, current_user = current_user
    )


@router.get(
    '/planning',
    response_model = TradePlanningListResponseSchema,
    summary = 'List planning campaigns'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def list_trade_planning_endpoint(
    request: Request,
    filters: TradePlanningFilterSchema = Depends(),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, gt = 0, le = 500),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> TradePlanningListResponseSchema:
    '''Paginated list of planning campaigns with filters.'''
    return await list_trade_planning_controller(
        filters = filters, skip = skip, limit = limit,
        db = db, request = request, current_user = current_user
    )


@router.get(
    '/planning/{planning_id}',
    response_model = TradePlanningResponseSchema,
    summary = 'Get a planning campaign by ID'
)
async def get_trade_planning_endpoint(
    planning_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> TradePlanningResponseSchema:
    '''Retrieve a planning campaign by ID with its details.'''
    return await get_trade_planning_controller(
        planning_id = planning_id, db = db,
        request = request, current_user = current_user
    )


@router.put(
    '/planning/{planning_id}',
    response_model = TradePlanningResponseSchema,
    summary = 'Update a planning campaign master record'
)
async def update_trade_planning_endpoint(
    planning_id: int,
    update_data: TradePlanningUpdateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> TradePlanningResponseSchema:
    '''Update planning master fields.'''
    return await update_trade_planning_controller(
        planning_id = planning_id, update_data = update_data,
        db = db, request = request, current_user = current_user
    )


@router.delete(
    '/planning/{planning_id}',
    response_model = Dict[str, Any],
    summary = 'Delete a planning campaign'
)
async def delete_trade_planning_endpoint(
    planning_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    '''Delete a planning campaign (cascades to its details).'''
    return await delete_trade_planning_controller(
        planning_id = planning_id, db = db,
        request = request, current_user = current_user
    )


# --- PLANNING DETAIL (subresource) ---
@router.post(
    '/planning/{planning_id}/details',
    response_model = TradePlanningDetailResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Add a detail row to a planning'
)
async def create_planning_detail_endpoint(
    planning_id: int,
    detail_data: TradePlanningDetailCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> TradePlanningDetailResponseSchema:
    '''Append a detail row (route + day) to a planning campaign.'''
    return await create_planning_detail_controller(
        planning_id = planning_id, detail_data = detail_data,
        db = db, request = request, current_user = current_user
    )


@router.delete(
    '/planning/details/{detail_id}',
    response_model = Dict[str, Any],
    summary = 'Delete a planning detail row'
)
async def delete_planning_detail_endpoint(
    detail_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    '''Remove a detail row from a planning campaign.'''
    return await delete_planning_detail_controller(
        detail_id = detail_id, db = db,
        request = request, current_user = current_user
    )


# --- BULK UPLOADS ---
@router.post(
    '/routes/bulk-upload',
    response_model = Dict[str, Any],
    summary = 'Bulk upload of planned routes + their points (CSV)'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def bulk_upload_planned_routes_endpoint(
    request: Request,
    file_name: str = Form(..., description = 'CSV file name already uploaded to FILES.'),
    delimiter: Optional[str] = Form(',', description = 'Field separator. Default: comma.'),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    '''Bulk upload of planned routes + their points from a CSV file.'''
    return await bulk_upload_planned_routes_controller(
        db = db, request = request, current_user = current_user,
        file_name = file_name, delimiter = delimiter, auth_token = authorization
    )


@router.post(
    '/planning/bulk-upload',
    response_model = Dict[str, Any],
    summary = 'Bulk upload of planning campaigns + day-by-day route assignments (CSV)'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def bulk_upload_trade_planning_endpoint(
    request: Request,
    file_name: str = Form(..., description = 'CSV file name already uploaded to FILES.'),
    delimiter: Optional[str] = Form(',', description = 'Field separator. Default: comma.'),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    '''Bulk upload of planning campaigns + day-by-day route assignments.'''
    return await bulk_upload_trade_planning_controller(
        db = db, request = request, current_user = current_user,
        file_name = file_name, delimiter = delimiter, auth_token = authorization
    )


# --- ATTENDANCES ---
@router.post(
    '/attendances/check-in',
    response_model = AttendanceResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register an attendance check-in'
)
async def attendance_check_in_endpoint(
    payload: AttendanceCheckInSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> AttendanceResponseSchema:
    '''Register a check-in event against a planned point.'''
    return await attendance_check_in_controller(
        payload = payload, db = db,
        request = request, current_user = current_user
    )


@router.patch(
    '/attendances/{attendance_id}/check-out',
    response_model = AttendanceResponseSchema,
    summary = 'Register an attendance check-out'
)
async def attendance_check_out_endpoint(
    attendance_id: int,
    payload: AttendanceCheckOutSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> AttendanceResponseSchema:
    '''Register a check-out event and compute duration + workload delta.'''
    return await attendance_check_out_controller(
        attendance_id = attendance_id, payload = payload,
        db = db, request = request, current_user = current_user
    )
