'''
    Controllers for suppliers (proveedores).

    Suppliers are referenced by every Nota de Ingreso, so removal is soft by
    default: deactivating hides a vendor from the pickers while the documents
    it issued keep resolving.
'''
from typing import List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.supplies import Entry, Supplier
from schemas.supplier import (
    SupplierCreateSchema,
    SupplierFilterSchema,
    SupplierResponseSchema,
    SupplierUpdateSchema,
)
from services.crud import create_record, get_record, update_record
from services.exceptions import InvalidInputError, RegisterAlreadyExistsError
from services.logger_config import custom_logger as logger


async def create_supplier_controller(
    db: Session, payload: SupplierCreateSchema
) -> SupplierResponseSchema:
    '''
        Registers a supplier.

        Args:
            db (Session): Active database session.
            payload (SupplierCreateSchema): Supplier data; NIT must be unique.

        Returns:
            SupplierResponseSchema: The stored supplier.

        Raises:
            RegisterAlreadyExistsError: If the NIT is already registered.
    '''
    try:
        record = create_record(db, Supplier, payload)
        db.commit()
        message = f'Supplier {record.name} (NIT {record.nit}) created.'
        logger.info(message)
        return SupplierResponseSchema.model_validate(record)
    except IntegrityError as exc:
        db.rollback()
        raise RegisterAlreadyExistsError(
            detail = f'A supplier with NIT "{payload.nit}" already exists.'
        ) from exc


async def list_suppliers_controller(
    db: Session, filters: SupplierFilterSchema
) -> List[SupplierResponseSchema]:
    '''
        Lists suppliers ordered by name, which is how the Nota de Ingreso
        picker presents them.

        Args:
            db (Session): Active database session.
            filters (SupplierFilterSchema): Free text, active flag and paging.

        Returns:
            List[SupplierResponseSchema]: Matching suppliers.
    '''
    query = db.query(Supplier)
    if filters.search:
        like_pattern = f'%{filters.search}%'
        query = query.filter(
            (Supplier.name.ilike(like_pattern))
            | (Supplier.nit.ilike(like_pattern))
            | (Supplier.contact_person.ilike(like_pattern))
        )
    if filters.only_active:
        query = query.filter(Supplier.is_active.is_(True))

    rows = (
        query.order_by(Supplier.name.asc())
        .offset(filters.skip)
        .limit(filters.limit)
        .all()
    )
    return [SupplierResponseSchema.model_validate(row) for row in rows]


async def get_supplier_controller(db: Session, supplier_id: int) -> SupplierResponseSchema:
    '''
        Returns a single supplier by id.
    '''
    record = get_record(db, Supplier, supplier_id)
    return SupplierResponseSchema.model_validate(record)


async def update_supplier_controller(
    db: Session, supplier_id: int, payload: SupplierUpdateSchema
) -> SupplierResponseSchema:
    '''
        Partial update of a supplier.

        Raises:
            RegisterAlreadyExistsError: If the new NIT belongs to another
                supplier.
    '''
    record = get_record(db, Supplier, supplier_id)
    try:
        updated = update_record(db, record, payload)
        db.commit()
        return SupplierResponseSchema.model_validate(updated)
    except IntegrityError as exc:
        db.rollback()
        raise RegisterAlreadyExistsError(
            detail = f'A supplier with NIT "{payload.nit}" already exists.'
        ) from exc


async def delete_supplier_controller(db: Session, supplier_id: int) -> int:
    '''
        Deletes a supplier that never issued a Nota de Ingreso.

        A vendor with entries is history: removing it would orphan signed
        documents, so those must be deactivated instead.

        Args:
            db (Session): Active database session.
            supplier_id (int): Supplier to remove.

        Returns:
            int: The removed supplier id.

        Raises:
            InvalidInputError: If the supplier already has entries.
    '''
    record = get_record(db, Supplier, supplier_id)
    used = db.query(Entry).filter(Entry.supplier_id == supplier_id).count()
    if used:
        raise InvalidInputError(
            detail = (
                f'Supplier "{record.name}" has {used} entry document(s) and '
                f'cannot be deleted. Deactivate it instead.'
            )
        )
    db.delete(record)
    db.commit()
    return supplier_id
