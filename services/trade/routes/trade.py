'''
    Trade: routes handler
'''
from typing import Any, Dict
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.trade import (
    create_adhoc_planning_controller,
    create_trade_planning_controller,
    delete_trade_planning_controller,
    get_trade_planning_by_id_controller,
    get_trade_planning_list_controller,
    justify_planning_absence_controller,
    update_trade_planning_controller,
    update_trade_planning_workload_controller
)
from schemas.trade import (
    TradePlanningAdHocCreateSchema,
    TradePlanningCreateSchema,
    TradePlanningFilterSchema,
    TradePlanningJustificationSchema,
    TradePlanningListResponseSchema,
    TradePlanningResponseSchema,
    TradePlanningUpdateSchema,
    TradePlanningWorkloadUpdateSchema,
)

router = APIRouter(prefix = '/v1/trade', tags = ['Trade'])

# --- A.3. TRADE PLANNING ENDPOINTS ---
@router.post(
    '/planning',
    response_model = TradePlanningResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create Trade Planning Entry',
    description = 'Creates a new local planning entry linking User, POS, and Planning ID.'
)
async def create_trade_planning_endpoint(
    planning_data: TradePlanningCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new Trade Planning entry.
    '''
    message = f'User: {current_user}. Request create Trade Planning.'
    logger.info(message)
    return await create_trade_planning_controller(
        planning_data = planning_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/planning/{planning_id}',
    response_model = TradePlanningResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get Trade Planning by ID'
)
async def get_trade_planning_by_id_endpoint(
    planning_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a specific Trade Planning entry.
    '''
    return await get_trade_planning_by_id_controller(
        planning_id = planning_id,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/planning',
    response_model = TradePlanningListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List Trade Planning Entries'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_trade_planning_list_endpoint(
    request: Request,
    filters: TradePlanningFilterSchema = Depends(),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to list Trade Planning entries with filtering and pagination.
    '''
    return await get_trade_planning_list_controller(
        filters = filters,
        db = db,
        request = request,
        current_user = current_user,
        skip = skip,
        limit = limit
    )

@router.put(
    '/planning/{planning_id}',
    response_model = TradePlanningResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update Trade Planning'
)
async def update_trade_planning_endpoint(
    planning_id: int,
    update_data: TradePlanningUpdateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update a Trade Planning entry (status/comments).
    '''
    message = f'User: {current_user}. Request update Trade Planning ID: {planning_id}.'
    logger.info(message)
    return await update_trade_planning_controller(
        planning_id = planning_id,
        update_data = update_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/planning/{planning_id}',
    response_model = Dict[str, Any],
    status_code = status.HTTP_200_OK,
    summary = 'Delete Trade Planning'
)
async def delete_trade_planning_endpoint(
    planning_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a Trade Planning entry.
    '''
    message = f'User: {current_user}. Request delete Trade Planning ID: {planning_id}.'
    logger.info(message)
    return await delete_trade_planning_controller(
        planning_id = planning_id,
        db = db,
        request = request,
        current_user = current_user
    )

@router.patch(
    '/planning/{planning_id}/workload',
    response_model = TradePlanningResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Calculate Workload (Check-out)'
)
async def update_trade_planning_workload_endpoint(
    planning_id: int,
    workload_data: TradePlanningWorkloadUpdateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to calculate actual workload based on Check-in/Check-out times.
        Usually called by Frontend after the user finishes the visit.
    '''
    message = f'User: {current_user}. Request Workload Calculation for ID: {planning_id}.'
    logger.info(message)
    return await update_trade_planning_workload_controller(
        planning_id = planning_id,
        workload_data = workload_data,
        db = db,
        request = request,
        current_user = current_user
    )

# --- A.4. AGENDA DE CAMPO ENDPOINTS ---
@router.post(
    '/planning/adhoc',
    response_model = TradePlanningResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create Ad-Hoc Visit',
    description = 'Creates an unplanned visit (Fuera de Ruta) for the user.'
)
async def create_adhoc_planning_endpoint(
    adhoc_data: TradePlanningAdHocCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create an Ad-Hoc visit.
    '''
    message = f'User: {current_user}. Request Create Ad-Hoc Visit.'
    logger.info(message)
    return await create_adhoc_planning_controller(
        adhoc_data = adhoc_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.patch(
    '/planning/{planning_id}/justify',
    response_model = TradePlanningResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Justify Non-Visit'
)
async def justify_planning_absence_endpoint(
    planning_id: int,
    justification_data: TradePlanningJustificationSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
    Endpoint to justify why a visit was not performed (cancels the visit).
    '''
    message = f'User: {current_user}. Request Justify Absence ID: {planning_id}.'
    logger.info(message)
    return await justify_planning_absence_controller(
        planning_id = planning_id,
        justification_data = justification_data,
        db = db,
        request = request,
        current_user = current_user
    )
