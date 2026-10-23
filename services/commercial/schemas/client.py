'''
    DTOs of the client card (plan phase 7): everything about one client in one
    place, and the timeline of its invoices and payments.
'''
from enum import Enum

from pydantic import BaseModel, Field

from schemas.analytics import Amount, Money, ReferenceRates


class TimelineKind(str, Enum):
    '''What one entry of the timeline is.'''
    INVOICE = 'INVOICE'
    PAYMENT = 'PAYMENT'


class ClientListRow(BaseModel):
    '''One client of the dataset, to find it and open its card.'''
    client_id: str
    name: str | None = None
    amount: Amount = 0.0
    purchases: int = 0
    last_purchase: str | None = None


class ClientListResponse(BaseModel):
    '''The clients of a dataset, the largest first, for GET /analytics/clients/{dataset}.'''
    dataset_id: str
    rates: ReferenceRates | None = None
    clients: list[ClientListRow] = []


class ClientMonth(BaseModel):
    '''What the client bought in one month, at its close.'''
    month: str
    amount: Money


class ClientProduct(BaseModel):
    '''A product the client buys, and how much of it.'''
    product: str
    amount: Amount
    quantity: float


class TimelineEntry(BaseModel):
    '''One invoice or one payment, in the order they happened.'''
    date: str
    kind: TimelineKind
    order_id: str
    amount: Amount
    terms: str | None = None
    due_date: str | None = None
    paid: Amount | None = Field(None, description = 'Of an invoice: collected so far.')
    balance: Amount | None = Field(None, description = 'Of an invoice: still owed.')


class ClientReceivable(BaseModel):
    '''What the client owes, and how late.'''
    available: bool = False
    balance: Amount = 0.0
    overdue: Amount = 0.0
    open_invoices: int = 0
    oldest_days_past_due: int = 0
    credit_limit: Amount | None = None


class ClientCardResponse(BaseModel):
    '''
        The card of one client for GET /analytics/client/{dataset}/{client}.
        What is owed and the totals read at today's rate; the months, at their
        close; each invoice and payment, in bolivianos as recorded.
    '''
    dataset_id: str
    client_id: str
    rates: ReferenceRates | None = None
    name: str | None = None
    seller: str | None = None
    city: str | None = None
    zone: str | None = None
    channel: str | None = None
    first_purchase: str | None = None
    last_purchase: str | None = None
    days_since_last: int | None = None
    purchases: int = 0
    total: Amount = 0.0
    average_ticket: Amount = 0.0
    months: list[ClientMonth] = []
    products: list[ClientProduct] = []
    receivable: ClientReceivable = ClientReceivable()
    timeline: list[TimelineEntry] = []
