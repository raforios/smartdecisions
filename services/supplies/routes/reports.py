'''
    Routes for the valued warehouse reports (Inventario, Kardex, Estadísticas).

    All endpoints are read-only and restricted to ADMIN / WAREHOUSE_MANAGER.
'''
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from controllers.reports import (
    in_out_by_group_report_controller,
    kardex_valued_report_controller,
    outflow_report_controller,
    physical_valued_report_controller,
    stock_on_hand_report_controller,
)
from schemas.enums import RoleEnum
from schemas.reports import (
    InOutByGroupReportSchema,
    KardexValuedReportSchema,
    OutflowReportSchema,
    PhysicalValuedReportSchema,
    StockOnHandReportSchema,
)
from services.db_connection import GET_DB_DEPENDENCY
from services.security import require_roles


router = APIRouter(prefix = '/v1/supplies', tags = ['Warehouse reports'])

_ROLES = (RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)


@router.get(
    '/reports/inventory/physical-valued',
    response_model = PhysicalValuedReportSchema,
    summary = 'Inventario General de Almacenes Físico Valorado',
)
async def report_physical_valued(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    group_code: Optional[str] = Query(None, description = 'Filter to a single accounting group.'),
    include_zero: bool = Query(True, description = 'Include items with no movements/stock.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*_ROLES)),
):
    '''
        Physical + valued inventory per accounting group over a date range.
    '''
    return await physical_valued_report_controller(
        db, date_from = date_from, date_to = date_to,
        group_code = group_code, include_zero = include_zero,
    )


@router.get(
    '/reports/inventory/stock-on-hand',
    response_model = StockOnHandReportSchema,
    summary = 'Inventario de Almacenes con Stock Existente',
)
async def report_stock_on_hand(
    group_code: Optional[str] = Query(None, description = 'Filter to a single accounting group.'),
    date_to: Optional[datetime] = Query(
        None, description = 'Cut-off date; omit for the live stock.'),
    include_zero: bool = Query(False, description = 'Include items whose balance is zero.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*_ROLES)),
):
    '''
        Stock valued from PEPS/FIFO layers, grouped by accounting group.
    '''
    return await stock_on_hand_report_controller(
        db, group_code = group_code, date_to = date_to, include_zero = include_zero,
    )


@router.get(
    '/reports/inventory/in-out-by-group',
    response_model = InOutByGroupReportSchema,
    summary = 'Entradas y Salidas Valorado por Cuenta Contable',
)
async def report_in_out_by_group(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*_ROLES)),
):
    '''
        Valued ins/outs per accounting group over the range.
    '''
    return await in_out_by_group_report_controller(
        db, date_from = date_from, date_to = date_to,
    )


@router.get(
    '/reports/kardex-valued',
    response_model = KardexValuedReportSchema,
    summary = 'Kardex Físico y Valorado',
)
async def report_kardex_valued(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    item_id: Optional[int] = Query(None, ge = 1, description = 'Restrict to a single item.'),
    group_code: Optional[str] = Query(None, description = 'Filter to a single accounting group.'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*_ROLES)),
):
    '''
        Physical + valued kardex for one item, one group or all, with opening
        balances.
    '''
    return await kardex_valued_report_controller(
        db, date_from = date_from, date_to = date_to, item_id = item_id,
        group_code = group_code,
    )


@router.get(
    '/reports/outflow-stats',
    response_model = OutflowReportSchema,
    summary = 'Estadísticas de Salida de Artículos',
)
async def report_outflow_stats(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*_ROLES)),
):
    '''
        Per-item deliveries over the range with recipient and quantity.
    '''
    return await outflow_report_controller(
        db, date_from = date_from, date_to = date_to,
    )
