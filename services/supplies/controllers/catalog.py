'''
    Controllers for the catalog (categories, units, items, system parameters).

    Routes delegate to these functions; business validation lives here and in
    services.supplies_logic when shared across modules.
'''
from typing import List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.supplies import Category, Item, SystemParameter, Unit
from schemas.catalog import (
    CategoryCreateSchema,
    CategoryResponseSchema,
    CategoryUpdateSchema,
    ItemCreateSchema,
    ItemParametersUpdateSchema,
    ItemResponseSchema,
    ItemUpdateSchema,
    SystemParameterResponseSchema,
    SystemParameterUpsertSchema,
    UnitCreateSchema,
    UnitResponseSchema,
    UnitUpdateSchema,
)
from services.crud import (
    create_record,
    delete_record,
    get_all_records_paginated,
    get_record,
    update_record,
)
from services.exceptions import RegisterAlreadyExistsError, RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt


# --------------------------------------------------------------------------- #
# Category                                                                    #
# --------------------------------------------------------------------------- #
async def create_category_controller(
    db: Session, payload: CategoryCreateSchema
) -> CategoryResponseSchema:
    '''
        Creates a category. Raises 409 if the code is already in use.
    '''
    try:
        record = create_record(db, Category, payload)
        db.commit()
        return CategoryResponseSchema.model_validate(record)
    except IntegrityError as exc:
        db.rollback()
        raise RegisterAlreadyExistsError(
            detail = f'Category code "{payload.code}" already exists.'
        ) from exc


async def list_categories_controller(
    db: Session, skip: int = 0, limit: int = 100
) -> List[CategoryResponseSchema]:
    '''
        Returns a paginated list of categories.
    '''
    rows = get_all_records_paginated(db, Category, skip = skip, limit = limit)
    return [CategoryResponseSchema.model_validate(row) for row in rows]


async def update_category_controller(
    db: Session, category_id: int, payload: CategoryUpdateSchema
) -> CategoryResponseSchema:
    '''
        Partial update of a category.
    '''
    record = get_record(db, Category, category_id)
    updated = update_record(db, record, payload)
    db.commit()
    return CategoryResponseSchema.model_validate(updated)


async def delete_category_controller(db: Session, category_id: int) -> int:
    '''
        Hard-deletes a category. Relies on FK constraints to block removal
        when items still reference it.
    '''
    delete_record(db, Category, category_id)
    db.commit()
    return category_id


# --------------------------------------------------------------------------- #
# Unit                                                                        #
# --------------------------------------------------------------------------- #
async def create_unit_controller(
    db: Session, payload: UnitCreateSchema
) -> UnitResponseSchema:
    '''
        Creates a unit of measure.
    '''
    try:
        record = create_record(db, Unit, payload)
        db.commit()
        return UnitResponseSchema.model_validate(record)
    except IntegrityError as exc:
        db.rollback()
        raise RegisterAlreadyExistsError(
            detail = f'Unit code "{payload.code}" already exists.'
        ) from exc


async def list_units_controller(
    db: Session, skip: int = 0, limit: int = 100
) -> List[UnitResponseSchema]:
    '''
        Returns a paginated list of units of measure.
    '''
    rows = get_all_records_paginated(db, Unit, skip = skip, limit = limit)
    return [UnitResponseSchema.model_validate(row) for row in rows]


async def update_unit_controller(
    db: Session, unit_id: int, payload: UnitUpdateSchema
) -> UnitResponseSchema:
    '''
        Partial update of a unit of measure.
    '''
    record = get_record(db, Unit, unit_id)
    updated = update_record(db, record, payload)
    db.commit()
    return UnitResponseSchema.model_validate(updated)


async def delete_unit_controller(db: Session, unit_id: int) -> int:
    '''
        Hard-deletes a unit of measure.
    '''
    delete_record(db, Unit, unit_id)
    db.commit()
    return unit_id


# --------------------------------------------------------------------------- #
# Item                                                                        #
# --------------------------------------------------------------------------- #
async def create_item_controller(
    db: Session, payload: ItemCreateSchema
) -> ItemResponseSchema:
    '''
        Creates an item with current_stock = 0. Stock arrives via the kardex.
    '''
    # Validate FKs upfront for a clearer 404 instead of an IntegrityError.
    get_record(db, Category, payload.category_id)
    get_record(db, Unit, payload.unit_id)

    try:
        record = create_record(db, Item, payload, extra_fields = {'current_stock': 0})
        db.commit()
        return ItemResponseSchema.model_validate(record)
    except IntegrityError as exc:
        db.rollback()
        raise RegisterAlreadyExistsError(
            detail = f'Item code "{payload.code}" already exists.'
        ) from exc


async def list_items_controller(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    only_available: bool = False,
) -> List[ItemResponseSchema]:
    '''
        Lists items, optionally filtered by free-text search on code/name
        and a flag to exclude items that are at or below the minimum stock.
    '''
    query = db.query(Item)
    if search:
        like_pattern = f'%{search}%'
        query = query.filter(
            (Item.code.ilike(like_pattern)) | (Item.name.ilike(like_pattern))
        )
    if only_available:
        query = query.filter(Item.current_stock > Item.min_stock,
                             Item.is_active.is_(True))

    rows = query.offset(skip).limit(limit).all()
    return [ItemResponseSchema.model_validate(row) for row in rows]


async def get_item_controller(db: Session, item_id: int) -> ItemResponseSchema:
    '''
        Returns a single item by id.
    '''
    record = get_record(db, Item, item_id)
    return ItemResponseSchema.model_validate(record)


async def update_item_controller(
    db: Session, item_id: int, payload: ItemUpdateSchema
) -> ItemResponseSchema:
    '''
        Partial update of an item's descriptive fields (no stock changes).
    '''
    record = get_record(db, Item, item_id)
    if payload.category_id is not None:
        get_record(db, Category, payload.category_id)
    if payload.unit_id is not None:
        get_record(db, Unit, payload.unit_id)
    updated = update_record(db, record, payload)
    db.commit()
    return ItemResponseSchema.model_validate(updated)


async def update_item_parameters_controller(
    db: Session, item_id: int, payload: ItemParametersUpdateSchema
) -> ItemResponseSchema:
    '''
        Updates the replenishment parameters (min_stock and/or default qty).
        Isolated from the main update to keep the audit trail explicit.
    '''
    record = get_record(db, Item, item_id)
    updated = update_record(db, record, payload)
    db.commit()
    return ItemResponseSchema.model_validate(updated)


async def delete_item_controller(db: Session, item_id: int) -> int:
    '''
        Soft-deletes by deactivating. Hard delete is rejected because
        kardex history must be preserved.
    '''
    record = get_record(db, Item, item_id)
    record.is_active = False
    db.add(record)
    db.commit()
    return item_id


# --------------------------------------------------------------------------- #
# System parameter                                                            #
# --------------------------------------------------------------------------- #
async def upsert_parameter_controller(
    db: Session, payload: SystemParameterUpsertSchema, updated_by: str
) -> SystemParameterResponseSchema:
    '''
        Creates or updates a system parameter keyed by `key`.
    '''
    existing = db.query(SystemParameter).filter(SystemParameter.key == payload.key).first()
    if existing:
        existing.value = payload.value
        existing.description = payload.description
        existing.updated_by = updated_by
        existing.updated_at = get_current_time_gmt()
        db.add(existing)
        db.commit()
        return SystemParameterResponseSchema.model_validate(existing)

    record = SystemParameter(
        key = payload.key,
        value = payload.value,
        description = payload.description,
        updated_by = updated_by,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return SystemParameterResponseSchema.model_validate(record)


async def list_parameters_controller(db: Session) -> List[SystemParameterResponseSchema]:
    '''
        Returns all system parameters.
    '''
    rows = db.query(SystemParameter).order_by(SystemParameter.key.asc()).all()
    return [SystemParameterResponseSchema.model_validate(row) for row in rows]


async def get_parameter_controller(db: Session, key: str) -> SystemParameterResponseSchema:
    '''
        Returns a single parameter by key.
    '''
    record = db.query(SystemParameter).filter(SystemParameter.key == key).first()
    if not record:
        raise RegisterNotFoundError(detail = f'System parameter "{key}" not found.')
    logger.debug(f'Parameter {key} = {record.value}')
    return SystemParameterResponseSchema.model_validate(record)
