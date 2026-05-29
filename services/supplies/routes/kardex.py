'''
    Routes for kardex queries, manual adjustments and operational reports.
'''
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from controllers.kardex import (
    create_manual_adjustment_controller,
    list_kardex_for_item_controller,
    list_low_stock_controller,
    replenishment_report_controller,
    request_report_controller,
)
from schemas.enums import RequestStatusEnum, RoleEnum
from schemas.kardex import (
    KardexAdjustmentSchema,
    KardexMovementResponseSchema,
    LowStockItemSchema,
    ReplenishmentReportRowSchema,
    RequestReportRowSchema,
)
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user, require_roles


router = APIRouter(prefix = '/v1/supplies', tags = ['Kardex'])


@router.get(
    '/kardex/items/{item_id}',
    response_model = List[KardexMovementResponseSchema],
    summary = 'Kardex movements for an item',
)
async def list_kardex(
    item_id: int,
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge = 0),
    limit: int = Query(200, ge = 1, le = 1000),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Returns the kardex ledger for a single item, ordered by most recent.
    '''
    return await list_kardex_for_item_controller(
        db, item_id, date_from = date_from, date_to = date_to,
        skip = skip, limit = limit,
    )


@router.post(
    '/kardex/adjustments',
    response_model = KardexMovementResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register a manual stock adjustment',
)
async def create_adjustment(
    payload: KardexAdjustmentSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(
        require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)
    ),
):
    '''
        Records a manual ADJUSTMENT row. Positive quantities add stock,
        negative quantities subtract.
    '''
    return await create_manual_adjustment_controller(
        db, payload, created_by = current_user,
    )


# --------------------------------------------------------------------------- #
# Reports                                                                     #
# --------------------------------------------------------------------------- #
@router.get(
    '/reports/low-stock',
    response_model = List[LowStockItemSchema],
    summary = 'Items at or below the configured minimum',
)
async def report_low_stock(
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user),
):
    '''
        Aggregated low-stock report.
    '''
    return await list_low_stock_controller(db)


@router.get(
    '/reports/replenishments',
    response_model = List[ReplenishmentReportRowSchema],
    summary = 'Replenishments report bounded by date range',
)
async def report_replenishments(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Returns replenishments enriched with item code, totals and status.
    '''
    return await replenishment_report_controller(
        db, date_from = date_from, date_to = date_to,
    )


@router.get(
    '/reports/requests',
    response_model = List[RequestReportRowSchema],
    summary = 'Requests report bounded by date and status',
)
async def report_requests(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    status_filter: Optional[RequestStatusEnum] = Query(None, alias = 'status'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
):
    '''
        Aggregated requests report with the number of lines per request.
    '''
    return await request_report_controller(
        db, date_from = date_from, date_to = date_to, status = status_filter,
    )
