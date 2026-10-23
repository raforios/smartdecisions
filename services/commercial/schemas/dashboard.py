'''
    DTOs of the main dashboard: the most salient figure of each area, light
    enough to read on entry, with the way into the area behind each one.
'''
from pydantic import BaseModel, Field

from schemas.analytics import Amount, Money, ReferenceRates


class SalesFigures(BaseModel):
    '''
        The last month with sales against the one before and the same month a
        year earlier, each at its own close: a month is the photo of its day.
    '''
    month: str | None = None
    amount: Money | None = None
    previous_amount: Money | None = None
    last_year_amount: Money | None = None
    change_vs_previous: float | None = Field(None, description = 'Percent, in bolivianos.')
    change_vs_last_year: float | None = Field(None, description = 'Percent, in bolivianos.')
    attainment: float | None = Field(
        None, description = 'Percent invoiced over objective of the latest objectives month.')
    gross_margin_percent: float | None = None


class ClientFigures(BaseModel):
    '''Who bought in the month, who is at risk, who came and who left.'''
    bought_this_month: int = 0
    at_risk: int = 0
    new_clients: int = 0
    lost: int = 0
    top_fifth_share: float | None = Field(
        None, description = 'Percent of the sales made by the largest 20 % of clients.')


class InventoryFigures(BaseModel):
    '''The stock photo: what it is worth now, what runs out and what does not move.'''
    available: bool = False
    value: Amount | None = None
    out_of_stock: int = 0
    at_risk: int = 0
    coverage_days: float | None = None
    idle_capital: Amount | None = None


class PurchaseFigures(BaseModel):
    '''The month's purchases and the products whose last cost moved.'''
    available: bool = False
    month: str | None = None
    amount: Money | None = Field(None, description = 'The month, at its close.')
    cost_up: int = 0
    cost_down: int = 0


class ReceivableFigures(BaseModel):
    '''What is owed, how late it is, what comes back and in how many days.'''
    available: bool = False
    balance: Amount = 0.0
    overdue_rate: float = 0.0
    recoverable: Amount = 0.0
    days_to_collect: float | None = None


class DashboardResponse(BaseModel):
    '''
        Main dashboard for GET /v1/commercial/dashboard/{dataset_id}. What is
        held now (stock, receivables) reads at today's rate; the months, at
        their close. The field figures come from OPTIMIZATION.
    '''
    dataset_id: str
    rates: ReferenceRates | None = None
    fx_gap: float | None = Field(
        None, description = 'Percent the USDT is above the official dollar today.')
    sales: SalesFigures = SalesFigures()
    clients: ClientFigures = ClientFigures()
    inventory: InventoryFigures = InventoryFigures()
    purchases: PurchaseFigures = PurchaseFigures()
    receivables: ReceivableFigures = ReceivableFigures()
