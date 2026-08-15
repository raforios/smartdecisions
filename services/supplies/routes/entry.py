'''
    Routes for warehouse entries (Nota de Ingreso).
'''
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from controllers.entry import (
    create_entry_controller,
    get_entry_controller,
    list_entries_controller,
)
from schemas.entry import (
    EntryCreateSchema,
    EntryDetailedResponseSchema,
    EntryFilterSchema,
    EntryResponseSchema,
)
from schemas.enums import RoleEnum
from services.db_connection import GET_DB_DEPENDENCY
from services.security import require_roles


router = APIRouter(prefix = '/v1/supplies', tags = ['Entries'])


@router.post(
    '/entries',
    response_model = EntryDetailedResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register a warehouse entry (Nota de Ingreso)',
)
async def create_entry(
    payload: EntryCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(
        require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)
    ),
):
    '''
        Registers a Nota de Ingreso with its cost layers and valued kardex IN
        movements. ADMIN or WAREHOUSE_MANAGER only.
    '''
    return await create_entry_controller(db, payload, created_by = current_user)


@router.get(
    '/entries',
    response_model = List[EntryResponseSchema],
    summary = 'List warehouse entries',
)
async def list_entries(
    filters: EntryFilterSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Lists entry headers with optional type and date-range filters.
    '''
    return await list_entries_controller(db, filters)


@router.get(
    '/entries/{entry_id}',
    response_model = EntryDetailedResponseSchema,
    summary = 'Get a warehouse entry with its detail lines',
)
async def get_entry(
    entry_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Returns a single entry (Nota de Ingreso) with its lines, for the
        detail and print views.
    '''
    return await get_entry_controller(db, entry_id)
