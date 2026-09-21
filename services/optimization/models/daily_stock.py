'''
    Daily stock item for DynamoDB.
'''
from typing import Optional, TypedDict


class DailyStockItem(TypedDict, total = False):
    '''
        What the company has of one SKU on one day.

        Table: optimization_daily_stock
        Partition Key: owner_email (String)
        Sort Key:      stock_key   (String, "{YYYY-MM-DD}#{sku}")

        The day prefixes the sort key so the whole day is one bounded Query.
        `available_quantity` is stored, not derived: DynamoDB conditions allow
        no arithmetic, so the only way to refuse a sale atomically is to keep
        the remaining units as an attribute and condition on it
        (`available_quantity >= :units`). `sold_quantity` moves in step.
    '''
    owner_email: str
    stock_key: str
    date: str
    sku: str
    product_name: Optional[str]
    opening_quantity: float
    sold_quantity: float
    available_quantity: float
    updated_at: str
