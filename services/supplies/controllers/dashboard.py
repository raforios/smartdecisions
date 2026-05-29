'''
    Dashboard controller. Aggregates KPIs and recent-activity feeds.
'''
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
    ReplenishmentStatusEnum,
    RequestStatusEnum,
)
from schemas.kardex import (
    KardexMovementResponseSchema,
    ReplenishmentReportRowSchema,
    RequestReportRowSchema,
)
from schemas.kardex import DashboardRecentActivitySchema, DashboardSummarySchema


async def dashboard_summary_controller(db: Session) -> DashboardSummarySchema:
    '''
        Returns the top-level KPIs shown on the dashboard's hero section.

        All counters are computed via aggregated queries to keep latency low
        even when the operation tables grow.
    '''
    total_items = db.query(func.count(Item.id)).scalar() or 0
    active_items = db.query(func.count(Item.id)).filter(Item.is_active.is_(True)).scalar() or 0
    items_below_min = (
        db.query(func.count(Item.id))
        .filter(Item.is_active.is_(True))
        .filter(Item.current_stock <= Item.min_stock)
        .scalar() or 0
    )

    open_requests = (
        db.query(func.count(Request.id))
        .filter(Request.status.in_([
            RequestStatusEnum.CREATED,
            RequestStatusEnum.IN_PROCESS,
            RequestStatusEnum.DELIVERED,
        ]))
        .scalar() or 0
    )
    requests_in_process = (
        db.query(func.count(Request.id))
        .filter(Request.status == RequestStatusEnum.IN_PROCESS)
        .scalar() or 0
    )
    requests_delivered_pending_close = (
        db.query(func.count(Request.id))
        .filter(Request.status == RequestStatusEnum.DELIVERED)
        .scalar() or 0
    )

    pending_replenishments = (
        db.query(func.count(Replenishment.id))
        .filter(Replenishment.status == ReplenishmentStatusEnum.REQUESTED)
        .scalar() or 0
    )
    in_reception_replenishments = (
        db.query(func.count(Replenishment.id))
        .filter(Replenishment.status == ReplenishmentStatusEnum.IN_RECEPTION)
        .scalar() or 0
    )

    return DashboardSummarySchema(
        total_items = total_items,
        active_items = active_items,
        items_below_min = items_below_min,
        open_requests = open_requests,
        requests_in_process = requests_in_process,
        requests_delivered_pending_close = requests_delivered_pending_close,
        pending_replenishments = pending_replenishments,
        in_reception_replenishments = in_reception_replenishments,
    )


async def dashboard_recent_activity_controller(
    db: Session, limit: int = 10
) -> DashboardRecentActivitySchema:
    '''
        Returns the most recent requests, replenishments and kardex
        movements. Useful for the operations feed on the dashboard.
    '''
    requests = (
        db.query(Request)
        .order_by(Request.requested_at.desc())
        .limit(limit)
        .all()
    )
    # Counts of detail lines per recent request for the report row schema.
    request_ids = [r.id for r in requests]
    counts: dict[int, int] = {}
    if request_ids:
        for request_id, count in (
            db.query(RequestDetail.request_id, func.count(RequestDetail.id))
            .filter(RequestDetail.request_id.in_(request_ids))
            .group_by(RequestDetail.request_id)
            .all()
        ):
            counts[request_id] = count

    replenishments = (
        db.query(Replenishment, Item)
        .join(Item, Replenishment.item_id == Item.id)
        .order_by(Replenishment.created_at.desc())
        .limit(limit)
        .all()
    )

    movements = (
        db.query(KardexMovement)
        .order_by(KardexMovement.created_at.desc())
        .limit(limit)
        .all()
    )

    return DashboardRecentActivitySchema(
        recent_requests = [
            RequestReportRowSchema(
                request_id = r.id,
                code = r.code,
                requester_email = r.requester_email,
                status = r.status,
                total_items = counts.get(r.id, 0),
                requested_at = r.requested_at,
                closed_at = r.closed_at,
            )
            for r in requests
        ],
        recent_replenishments = [
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
            for rep, item in replenishments
        ],
        recent_movements = [
            KardexMovementResponseSchema.model_validate(m) for m in movements
        ],
    )
