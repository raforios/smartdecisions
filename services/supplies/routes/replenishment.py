'''
    Routes for replenishments and receptions.
'''
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Query, status
from sqlalchemy.orm import Session

from controllers.replenishment import (
    cancel_replenishment_controller,
    create_reception_controller,
    create_replenishment_controller,
    create_replenishments_bulk_controller,
    get_replenishment_controller,
    list_pending_suggestions_controller,
    list_receptions_controller,
    list_replenishments_controller,
)
from schemas.enums import ReplenishmentStatusEnum, RoleEnum
from schemas.replenishment import (
    ReceptionCreateSchema,
    ReceptionResponseSchema,
    ReplenishmentBulkCreateSchema,
    ReplenishmentCreateSchema,
    ReplenishmentResponseSchema,
    ReplenishmentSuggestionSchema,
)
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user, require_roles


router = APIRouter(prefix = '/v1/supplies', tags = ['Replenishments'])


@router.get(
    '/replenishments/pending',
    response_model = List[ReplenishmentSuggestionSchema],
    summary = 'List items that need replenishment',
)
async def list_pending(
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Items at or below the configured minimum, with the suggested quantity
        to be requested to the external purchasing system.
    '''
    return await list_pending_suggestions_controller(db)


@router.post(
    '/replenishments',
    response_model = ReplenishmentResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a replenishment order',
)
async def create_replenishment(
    payload: ReplenishmentCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(
        require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)
    ),
):
    '''
        Creates a single replenishment order. ADMIN or WAREHOUSE_MANAGER only.
    '''
    return await create_replenishment_controller(db, payload, created_by = current_user)


@router.post(
    '/replenishments/bulk',
    response_model = List[ReplenishmentResponseSchema],
    status_code = status.HTTP_201_CREATED,
    summary = 'Create multiple replenishment orders at once',
)
async def create_replenishments_bulk(
    payload: ReplenishmentBulkCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(
        require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)
    ),
):
    '''
        Creates several replenishments in one round-trip, typically after
        consuming /replenishments/pending.
    '''
    return await create_replenishments_bulk_controller(db, payload, created_by = current_user)


@router.get(
    '/replenishments',
    response_model = List[ReplenishmentResponseSchema],
    summary = 'List replenishments',
)
async def list_replenishments(
    status_filter: Optional[ReplenishmentStatusEnum] = Query(None, alias = 'status'),
    item_id: Optional[int] = Query(None, ge = 1),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Lists replenishments with optional status and item filters.
    '''
    return await list_replenishments_controller(
        db, status = status_filter, item_id = item_id, skip = skip, limit = limit,
    )


@router.get(
    '/replenishments/{replenishment_id}',
    response_model = ReplenishmentResponseSchema,
    summary = 'Get a replenishment by id',
)
async def get_replenishment(
    replenishment_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Returns a single replenishment by id.
    '''
    return await get_replenishment_controller(db, replenishment_id)


@router.patch(
    '/replenishments/{replenishment_id}/cancel',
    response_model = ReplenishmentResponseSchema,
    summary = 'Cancel a replenishment',
)
async def cancel_replenishment(
    replenishment_id: int,
    reason: Optional[str] = Body(None, embed = True),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Cancels a replenishment that is still in REQUESTED status.
    '''
    return await cancel_replenishment_controller(db, replenishment_id, reason)


@router.post(
    '/replenishments/{replenishment_id}/receptions',
    response_model = ReceptionResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register a reception against a replenishment',
)
async def create_reception(
    replenishment_id: int,
    payload: ReceptionCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(
        require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)
    ),
):
    '''
        Registers a physical reception, posts a kardex IN movement, and
        advances the replenishment status when fully received.
    '''
    return await create_reception_controller(
        db, replenishment_id, payload, received_by = current_user,
    )


@router.get(
    '/replenishments/{replenishment_id}/receptions',
    response_model = List[ReceptionResponseSchema],
    summary = 'List receptions of a replenishment',
)
async def list_receptions(
    replenishment_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Lists all receptions registered against a replenishment.
    '''
    return await list_receptions_controller(db, replenishment_id)
