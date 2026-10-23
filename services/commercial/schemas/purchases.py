'''
    DTOs of the purchases view: what the last purchase of each product cost
    against the previous ones, and what replacing it costs today.
'''
from enum import Enum

from pydantic import BaseModel, Field

from schemas.analytics import Money, ReferenceRates


class PurchasesUnavailable(str, Enum):
    '''Why the purchases view cannot be built.'''
    NO_PURCHASES = 'NO_PURCHASES'


class PurchaseRow(BaseModel):
    '''
        One product: its last purchase at the rate of its day, the previous
        ones, what the same purchase costs today, and the margin at the price
        it sells for.
    '''
    product_id: str
    product_name: str | None = None
    supplier: str | None = None
    last_date: str
    currency: str
    quantity: float
    last_cost: Money = Field(..., description = 'Unit cost put in the warehouse, its day.')
    previous_cost: Money | None = Field(None, description = 'Unit cost of the purchase before.')
    change_vs_previous: float | None = Field(None, description = 'Percent, in bolivianos.')
    average_previous_cost: Money | None = None
    cost_today: Money = Field(..., description = 'The same purchase paid at today\'s rate.')
    difference_today: Money
    sale_price: float | None = Field(None, description = 'Bolivianos, the latest known.')
    margin_at_last_cost: float | None = Field(None, description = 'Percent.')
    margin_at_cost_today: float | None = Field(None, description = 'Percent.')


class PurchasesResponse(BaseModel):
    '''
        Purchases view for GET /v1/commercial/purchases/{dataset_id}. Each
        purchase reads at its own day (rule 2); next to it, today.
    '''
    dataset_id: str
    available: bool = False
    reason_code: str | None = None
    rates: ReferenceRates | None = None
    month: str | None = None
    month_amount: Money | None = Field(None, description = 'The last month, at its close.')
    purchases_count: int = 0
    suppliers: int = 0
    cost_up: int = Field(0, description = 'Products whose last cost rose against the previous.')
    cost_down: int = 0
    products: list[PurchaseRow] = []
