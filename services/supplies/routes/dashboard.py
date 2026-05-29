'''
    Dashboard routes. Returns KPI snapshots and the latest activity feed.
'''
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from controllers.dashboard import (
    dashboard_recent_activity_controller,
    dashboard_summary_controller,
)
from schemas.enums import RoleEnum
from schemas.kardex import DashboardRecentActivitySchema, DashboardSummarySchema
from services.db_connection import GET_DB_DEPENDENCY
from services.security import require_roles


router = APIRouter(prefix = '/v1/supplies', tags = ['Dashboard'])


@router.get(
    '/dashboard/summary',
    response_model = DashboardSummarySchema,
    summary = 'Top-level KPIs for the supplies dashboard',
)
async def dashboard_summary(
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Returns the dashboard KPIs (items, requests, replenishments).
    '''
    return await dashboard_summary_controller(db)


@router.get(
    '/dashboard/recent-activity',
    response_model = DashboardRecentActivitySchema,
    summary = 'Most recent requests, replenishments and kardex movements',
)
async def dashboard_recent_activity(
    limit: int = Query(10, ge = 1, le = 50),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Returns the latest activity to render the dashboard feed.
    '''
    return await dashboard_recent_activity_controller(db, limit = limit)
