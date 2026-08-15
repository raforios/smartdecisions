'''
    Routes for suppliers (proveedores).
'''
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from controllers.supplier import (
    create_supplier_controller,
    delete_supplier_controller,
    get_supplier_controller,
    list_suppliers_controller,
    update_supplier_controller,
)
from schemas.enums import RoleEnum
from schemas.supplier import (
    SupplierCreateSchema,
    SupplierFilterSchema,
    SupplierResponseSchema,
    SupplierUpdateSchema,
)
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user, require_roles


router = APIRouter(prefix = '/v1/supplies', tags = ['Suppliers'])

WAREHOUSE_ROLES = (RoleEnum.WAREHOUSE_MANAGER.value, RoleEnum.ADMIN.value)


@router.post(
    '/suppliers',
    response_model = SupplierResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register a supplier',
)
async def create_supplier(
    payload: SupplierCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*WAREHOUSE_ROLES)),
):
    '''
        Registers a supplier. Restricted to warehouse staff and ADMIN.
    '''
    return await create_supplier_controller(db, payload)


@router.get(
    '/suppliers',
    response_model = List[SupplierResponseSchema],
    summary = 'List suppliers',
)
async def list_suppliers(
    filters: SupplierFilterSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user),
):
    '''
        Lists suppliers, optionally filtered by free text or active status.
    '''
    return await list_suppliers_controller(db, filters)


@router.get(
    '/suppliers/{supplier_id}',
    response_model = SupplierResponseSchema,
    summary = 'Get a supplier',
)
async def get_supplier(
    supplier_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user),
):
    '''
        Returns a single supplier by id.
    '''
    return await get_supplier_controller(db, supplier_id)


@router.put(
    '/suppliers/{supplier_id}',
    response_model = SupplierResponseSchema,
    summary = 'Update a supplier',
)
async def update_supplier(
    supplier_id: int,
    payload: SupplierUpdateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*WAREHOUSE_ROLES)),
):
    '''
        Partially updates a supplier. Restricted to warehouse staff and ADMIN.
    '''
    return await update_supplier_controller(db, supplier_id, payload)


@router.delete(
    '/suppliers/{supplier_id}',
    summary = 'Delete a supplier without documents',
)
async def delete_supplier(
    supplier_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value)),
):
    '''
        Deletes a supplier that never issued a Nota de Ingreso. Restricted to
        ADMIN; vendors with documents must be deactivated instead.
    '''
    removed_id = await delete_supplier_controller(db, supplier_id)
    return {'deleted_id': removed_id}
