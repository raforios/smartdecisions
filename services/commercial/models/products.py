'''
    Product master model for DynamoDB.
'''
from typing import TypedDict


class ProductItem(TypedDict, total = False):
    '''
        One product of the master in DynamoDB.

        Table: commercial_products
        Partition Key: owner_email (String) — the account that owns the data.
        Sort Key: sku (String) — the SKU the producer, distributor or supplier
                  gives the product (Rafael, 5-nov-2026), so a reload and a
                  sale recognise the same product.

        Source: 'FILE' (a sales file named it) or 'API' (pushed by the owner's
        system).
    '''
    owner_email: str
    sku: str
    description: str
    category: str | None
    brand: str | None
    supplier: str | None
    unit: str | None
    suggested_price: float | None
    source: str
    created_at: str
    updated_at: str
