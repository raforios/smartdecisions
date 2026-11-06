'''
    The counter dashboard: the contract.

    What sold, what it left, what is about to expire and what is about to run
    out, plus what each payment method brought in —the same total the cash
    tills reconcile against.
'''
from datetime import date

from pydantic import BaseModel, Field

from schemas.billing import PaymentMethod

class ExpiringLot(BaseModel):
    '''
        A batch close enough to its expiry date to act on: return it to the
        laboratory, discount it, or push it at the counter.
    '''
    sku: str
    description: str
    lot_code: str | None = None
    expiry_date: date
    days_left: int
    quantity_remaining: float
    unit_cost: float
    value_at_cost: float


class LowStockProduct(BaseModel):
    '''
        A SKU at or under the minimum the pharmacy set for it.
    '''
    sku: str
    description: str
    available_quantity: float
    min_stock: float


class TopProduct(BaseModel):
    '''
        What sold most over the window, by amount charged.
    '''
    sku: str
    description: str
    quantity: float
    amount: float


class MethodTotal(BaseModel):
    '''
        What one payment method brought in.
    '''
    payment_method: PaymentMethod
    count: int
    total: float


class BillingDashboard(BaseModel):
    '''
        What the person behind the counter needs to see when they open the
        screen: what was sold, what it left, what is about to expire and what
        is about to run out.

        The window defaults to today because that is the question a till asks;
        the same numbers answer for any range.
    '''
    date_from: date
    date_to: date
    sales_count: int
    sales_amount: float
    sales_cost: float
    margin: float
    margin_percent: float | None = Field(
        None, description = 'Margin over the amount charged; None when nothing sold.'
    )
    average_ticket: float | None = None
    cancelled_count: int
    stock_value_at_cost: float
    expiry_alert_days: int
    expiring_soon: list[ExpiringLot]
    expired: list[ExpiringLot]
    low_stock: list[LowStockProduct]
    top_products: list[TopProduct]
    sales_by_method: list[MethodTotal] = []
