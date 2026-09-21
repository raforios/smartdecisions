'''
    Pydantic V2 DTOs for the daily stock.

    The company loads what it has per SKU when the day starts; every sale a
    seller registers on a visit draws from that single figure, so two sellers
    cannot promise the same last box. It is an on-the-day utility, apart from
    the historical stock analysis INGEST and ANALYTICS run on the uploaded file.
'''
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class StockError(str, Enum):
    '''
        Why a stock request could not be served.
    '''
    EMPTY_STOCK_LOAD = 'EMPTY_STOCK_LOAD'
    DUPLICATE_SKU = 'DUPLICATE_SKU'
    STOCK_NOT_LOADED = 'STOCK_NOT_LOADED'
    INSUFFICIENT_STOCK = 'INSUFFICIENT_STOCK'


class StockItemLoadSchema(BaseModel):
    '''
        One SKU as loaded at the start of the day.
    '''
    sku: str = Field(..., min_length = 1, max_length = 64)
    product_name: Optional[str] = Field(None, max_length = 150)
    quantity: float = Field(..., ge = 0, description = 'Units available when the day starts.')


class DailyStockLoadSchema(BaseModel):
    '''
        The day's opening stock. Loading the same day again replaces it.
    '''
    date: str = Field(..., pattern = r'^\d{4}-\d{2}-\d{2}$', description = 'YYYY-MM-DD.')
    items: List[StockItemLoadSchema] = Field(..., min_length = 1)


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
    product_name: Optional[str] = None
    opening_quantity: float
    sold_quantity: float
    available_quantity: float
    updated_at: str


class DailyStockResponseSchema(BaseModel):
    '''
        The day's stock, one row per SKU.
    '''
    date: str
    items: List[StockItemResponseSchema]
    skus_loaded: int
    skus_out_of_stock: int
