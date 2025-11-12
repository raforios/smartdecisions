'''
    Trade Controllers
'''
from typing import Any, Dict
from sqlalchemy.orm import Session
from fastapi import Request
from services.utils import handle_service_errors
from services.trade import (
    create_adhoc_planning_service,
    create_trade_planning_service,
    delete_trade_planning_service,
    get_trade_planning_by_id_service,
    get_trade_planning_list_service,
    justify_planning_absence_service,
    update_trade_planning_service,
    update_trade_planning_workload_service
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

# --- A.3. TRADE PLANNING CONTROLLERS ---

@handle_service_errors('TRADE')
async def create_trade_planning_controller(
    planning_data: TradePlanningCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TradePlanningResponseSchema:
    '''
        Controller to handle the creation of a new Trade Planning entry.
    '''
    # 1. Call the service
    # El servicio devuelve (db_planning, auditable_data)
    db_planning, _ = await create_trade_planning_service(
        db = db,
        planning_data = planning_data
    )

    # 2. Return the response model
    return TradePlanningResponseSchema.model_validate(
        db_planning, from_attributes = True
    )


@handle_service_errors('TRADE')
async def get_trade_planning_by_id_controller(
    planning_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TradePlanningResponseSchema:
    '''
        Controller to retrieve a specific Trade Planning entry by its ID.
    '''
    db_planning = await get_trade_planning_by_id_service(
        db = db,
        planning_id = planning_id
    )
    return TradePlanningResponseSchema.model_validate(
        db_planning, from_attributes = True
    )


@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_trade_planning_list_controller(
    filters: TradePlanningFilterSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    skip: int = 0,
    limit: int = 100
) -> TradePlanningListResponseSchema:
    '''
        Controller to retrieve a paginated list of Trade Planning entries.
    '''
    items, total = await get_trade_planning_list_service(
        db = db, filters = filters, skip = skip, limit = limit
    )
    return TradePlanningListResponseSchema(items = items, total = total)


@handle_service_errors('TRADE')
async def update_trade_planning_controller(
    planning_id: int,
    update_data: TradePlanningUpdateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TradePlanningResponseSchema:
    '''
        Controller for updating a Trade Planning entry (status or comments).
    '''
    db_planning, _ = await update_trade_planning_service(
        db = db,
        planning_id = planning_id,
        update_data = update_data
    )
    return TradePlanningResponseSchema.model_validate(
        db_planning, from_attributes = True
    )


@handle_service_errors('TRADE')
async def delete_trade_planning_controller(
    planning_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller for deleting a Trade Planning entry.
    '''
    deleted_id, _ = await delete_trade_planning_service(
        db = db,
        planning_id = planning_id
    )
    return {
        'message': f'Trade Planning with ID {deleted_id} deleted successfully.'
    }


@handle_service_errors('TRADE')
async def update_trade_planning_workload_controller(
    planning_id: int,
    workload_data: TradePlanningWorkloadUpdateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TradePlanningResponseSchema:
    '''
        Controller for the PATCH endpoint to calculate and update workload.
    '''
    db_planning, _ = await update_trade_planning_workload_service(
        db = db,
        planning_id = planning_id,
        workload_data = workload_data
    )
    return TradePlanningResponseSchema.model_validate(
        db_planning, from_attributes = True
    )

# --- A.4. AGENDA DE CAMPO CONTROLLERS ---

@handle_service_errors('TRADE')
async def create_adhoc_planning_controller(
    adhoc_data: TradePlanningAdHocCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TradePlanningResponseSchema:
    '''
        Controller for creating an Ad-Hoc visit.
    '''
    db_planning, _ = await create_adhoc_planning_service(
        db = db,
        adhoc_data = adhoc_data
    )
    return TradePlanningResponseSchema.model_validate(
        db_planning, from_attributes = True
    )


@handle_service_errors('TRADE')
async def justify_planning_absence_controller(
    planning_id: int,
    justification_data: TradePlanningJustificationSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TradePlanningResponseSchema:
    '''
        Controller for justifying a non-visit.
    '''
    db_planning, _ = await justify_planning_absence_service(
        db = db,
        planning_id = planning_id,
        justification_data = justification_data
    )
    return TradePlanningResponseSchema.model_validate(
        db_planning, from_attributes = True
    )
