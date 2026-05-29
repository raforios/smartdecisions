'''
    Pydantic schemas for the kardex (stock ledger) and reports.
'''
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from schemas.enums import MovementTypeEnum, ReferenceTypeEnum, RequestStatusEnum


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


class KardexMovementResponseSchema(_Base):
    '''
        Single kardex row.
    '''
    id: int
    item_id: int
    movement_type: MovementTypeEnum
    reference_type: ReferenceTypeEnum
    reference_id: Optional[int]
    quantity: Decimal
    balance_before: Decimal
    balance_after: Decimal
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


class ReplenishmentReportRowSchema(_Base):
    '''
        Aggregated row for the replenishments report.
    '''
    replenishment_id: int
    code: str
    item_id: int
    item_code: str
    requested_qty: Decimal
    received_qty: Decimal
    status: str
    created_at: datetime
    completed_at: Optional[datetime]


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
    pending_replenishments: int
    in_reception_replenishments: int


class DashboardRecentActivitySchema(_Base):
    '''
        Latest events to render the activity feed.
    '''
    recent_requests: List[RequestReportRowSchema]
    recent_replenishments: List[ReplenishmentReportRowSchema]
    recent_movements: List[KardexMovementResponseSchema]
