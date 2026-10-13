'''
    Pydantic V2 DTOs for the daily stock.

    The company loads what it has per SKU when the day starts; every sale a
    seller registers on a visit draws from that single figure, so two sellers
    cannot promise the same last box. It is an on-the-day utility, apart from
    the historical stock analysis INGEST and ANALYTICS run on the uploaded file.
'''
from enum import Enum
from pydantic import BaseModel, Field


class StockError(str, Enum):
    '''
        Why a stock request could not be served.
    '''
    EMPTY_STOCK_LOAD = 'EMPTY_STOCK_LOAD'
    DUPLICATE_SKU = 'DUPLICATE_SKU'
    STOCK_NOT_LOADED = 'STOCK_NOT_LOADED'
    INSUFFICIENT_STOCK = 'INSUFFICIENT_STOCK'
    NO_STOCK_FOR_DAY = 'NO_STOCK_FOR_DAY'
    STOCK_SOURCE_UNAVAILABLE = 'STOCK_SOURCE_UNAVAILABLE'
    MISSING_PRICE = 'MISSING_PRICE'


class StockItemLoadSchema(BaseModel):
    '''
        One SKU as loaded at the start of the day.
    '''
    sku: str = Field(..., min_length = 1, max_length = 64)
    product_name: str | None = Field(None, max_length = 150)
    quantity: float = Field(..., ge = 0, description = 'Units available when the day starts.')
    unit_price: float = Field(..., ge = 0, description = 'What one unit sells for today.')
    unit_cost: float | None = Field(None, ge = 0)


class DailyStockLoadSchema(BaseModel):
    '''
        The day's opening stock. Loading the same day again replaces it.
    '''
    date: str = Field(..., pattern = r'^\d{4}-\d{2}-\d{2}$', description = 'YYYY-MM-DD.')
    items: list[StockItemLoadSchema] = Field(..., min_length = 1)


class DailyStockFromIngestSchema(BaseModel):
    '''
        Open the day from the stock file already loaded in INGEST.

        The same file the analysis reads: the company fills one stock template
        and both modules use it, instead of typing the day's stock again here.
    '''
    dataset_id: str = Field(..., min_length = 8, max_length = 64)
    date: str = Field(..., pattern = r'^\d{4}-\d{2}-\d{2}$', description = 'YYYY-MM-DD.')


class SaleItemSchema(BaseModel):
    '''
        One line of a sale registered on a visit.
    '''
    sku: str = Field(..., min_length = 1, max_length = 64)
    quantity: float = Field(..., gt = 0)


class StockItemResponseSchema(BaseModel):
    '''
        One SKU of the day: what was loaded, what was sold, what is left.
    '''
    date: str
    sku: str
    product_name: str | None = None
    opening_quantity: float
    sold_quantity: float
    available_quantity: float
    unit_price: float | None = None
    unit_cost: float | None = None
    updated_at: str


class DailyStockResponseSchema(BaseModel):
    '''
        The day's stock, one row per SKU.
    '''
    date: str
    items: list[StockItemResponseSchema]
    skus_loaded: int
    skus_out_of_stock: int


class SellerDaySchema(BaseModel):
    '''
        One seller's day: visits, what was sold at the day's stock price and
        how far the routes went.
    '''
    seller: str
    on_route: bool
    visits: int = Field(..., ge = 0)
    units_sold: float = Field(..., ge = 0)
    sales_amount: float = Field(..., ge = 0, description = 'Bolivianos, at the day\'s price.')
    distance_km: float = Field(..., ge = 0)


class DayStatisticsSchema(BaseModel):
    '''
        What the field did on one day, for the main dashboard: who is out,
        how much of what was planned was visited, and how far they drove.
    '''
    date: str
    sellers_on_route: int = Field(..., ge = 0, description = 'Routes started and still open.')
    routes_started: int = Field(..., ge = 0)
    routes_closed: int = Field(..., ge = 0)
    planned_stops: int = Field(..., ge = 0, description = 'Stops of the plans run that day.')
    visited_stops: int = Field(..., ge = 0)
    visit_compliance: float | None = Field(
        None, description = 'Visited over planned, percent; None with no plan run.')
    distance_km: float = Field(..., ge = 0, description = 'Along the reported points.')
    sales_amount: float = Field(0.0, ge = 0, description = 'Bolivianos sold on visits, '
                                                           'at the day\'s stock price.')
    stock_available_value: float | None = Field(
        None, description = 'Bolivianos still on hand at the day\'s price; None '
                            'when the day\'s stock was not loaded.')
    sellers: list[SellerDaySchema] = []
