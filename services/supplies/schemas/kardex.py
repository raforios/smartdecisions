'''
    Pydantic schemas for the kardex (stock ledger) and reports.
'''
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.enums import (
    EntryTypeEnum,
    MovementTypeEnum,
    ReferenceTypeEnum,
    RequestStatusEnum,
)


class _Base(BaseModel):
    '''
        Shared base config so SQLAlchemy objects can be serialized.
    '''
    model_config = ConfigDict(from_attributes = True)


# --------------------------------------------------------------------------- #
# Manual adjustment                                                           #
# --------------------------------------------------------------------------- #
class KardexAdjustmentSchema(BaseModel):
    '''
        Manual stock adjustment. Allows positive or negative deltas to
        correct counts; always recorded as a new append-only row.
    '''
    item_id: int = Field(..., gt = 0)
    quantity: Decimal = Field(..., description = 'Positive to add, negative to subtract.')
    notes: Optional[str] = Field(None, max_length = 500)


class KardexFilterSchema(BaseModel):
    '''
        Date range and paging accepted by the per-item kardex listing, grouped
        so the controller keeps a readable signature.
    '''
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    skip: int = Field(0, ge = 0)
    limit: int = Field(200, ge = 1, le = 1000)


class KardexMovementResponseSchema(_Base):
    '''
        Single valued kardex row. unit_cost/total_cost and source_entry_id
        carry the PEPS/FIFO cost and the lote (Nota de Ingreso) it came from.
    '''
    id: int
    item_id: int
    movement_type: MovementTypeEnum
    reference_type: ReferenceTypeEnum
    reference_id: Optional[int]
    quantity: Decimal
    balance_before: Decimal
    balance_after: Decimal
    unit_cost: Optional[Decimal]
    total_cost: Optional[Decimal]
    source_entry_id: Optional[int]
    source_entry_detail_id: Optional[int]
    batch_code: Optional[str]
    notes: Optional[str]
    created_by: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# Reports                                                                     #
# --------------------------------------------------------------------------- #
class LowStockItemSchema(_Base):
    '''
        Item flagged as below or at the configured minimum.
    '''
    item_id: int
    item_code: str
    item_name: str
    current_stock: Decimal
    min_stock: Decimal
    deficit: Decimal


class EntryReportRowSchema(_Base):
    '''
        Aggregated row for the entries (Notas de Ingreso) report.
    '''
    entry_id: int
    code: str
    entry_type: EntryTypeEnum
    supplier: Optional[str]
    total_lines: int
    subtotal: Decimal
    discount: Decimal
    total: Decimal
    created_at: datetime


class RequestReportRowSchema(_Base):
    '''
        Aggregated row for the requests report.
    '''
    request_id: int
    code: str
    requester_email: str
    status: RequestStatusEnum
    total_items: int
    requested_at: datetime
    closed_at: Optional[datetime]


# --------------------------------------------------------------------------- #
# Dashboard                                                                   #
# --------------------------------------------------------------------------- #
class DashboardSummarySchema(_Base):
    '''
        Top-level KPIs for the dashboard.
    '''
    total_items: int
    active_items: int
    items_below_min: int
    open_requests: int
    requests_in_process: int
    requests_delivered_pending_close: int
    total_entries: int
    entries_last_30_days: int


class DashboardRecentActivitySchema(_Base):
    '''
        Latest events to render the activity feed.
    '''
    recent_requests: List[RequestReportRowSchema]
    recent_entries: List[EntryReportRowSchema]
    recent_movements: List[KardexMovementResponseSchema]
