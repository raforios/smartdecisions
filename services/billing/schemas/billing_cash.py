'''
    Cash tills: the contract.

    A till is one user's shift at the counter, for one day. It opens with the
    cash counted in the drawer, takes the sales of whoever opened it and the
    cash that leaves it, and closes with the cash counted again. Nothing is
    deleted: an expense is cancelled with who and when.

    Only cash is counted. QR and cards are not money in the drawer: their
    totals are shown to reconcile them with the bank and the card terminal.
'''
from datetime import date, time as time_type
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from schemas.billing import MethodTotal


class CashSessionStatus(str, Enum):
    '''
        Whether a till still takes movements.
    '''
    OPEN = 'OPEN'
    CLOSED = 'CLOSED'


class ExpenseType(str, Enum):
    '''
        Why cash left the drawer.
    '''
    SUPPLIER_PAYMENT = 'SUPPLIER_PAYMENT'
    SERVICE_PAYMENT = 'SERVICE_PAYMENT'
    PETTY_CASH = 'PETTY_CASH'


class MovementStatus(str, Enum):
    '''
        A cancelled expense stays on record and stops counting.
    '''
    ACTIVE = 'ACTIVE'
    CANCELLED = 'CANCELLED'


class CashOpenIn(BaseModel):
    '''
        Opening a till: the cash counted in the drawer.
    '''
    opening_cash: float = Field(..., ge = 0)


class ExpenseIn(BaseModel):
    '''
        Cash leaving the open till.
    '''
    expense_type: ExpenseType
    amount: float = Field(..., gt = 0)
    concept: str = Field(..., min_length = 1, max_length = 200)
    purchase_id: Optional[str] = Field(
        None, max_length = 120,
        description = 'Delivery note the supplier payment settles, when there is one.'
    )


class CashCloseIn(BaseModel):
    '''
        Closing a till: the cash counted and the note about the difference.

        The screen pre-fills the note from the difference; what arrives here is
        what the user confirmed. A manager closing somebody else's till must
        write one.
    '''
    counted_cash: float = Field(..., ge = 0)
    note: Optional[str] = Field(None, max_length = 500)


class ExpenseOut(BaseModel):
    '''
        One expense of a till, as recorded.
    '''
    movement_id: str
    expense_type: ExpenseType
    amount: float
    concept: str
    purchase_id: Optional[str] = None
    status: MovementStatus
    created_by: str
    created_at: str
    cancelled_by: Optional[str] = None
    cancelled_at: Optional[str] = None


class ExpenseTotal(BaseModel):
    '''
        What one kind of expense took out of the drawer.
    '''
    expense_type: ExpenseType
    count: int
    total: float


class CashSessionOut(BaseModel):
    '''
        A till and its count: everything the cashier sees before closing.
    '''
    session_id: str
    user_email: str
    status: CashSessionStatus
    business_day: date
    expired: bool = Field(
        ..., description = 'Still open on a later day: it takes nothing until closed.'
    )
    opened_at: str
    opening_cash: float
    income: List[MethodTotal]
    income_total: float
    expenses: List[ExpenseTotal]
    expenses_total: float
    expected_cash: float = Field(
        ..., description = 'Opening cash plus cash sales minus active expenses.'
    )
    movements: List[ExpenseOut]
    closed_at: Optional[str] = None
    closed_by: Optional[str] = None
    counted_cash: Optional[float] = None
    difference: Optional[float] = Field(
        None, description = 'Counted minus expected: negative is missing cash.'
    )
    note: Optional[str] = None


class CashSessionsResponse(BaseModel):
    '''
        A list of tills, newest first.
    '''
    items: List[CashSessionOut]


class CashAlert(BaseModel):
    '''
        A till that should be closed: open past the shop's alert time, or
        left open from an earlier day.
    '''
    session_id: str
    user_email: str
    business_day: date
    opened_at: str
    expired: bool


class CashAlertsResponse(BaseModel):
    '''
        The tills to close now. Empty when the shop set no alert time and no
        till was left open from an earlier day.
    '''
    alert_time: Optional[time_type] = None
    items: List[CashAlert]


# --- grouped arguments -------------------------------------------------------
# A controller carries the resource, the owner, `request` and `current_user`
# for the decorators; what the operation is about travels as one argument.

class TillRef(BaseModel):
    '''
        One till, and whether the caller may see every till of the shop.
    '''
    session_id: str = Field(..., min_length = 1, max_length = 120)
    is_manager: bool = False


class TillQuery(BaseModel):
    '''
        Which tills a list returns, and for whom.
    '''
    is_manager: bool = False
    user_email: Optional[str] = Field(None, max_length = 100)
    date_from: Optional[date] = None
    date_to: Optional[date] = None


class TillExpense(BaseModel):
    '''
        An expense and the till it leaves.
    '''
    session_id: str = Field(..., min_length = 1, max_length = 120)
    expense: ExpenseIn


class TillExpenseRef(BaseModel):
    '''
        One expense of one till.
    '''
    session_id: str = Field(..., min_length = 1, max_length = 120)
    movement_id: str = Field(..., min_length = 1, max_length = 60)


class TillClose(BaseModel):
    '''
        Closing one till, by its user or by a manager.
    '''
    session_id: str = Field(..., min_length = 1, max_length = 120)
    is_manager: bool = False
    closing: CashCloseIn
