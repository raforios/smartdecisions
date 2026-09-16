'''
    Pydantic V2 DTOs of the stock view.

    Its own module because it is its own question: the receivables schema
    answers what is owed and this one answers what is in the warehouse. They
    share nothing but `PeriodInfo`.

    The codes are the contract —`StockStatus.CRITICAL`, `StockUnavailable`—
    and the sentence a manager reads belongs to whoever renders it.
'''
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from schemas.analytics import PeriodInfo


class StockStatus(str, Enum):
    '''
        How one product reads today. A code: the sentence belongs to the UI.
    '''
    OUT_OF_STOCK = 'OUT_OF_STOCK'
    CRITICAL = 'CRITICAL'
    LOW = 'LOW'
    HEALTHY = 'HEALTHY'
    EXCESS = 'EXCESS'
    NO_DEMAND = 'NO_DEMAND'


class StockUnavailable(str, Enum):
    '''
        Why the stock view cannot be built.
    '''
    NO_SNAPSHOT = 'NO_SNAPSHOT'
    NO_PRODUCTS = 'NO_PRODUCTS'


class StockRow(BaseModel):
    '''
        One product in the warehouse, read against how fast it sells.

        `available` is `on_hand - committed`: what the ERP has NOT already
        promised. It is reported, never decided here — this service does not
        hold reservations.

        `coverage_days` is the figure that turns a balance into a decision: how
        many days the stock lasts at the observed daily demand. It is None when
        the product had no sales in the window, because dividing by zero demand
        would report infinite coverage on something nobody buys.
    '''
    label: str
    product_id: str
    on_hand: float = 0.0
    committed: float = 0.0
    available: float = 0.0
    in_transit: float = 0.0
    daily_demand: float = 0.0
    coverage_days: Optional[float] = None
    stockout_date: Optional[str] = None
    status_code: StockStatus = StockStatus.HEALTHY
    abc_class: Optional[str] = None
    stock_value: Optional[float] = None
    excess_units: float = 0.0
    excess_value: Optional[float] = None


class StockKpis(BaseModel):
    '''
        The position of the warehouse and the money sitting in it.
    '''
    snapshot_date: Optional[str] = Field(None, description = 'Date of the photo, ISO.')
    products: int = 0
    units_on_hand: float = 0.0
    units_committed: float = 0.0
    units_available: float = 0.0
    stock_value: Optional[float] = None
    out_of_stock: int = 0
    at_risk: int = 0
    excess_products: int = 0
    excess_value: Optional[float] = None
    average_coverage_days: Optional[float] = None
    stockout_value_at_risk: float = 0.0


class StockBlock(BaseModel):
    '''
        Stock view: what is in the warehouse, how long it lasts and what it
        costs to hold.

        BI and not a transactional system, deliberately: it reports what the
        ERP says and what that implies. `available` reflects a commitment the
        ERP already made; nothing here reserves, holds or promises anything.
    '''
    available: bool = False
    reason_code: Optional[str] = None
    kpis: StockKpis = StockKpis()
    at_risk: list[StockRow] = []
    excess: list[StockRow] = []
    products: list[StockRow] = []


class StockResponse(BaseModel):
    '''
        Full stock view for GET /v1/analytics/stock/{dataset_id}.
    '''
    dataset_id: str
    period: PeriodInfo = PeriodInfo()
    available: bool = False
    reason_code: Optional[str] = None
    kpis: StockKpis = StockKpis()
    at_risk: list[StockRow] = []
    excess: list[StockRow] = []
    products: list[StockRow] = []
