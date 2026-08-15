'''
    Routes for the catalog (categories, units, items).
'''
from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from controllers.catalog import (
    create_category_controller,
    create_item_controller,
    create_unit_controller,
    delete_category_controller,
    delete_item_controller,
    delete_unit_controller,
    get_item_controller,
    list_categories_controller,
    list_items_controller,
    list_units_controller,
    update_category_controller,
    update_item_controller,
    update_item_parameters_controller,
    update_unit_controller,
)
from schemas.catalog import (
    CategoryCreateSchema,
    CategoryResponseSchema,
    CategoryUpdateSchema,
    ItemCreateSchema,
    ItemFilterSchema,
    ItemParametersUpdateSchema,
    ItemResponseSchema,
    ItemUpdateSchema,
    UnitCreateSchema,
    UnitResponseSchema,
    UnitUpdateSchema,
)
from schemas.enums import RoleEnum
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user, require_roles


router = APIRouter(prefix = '/v1/supplies', tags = ['Catalog'])


# --------------------------------------------------------------------------- #
# Categories                                                                  #
# --------------------------------------------------------------------------- #
@router.post(
    '/categories',
    response_model = CategoryResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new supply category',
)
async def create_category(
    payload: CategoryCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value)),
):
    '''
        Creates a new supply category. Restricted to ADMIN.
    '''
    return await create_category_controller(db, payload)


@router.get(
    '/categories',
    response_model = List[CategoryResponseSchema],
    summary = 'List supply categories',
)
async def list_categories(
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user),
):
    '''
        Lists all supply categories. Available to any authenticated user.
    '''
    return await list_categories_controller(db, skip = skip, limit = limit)


@router.put(
    '/categories/{category_id}',
    response_model = CategoryResponseSchema,
    summary = 'Update a supply category',
)
async def update_category(
    category_id: int,
    payload: CategoryUpdateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value)),
):
    '''
        Partial update of a category. Restricted to ADMIN.
    '''
    return await update_category_controller(db, category_id, payload)


@router.delete(
    '/categories/{category_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a supply category',
)
async def delete_category(
    category_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value)),
):
    '''
        Hard-deletes a category. Restricted to ADMIN.
    '''
    deleted = await delete_category_controller(db, category_id)
    return {'deleted_id': deleted}


# --------------------------------------------------------------------------- #
# Units                                                                       #
# --------------------------------------------------------------------------- #
@router.post(
    '/units',
    response_model = UnitResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a unit of measure',
)
async def create_unit(
    payload: UnitCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value)),
):
    '''
        Creates a new unit of measure. Restricted to ADMIN.
    '''
    return await create_unit_controller(db, payload)


@router.get(
    '/units',
    response_model = List[UnitResponseSchema],
    summary = 'List units of measure',
)
async def list_units(
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user),
):
    '''
        Lists all units of measure. Available to any authenticated user.
    '''
    return await list_units_controller(db, skip = skip, limit = limit)


@router.put(
    '/units/{unit_id}',
    response_model = UnitResponseSchema,
    summary = 'Update a unit of measure',
)
async def update_unit(
    unit_id: int,
    payload: UnitUpdateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value)),
):
    '''
        Partial update of a unit of measure. Restricted to ADMIN.
    '''
    return await update_unit_controller(db, unit_id, payload)


@router.delete(
    '/units/{unit_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a unit of measure',
)
async def delete_unit(
    unit_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value)),
):
    '''
        Hard-deletes a unit of measure. Restricted to ADMIN.
    '''
    deleted = await delete_unit_controller(db, unit_id)
    return {'deleted_id': deleted}


# --------------------------------------------------------------------------- #
# Items                                                                       #
# --------------------------------------------------------------------------- #
@router.post(
    '/items',
    response_model = ItemResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a supply item',
)
async def create_item(
    payload: ItemCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value)),
):
    '''
        Creates a new supply item with current_stock = 0. Restricted to ADMIN.
    '''
    return await create_item_controller(db, payload)


@router.get(
    '/items',
    response_model = List[ItemResponseSchema],
    summary = 'List supply items',
)
async def list_items(
    filters: ItemFilterSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user),
):
    '''
        Lists supply items filtered by text, accounting group and availability.
    '''
    return await list_items_controller(db, filters = filters)


@router.get(
    '/items/{item_id}',
    response_model = ItemResponseSchema,
    summary = 'Get a supply item',
)
async def get_item(
    item_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user),
):
    '''
        Returns a single item by id.
    '''
    return await get_item_controller(db, item_id)


@router.put(
    '/items/{item_id}',
    response_model = ItemResponseSchema,
    summary = 'Update a supply item',
)
async def update_item(
    item_id: int,
    payload: ItemUpdateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value)),
):
    '''
        Partial update of an item's descriptive fields. Restricted to ADMIN.
    '''
    return await update_item_controller(db, item_id, payload)


@router.put(
    '/items/{item_id}/parameters',
    response_model = ItemResponseSchema,
    summary = 'Update replenishment parameters of an item',
)
async def update_item_parameters(
    item_id: int,
    payload: ItemParametersUpdateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Updates min_stock and/or default_replenishment_qty for an item.
        Available to ADMIN and WAREHOUSE_MANAGER.
    '''
    return await update_item_parameters_controller(db, item_id, payload)


@router.delete(
    '/items/{item_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Deactivate a supply item',
)
async def delete_item(
    item_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value)),
):
    '''
        Soft-deletes an item by setting is_active = False. Restricted to ADMIN.
        Kardex history is preserved by design.
    '''
    deleted = await delete_item_controller(db, item_id)
    return {'deactivated_id': deleted}
