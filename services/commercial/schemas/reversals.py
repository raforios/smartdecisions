'''
    DTOs of cancellations and returns (Rafael, 6-nov-2026).

    A cancelled or returned sale is known and analyzed on its own —when, how
    much, which products, why— while the sales stay net: what the buyer kept.
    One record per cancellation or return; reverting one writes the same
    record again with its new state, so the report counts only what stands.
'''
import datetime
from enum import Enum

from pydantic import BaseModel, Field

from schemas.analytics import Money
from schemas.channels import SaleRowSchema


class ReversalKind(str, Enum):
    '''
        What undid a sale: all of it, or some units of it.
    '''
    CANCELLATION = 'CANCELLATION'
    RETURN = 'RETURN'


class ReversalState(str, Enum):
    '''
        Whether the cancellation or the return still stands; a reverted one
        stays recorded and stops counting.
    '''
    ACTIVE = 'ACTIVE'
    REVERTED = 'REVERTED'


class ReversalLineSchema(BaseModel):
    '''
        One product undone: how many units and what they were worth.
    '''
    product_id: str | None = Field(
        None, min_length = 1, max_length = 64,
        description = 'SKU of the producer, distributor or supplier.')
    product_name: str = Field(..., min_length = 1, max_length = 150)
    quantity: float = Field(..., gt = 0)
    amount: float = Field(..., ge = 0, description = 'Bolivianos.')


class ReversalSchema(BaseModel):
    '''
        A cancellation or a return, and what the sale amounts to after it.

        `rows` are the sale's lines as they now stand —what the buyer kept,
        nothing when it was cancelled— and replace the sale's lines in the
        company's latest dataset, so the analysis counts net sales.
    '''
    reversal_id: str = Field(..., min_length = 1, max_length = 120,
                             description = 'The cancelled sale, or the credit note.')
    kind: ReversalKind
    state: ReversalState = ReversalState.ACTIVE
    order_id: str = Field(..., min_length = 1, max_length = 64,
                          description = 'The sale, as its lines name it.')
    date: datetime.date = Field(..., description = 'The day it was cancelled or returned.')
    reason_code: int | None = Field(None, ge = 1)
    reason: str | None = Field(None, max_length = 200)
    lines: list[ReversalLineSchema] = Field(..., min_length = 1)
    rows: list[SaleRowSchema] = []


class ReversalResponse(BaseModel):
    '''
        A cancellation or a return as recorded, and the dataset whose sale it
        set right; None when the company has no dataset yet.
    '''
    reversal_id: str
    kind: ReversalKind
    state: ReversalState
    order_id: str
    date: str
    reason_code: int | None = None
    reason: str | None = None
    lines: list[ReversalLineSchema]
    quantity: float
    amount: float = Field(..., description = 'Bolivianos.')
    updated_at: str
    dataset_id: str | None = None


class ReversalMonth(BaseModel):
    '''
        What one kind undid in one month, at that month's close.
    '''
    month: str
    kind: ReversalKind
    count: int
    quantity: float
    amount: Money


class ReversalReason(BaseModel):
    '''
        What one reason undid over the window, at today's rate.
    '''
    kind: ReversalKind
    reason_code: int | None = None
    reason: str | None = None
    count: int
    amount: Money


class ReversalsReport(BaseModel):
    '''
        Cancellations and returns for GET /v1/commercial/reversals: totals by
        month and by reason over what stands, and every record, reverted ones
        included.
    '''
    count: int = 0
    quantity: float = 0.0
    amount: Money | None = None
    months: list[ReversalMonth] = []
    reasons: list[ReversalReason] = []
    reversals: list[ReversalResponse] = []
