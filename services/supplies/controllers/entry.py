'''
    Controllers for warehouse entries (Nota de Ingreso).

    Registering an entry creates its detail lines (each a PEPS/FIFO cost layer)
    and posts one valued kardex IN movement per line, so stock and valuation
    stay in lock-step with the source document.
'''
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from models.supplies import Entry, EntryDetail, Supplier
from schemas.entry import (
    EntryCreateSchema,
    EntryDetailedResponseSchema,
    EntryDetailResponseSchema,
    EntryFilterSchema,
    EntryResponseSchema,
)
from schemas.enums import MovementTypeEnum, ReferenceTypeEnum
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.supplies_logic import (
    CostLayer,
    MovementReference,
    MovementSpec,
    commit_or_conflict,
    fetch_active_item,
    post_kardex_movement,
)


def _generate_entry_code(db: Session) -> str:
    '''
        Builds ING-YYYY-NNNNNN codes for warehouse entries.
    '''
    last = db.query(Entry).order_by(Entry.id.desc()).first()
    next_id = (last.id + 1) if last else 1
    year = datetime.now().year
    return f'ING-{year}-{next_id:06d}'


def _serialize_detail(detail: EntryDetail) -> EntryDetailResponseSchema:
    '''
        Enriches an entry line with item code, name and unit for display.
    '''
    return EntryDetailResponseSchema(
        id = detail.id,
        item_id = detail.item_id,
        item_code = detail.item.code,
        item_name = detail.item.name,
        unit = detail.item.unit.abbreviation if detail.item.unit else '',
        qty_initial = detail.qty_initial,
        qty_remaining = detail.qty_remaining,
        unit_cost = detail.unit_cost,
        total_cost = detail.total_cost,
    )


def _serialize_detailed(record: Entry) -> EntryDetailedResponseSchema:
    '''
        Full entry with its detail lines.
    '''
    return EntryDetailedResponseSchema(
        **EntryResponseSchema.model_validate(record).model_dump(),
        details = [_serialize_detail(detail) for detail in record.details],
    )


def _resolve_supplier(db: Session, payload: EntryCreateSchema) -> Optional[Supplier]:
    '''
        Resolves the registered supplier a note is issued against.

        Args:
            db (Session): Active database session.
            payload (EntryCreateSchema): Incoming note; supplier_id is optional
                so notes without a vendor (reingreso) stay valid.

        Returns:
            Optional[Supplier]: The supplier, or None when none was declared.

        Raises:
            RegisterNotFoundError: If the id does not exist.
            InvalidInputError: If the supplier is deactivated.
    '''
    if payload.supplier_id is None:
        return None

    record = db.query(Supplier).filter(Supplier.id == payload.supplier_id).first()
    if record is None:
        raise RegisterNotFoundError(detail = f'Supplier {payload.supplier_id} not found.')
    if not record.is_active:
        raise InvalidInputError(
            detail = f'Supplier "{record.name}" is deactivated and cannot receive new notes.'
        )
    return record


async def create_entry_controller(
    db: Session, payload: EntryCreateSchema, created_by: str
) -> EntryDetailedResponseSchema:
    '''
        Registers a Nota de Ingreso: creates the header, one cost layer per
        detail line, and the matching valued kardex IN movements.
    '''
    subtotal = sum((line.quantity * line.unit_cost for line in payload.details), Decimal('0'))
    if payload.discount > subtotal:
        raise InvalidInputError(
            detail = f'Discount ({payload.discount}) cannot exceed the subtotal ({subtotal}).'
        )

    supplier = _resolve_supplier(db, payload)
    record = Entry(
        code = _generate_entry_code(db),
        entry_type = payload.entry_type,
        supplier_id = supplier.id if supplier else None,
        supplier = supplier.name if supplier else payload.supplier,
        requirement_no = payload.requirement_no,
        requirement_date = payload.requirement_date,
        delivery_note = payload.delivery_note,
        delivery_note_date = payload.delivery_note_date,
        invoice_no = payload.invoice_no,
        authorization = payload.authorization,
        invoice_date = payload.invoice_date,
        observations = payload.observations,
        discount = payload.discount,
        subtotal = subtotal,
        total = subtotal - payload.discount,
        created_by = created_by,
    )
    db.add(record)
    db.flush()

    for line in payload.details:
        item = fetch_active_item(db, line.item_id)
        detail = EntryDetail(
            entry_id = record.id,
            item_id = item.id,
            qty_initial = line.quantity,
            qty_remaining = line.quantity,
            unit_cost = line.unit_cost,
            total_cost = line.quantity * line.unit_cost,
        )
        db.add(detail)
        db.flush()

        post_kardex_movement(db, item, MovementSpec(
            movement_type = MovementTypeEnum.IN,
            reference = MovementReference(
                kind = ReferenceTypeEnum.ENTRY, identifier = record.id),
            quantity = line.quantity,
            created_by = created_by,
            notes = f'Nota de Ingreso {record.code}',
            layer = CostLayer(
                unit_cost = line.unit_cost,
                entry_id = record.id,
                entry_detail_id = detail.id,
            ),
        ))

    commit_or_conflict(db, 'Entry code collision; retry the request.')

    db.refresh(record)
    message = (f'Entry {record.code} registered by {created_by} '
               f'with {len(payload.details)} lines.')
    logger.info(message)
    return _serialize_detailed(record)


async def list_entries_controller(
    db: Session, filters: EntryFilterSchema
) -> List[EntryResponseSchema]:
    '''
        Lists entry headers with optional type and date-range filters.
    '''
    query = db.query(Entry)
    if filters.entry_type:
        query = query.filter(Entry.entry_type == filters.entry_type)
    if filters.date_from:
        query = query.filter(Entry.created_at >= filters.date_from)
    if filters.date_to:
        query = query.filter(Entry.created_at <= filters.date_to)

    rows = (
        query.order_by(Entry.created_at.desc())
        .offset(filters.skip)
        .limit(filters.limit)
        .all()
    )
    return [EntryResponseSchema.model_validate(row) for row in rows]


async def get_entry_controller(db: Session, entry_id: int) -> EntryDetailedResponseSchema:
    '''
        Returns a single entry with its detail lines.
    '''
    record = (
        db.query(Entry)
        .options(joinedload(Entry.details).joinedload(EntryDetail.item))
        .filter(Entry.id == entry_id)
        .first()
    )
    if record is None:
        raise RegisterNotFoundError(detail = f'Entry {entry_id} not found.')
    return _serialize_detailed(record)
