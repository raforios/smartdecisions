'''
    Controllers for replenishments and receptions.

    A replenishment is a single, independent order against an external
    purchasing system. Each reception against it is also independent,
    carrying its own batch, supplier and invoice metadata so the trail can
    be reconstructed item-by-item.
'''
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from models.supplies import Item, Reception, Replenishment
from schemas.enums import (
    MovementTypeEnum,
    ReferenceTypeEnum,
    ReplenishmentStatusEnum,
)
from schemas.replenishment import (
    ReceptionCreateSchema,
    ReceptionResponseSchema,
    ReplenishmentBulkCreateSchema,
    ReplenishmentCreateSchema,
    ReplenishmentResponseSchema,
    ReplenishmentSuggestionSchema,
)
from services.crud import get_record
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError,
)
from services.logger_config import custom_logger as logger
from services.supplies_logic import fetch_active_item, post_kardex_movement
from services.utils import get_current_time_gmt


def _generate_code(prefix: str, db: Session, model) -> str:
    '''
        Builds a human-friendly code like REP-2026-000123 / REC-2026-000123.

        The counter is monotonically increasing by inspecting the highest id
        in the table. Good enough for a low-throughput admin workload; can be
        swapped for a dedicated sequence later without changing call sites.
    '''
    last = db.query(model).order_by(model.id.desc()).first()
    next_id = (last.id + 1) if last else 1
    year = datetime.now().year
    return f'{prefix}-{year}-{next_id:06d}'


# --------------------------------------------------------------------------- #
# Pending suggestion                                                          #
# --------------------------------------------------------------------------- #
async def list_pending_suggestions_controller(
    db: Session,
) -> List[ReplenishmentSuggestionSchema]:
    '''
        Returns the list of items that are at or below their minimum stock,
        with the suggested replenishment quantity taken from each item's
        default value (falling back to the deficit if the default is zero).
    '''
    rows = (
        db.query(Item)
        .filter(Item.is_active.is_(True))
        .filter(Item.current_stock <= Item.min_stock)
        .all()
    )

    suggestions: List[ReplenishmentSuggestionSchema] = []
    for item in rows:
        suggested = item.default_replenishment_qty
        if suggested <= 0:
            suggested = (item.min_stock - item.current_stock) or Decimal('1')
        suggestions.append(
            ReplenishmentSuggestionSchema(
                item_id = item.id,
                item_code = item.code,
                item_name = item.name,
                current_stock = item.current_stock,
                min_stock = item.min_stock,
                suggested_qty = suggested,
            )
        )
    return suggestions


# --------------------------------------------------------------------------- #
# Replenishment CRUD                                                          #
# --------------------------------------------------------------------------- #
async def create_replenishment_controller(
    db: Session, payload: ReplenishmentCreateSchema, created_by: str
) -> ReplenishmentResponseSchema:
    '''
        Creates a single replenishment order.
    '''
    item = fetch_active_item(db, payload.item_id)

    qty = payload.requested_qty or item.default_replenishment_qty
    if qty is None or qty <= 0:
        raise InvalidInputError(
            detail = (
                f'No requested_qty was provided and item {item.code} has no '
                f'default_replenishment_qty configured.'
            )
        )

    record = Replenishment(
        code = _generate_code('REP', db, Replenishment),
        item_id = item.id,
        requested_qty = qty,
        received_qty = Decimal('0'),
        status = ReplenishmentStatusEnum.REQUESTED,
        supplier_hint = payload.supplier_hint,
        notes = payload.notes,
        created_by = created_by,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RegisterAlreadyExistsError(
            detail = 'Replenishment code collision; retry the request.'
        ) from exc
    db.refresh(record)
    return ReplenishmentResponseSchema.model_validate(record)


async def create_replenishments_bulk_controller(
    db: Session, payload: ReplenishmentBulkCreateSchema, created_by: str
) -> List[ReplenishmentResponseSchema]:
    '''
        Creates several replenishment orders in a single round-trip,
        typically right after consuming /replenishments/pending.
    '''
    created: List[Replenishment] = []
    for entry in payload.items:
        item = fetch_active_item(db, entry.item_id)
        qty = entry.requested_qty or item.default_replenishment_qty
        if qty is None or qty <= 0:
            raise InvalidInputError(
                detail = (
                    f'No requested_qty was provided and item {item.code} has no '
                    f'default_replenishment_qty configured.'
                )
            )
        record = Replenishment(
            code = _generate_code('REP', db, Replenishment),
            item_id = item.id,
            requested_qty = qty,
            received_qty = Decimal('0'),
            status = ReplenishmentStatusEnum.REQUESTED,
            supplier_hint = entry.supplier_hint,
            notes = entry.notes,
            created_by = created_by,
        )
        db.add(record)
        # Flush so the next iteration sees the new id when generating codes.
        db.flush()
        created.append(record)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RegisterAlreadyExistsError(
            detail = 'Replenishment code collision in bulk creation; retry.'
        ) from exc

    return [ReplenishmentResponseSchema.model_validate(r) for r in created]


async def list_replenishments_controller(
    db: Session,
    status: Optional[ReplenishmentStatusEnum] = None,
    item_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[ReplenishmentResponseSchema]:
    '''
        Lists replenishments with optional status and item filters.
    '''
    query = db.query(Replenishment)
    if status:
        query = query.filter(Replenishment.status == status)
    if item_id:
        query = query.filter(Replenishment.item_id == item_id)
    rows = (
        query.order_by(Replenishment.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [ReplenishmentResponseSchema.model_validate(r) for r in rows]


async def get_replenishment_controller(
    db: Session, replenishment_id: int
) -> ReplenishmentResponseSchema:
    '''
        Returns a single replenishment by id.
    '''
    record = get_record(db, Replenishment, replenishment_id)
    return ReplenishmentResponseSchema.model_validate(record)


async def cancel_replenishment_controller(
    db: Session, replenishment_id: int, reason: Optional[str]
) -> ReplenishmentResponseSchema:
    '''
        Cancels a replenishment that has not yet been received.
    '''
    record = get_record(db, Replenishment, replenishment_id)
    if record.status not in (ReplenishmentStatusEnum.REQUESTED,):
        raise InvalidInputError(
            detail = (
                f'Only REQUESTED replenishments can be cancelled. Current '
                f'status: {record.status.value}.'
            )
        )
    record.status = ReplenishmentStatusEnum.CANCELLED
    record.notes = (record.notes or '') + (f'\nCancelled: {reason}' if reason else '\nCancelled')
    db.add(record)
    db.commit()
    db.refresh(record)
    return ReplenishmentResponseSchema.model_validate(record)


# --------------------------------------------------------------------------- #
# Reception                                                                   #
# --------------------------------------------------------------------------- #
async def create_reception_controller(
    db: Session,
    replenishment_id: int,
    payload: ReceptionCreateSchema,
    received_by: str,
) -> ReceptionResponseSchema:
    '''
        Registers a physical reception against an existing replenishment,
        posts the matching kardex IN movement, and advances the
        replenishment status if the cumulative received quantity reaches
        the requested total.
    '''
    replenishment = (
        db.query(Replenishment)
        .options(joinedload(Replenishment.item))
        .filter(Replenishment.id == replenishment_id)
        .first()
    )
    if replenishment is None:
        raise RegisterNotFoundError(
            detail = f'Replenishment {replenishment_id} not found.'
        )
    if replenishment.status in (ReplenishmentStatusEnum.CANCELLED,
                                ReplenishmentStatusEnum.COMPLETED):
        raise InvalidInputError(
            detail = (
                f'Cannot register receptions on a {replenishment.status.value} '
                f'replenishment.'
            )
        )

    item = replenishment.item
    reception = Reception(
        replenishment_id = replenishment.id,
        received_qty = payload.received_qty,
        batch_code = payload.batch_code,
        expiration_date = payload.expiration_date,
        supplier_name = payload.supplier_name,
        invoice_number = payload.invoice_number,
        file_key = payload.file_key,
        notes = payload.notes,
        received_by = received_by,
    )
    db.add(reception)
    db.flush()

    post_kardex_movement(
        db = db,
        item = item,
        movement_type = MovementTypeEnum.IN,
        reference_type = ReferenceTypeEnum.REPLENISHMENT,
        reference_id = replenishment.id,
        quantity = payload.received_qty,
        created_by = received_by,
        batch_code = payload.batch_code,
        notes = f'Reception #{reception.id} on replenishment {replenishment.code}',
    )

    replenishment.received_qty = Decimal(replenishment.received_qty) + payload.received_qty
    if replenishment.received_qty >= replenishment.requested_qty:
        replenishment.status = ReplenishmentStatusEnum.COMPLETED
        replenishment.completed_at = get_current_time_gmt()
    else:
        replenishment.status = ReplenishmentStatusEnum.IN_RECEPTION

    db.add(replenishment)
    db.commit()
    db.refresh(reception)
    logger.info(
        f'Reception {reception.id} registered on replenishment {replenishment.code}; '
        f'replenishment status -> {replenishment.status.value}.'
    )
    return ReceptionResponseSchema.model_validate(reception)


async def list_receptions_controller(
    db: Session, replenishment_id: int
) -> List[ReceptionResponseSchema]:
    '''
        Lists all receptions registered against a replenishment.
    '''
    get_record(db, Replenishment, replenishment_id)
    rows = (
        db.query(Reception)
        .filter(Reception.replenishment_id == replenishment_id)
        .order_by(Reception.received_at.asc())
        .all()
    )
    return [ReceptionResponseSchema.model_validate(r) for r in rows]
