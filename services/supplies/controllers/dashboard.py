'''
    Dashboard controller. Aggregates KPIs and recent-activity feeds.
'''
from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from models.supplies import Entry, Item, KardexMovement
from schemas.kardex import (
    DashboardRecentActivitySchema,
    DashboardSummarySchema,
    KardexMovementResponseSchema,
)
from services.report_rows import build_entry_rows
from services.utils import get_current_time_gmt

# SQLAlchemy builds `func.count` dynamically, which Pylint cannot resolve and
# reports as not-callable. The call is correct; the checker is not.
# pylint: disable=not-callable


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

    total_entries = db.query(func.count(Entry.id)).scalar() or 0
    since = get_current_time_gmt() - timedelta(days = 30)
    entries_last_30_days = (
        db.query(func.count(Entry.id))
        .filter(Entry.created_at >= since)
        .scalar() or 0
    )

    return DashboardSummarySchema(
        total_items = total_items,
        active_items = active_items,
        items_below_min = items_below_min,
        total_entries = total_entries,
        entries_last_30_days = entries_last_30_days,
    )


async def dashboard_recent_activity_controller(
    db: Session, limit: int = 10
) -> DashboardRecentActivitySchema:
    '''
        Returns the most recent entries and kardex movements.
        Useful for the operations feed on the dashboard.
    '''
    entries = (
        db.query(Entry)
        .order_by(Entry.created_at.desc())
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
        recent_entries = build_entry_rows(db, entries),
        recent_movements = [
            KardexMovementResponseSchema.model_validate(m) for m in movements
        ],
    )
