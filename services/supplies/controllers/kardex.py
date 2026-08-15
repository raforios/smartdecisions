'''
    Controllers for kardex queries, manual adjustments and operational reports.
'''
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from models.supplies import Entry, Item, KardexMovement, Request
from schemas.enums import (
    MovementTypeEnum,
    ReferenceTypeEnum,
    RequestStatusEnum,
)
from schemas.kardex import (
    EntryReportRowSchema,
    KardexAdjustmentSchema,
    KardexFilterSchema,
    KardexMovementResponseSchema,
    LowStockItemSchema,
    RequestReportRowSchema,
)
from services.crud import get_record
from services.report_rows import build_entry_rows, build_request_rows
from services.supplies_logic import MovementReference, MovementSpec, post_kardex_movement


# --------------------------------------------------------------------------- #
# Kardex queries                                                              #
# --------------------------------------------------------------------------- #
async def list_kardex_for_item_controller(
    db: Session, item_id: int, filters: KardexFilterSchema
) -> List[KardexMovementResponseSchema]:
    '''
        Returns the kardex movements for a single item, optionally bounded by
        a date range. Ordered descending by creation time for UI convenience.
    '''
    get_record(db, Item, item_id)
    query = db.query(KardexMovement).filter(KardexMovement.item_id == item_id)
    if filters.date_from:
        query = query.filter(KardexMovement.created_at >= filters.date_from)
    if filters.date_to:
        query = query.filter(KardexMovement.created_at <= filters.date_to)

    rows = (
        query.order_by(KardexMovement.created_at.desc())
        .offset(filters.skip)
        .limit(filters.limit)
        .all()
    )
    return [KardexMovementResponseSchema.model_validate(r) for r in rows]


async def create_manual_adjustment_controller(
    db: Session, payload: KardexAdjustmentSchema, created_by: str
) -> KardexMovementResponseSchema:
    '''
        Records a manual ADJUSTMENT against an item. Positive deltas add
        stock, negative deltas subtract; both produce a new append-only row.
    '''
    item = get_record(db, Item, payload.item_id)
    movement = post_kardex_movement(db, item, MovementSpec(
        movement_type = MovementTypeEnum.ADJUSTMENT,
        reference = MovementReference(kind = ReferenceTypeEnum.MANUAL),
        quantity = payload.quantity,
        created_by = created_by,
        notes = payload.notes,
    ))
    db.commit()
    db.refresh(movement)
    return KardexMovementResponseSchema.model_validate(movement)


# --------------------------------------------------------------------------- #
# Reports                                                                     #
# --------------------------------------------------------------------------- #
async def list_low_stock_controller(db: Session) -> List[LowStockItemSchema]:
    '''
        Items that are below or at the configured minimum, with the deficit
        precomputed so the UI doesn't need to recalculate.
    '''
    rows = (
        db.query(Item)
        .filter(Item.is_active.is_(True))
        .filter(Item.current_stock <= Item.min_stock)
        .order_by(Item.code.asc())
        .all()
    )
    return [
        LowStockItemSchema(
            item_id = item.id,
            item_code = item.code,
            item_name = item.name,
            current_stock = item.current_stock,
            min_stock = item.min_stock,
            deficit = (item.min_stock - item.current_stock),
        )
        for item in rows
    ]


async def entries_report_controller(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[EntryReportRowSchema]:
    '''
        Aggregated entries (Notas de Ingreso) report optionally bounded by
        created_at, with the number of lines per entry.
    '''
    query = db.query(Entry)
    if date_from:
        query = query.filter(Entry.created_at >= date_from)
    if date_to:
        query = query.filter(Entry.created_at <= date_to)

    return build_entry_rows(db, query.order_by(Entry.created_at.desc()).all())


async def request_report_controller(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    status: Optional[RequestStatusEnum] = None,
) -> List[RequestReportRowSchema]:
    '''
        Aggregated requests report, with line count per request.
    '''
    query = db.query(Request)
    if date_from:
        query = query.filter(Request.requested_at >= date_from)
    if date_to:
        query = query.filter(Request.requested_at <= date_to)
    if status:
        query = query.filter(Request.status == status)

    return build_request_rows(db, query.order_by(Request.requested_at.desc()).all())
