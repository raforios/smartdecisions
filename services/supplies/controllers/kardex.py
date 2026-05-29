'''
    Controllers for kardex queries, manual adjustments and operational reports.
'''
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.supplies import (
    Item,
    KardexMovement,
    Replenishment,
    Request,
    RequestDetail,
)
from schemas.enums import (
    MovementTypeEnum,
    ReferenceTypeEnum,
    RequestStatusEnum,
)
from schemas.kardex import (
    KardexAdjustmentSchema,
    KardexMovementResponseSchema,
    LowStockItemSchema,
    ReplenishmentReportRowSchema,
    RequestReportRowSchema,
)
from services.crud import get_record
from services.exceptions import RegisterNotFoundError
from services.supplies_logic import post_kardex_movement


# --------------------------------------------------------------------------- #
# Kardex queries                                                              #
# --------------------------------------------------------------------------- #
async def list_kardex_for_item_controller(
    db: Session,
    item_id: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 200,
) -> List[KardexMovementResponseSchema]:
    '''
        Returns the kardex movements for a single item, optionally bounded by
        a date range. Ordered descending by creation time for UI convenience.
    '''
    get_record(db, Item, item_id)
    query = db.query(KardexMovement).filter(KardexMovement.item_id == item_id)
    if date_from:
        query = query.filter(KardexMovement.created_at >= date_from)
    if date_to:
        query = query.filter(KardexMovement.created_at <= date_to)

    rows = (
        query.order_by(KardexMovement.created_at.desc())
        .offset(skip)
        .limit(limit)
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
    movement = post_kardex_movement(
        db = db,
        item = item,
        movement_type = MovementTypeEnum.ADJUSTMENT,
        reference_type = ReferenceTypeEnum.MANUAL,
        reference_id = None,
        quantity = payload.quantity,
        created_by = created_by,
        notes = payload.notes,
    )
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


async def replenishment_report_controller(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> List[ReplenishmentReportRowSchema]:
    '''
        Aggregated replenishments report optionally bounded by created_at.
    '''
    query = db.query(Replenishment, Item).join(Item, Replenishment.item_id == Item.id)
    if date_from:
        query = query.filter(Replenishment.created_at >= date_from)
    if date_to:
        query = query.filter(Replenishment.created_at <= date_to)

    rows = query.order_by(Replenishment.created_at.desc()).all()
    return [
        ReplenishmentReportRowSchema(
            replenishment_id = rep.id,
            code = rep.code,
            item_id = item.id,
            item_code = item.code,
            requested_qty = rep.requested_qty,
            received_qty = rep.received_qty,
            status = rep.status.value if hasattr(rep.status, 'value') else str(rep.status),
            created_at = rep.created_at,
            completed_at = rep.completed_at,
        )
        for rep, item in rows
    ]


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

    rows = query.order_by(Request.requested_at.desc()).all()

    # Count details per request in one query to avoid N+1 lookups.
    request_ids = [r.id for r in rows]
    counts: dict[int, int] = {}
    if request_ids:
        for request_id, count in (
            db.query(RequestDetail.request_id, func.count(RequestDetail.id))
            .filter(RequestDetail.request_id.in_(request_ids))
            .group_by(RequestDetail.request_id)
            .all()
        ):
            counts[request_id] = count

    return [
        RequestReportRowSchema(
            request_id = r.id,
            code = r.code,
            requester_email = r.requester_email,
            status = r.status,
            total_items = counts.get(r.id, 0),
            requested_at = r.requested_at,
            closed_at = r.closed_at,
        )
        for r in rows
    ]
