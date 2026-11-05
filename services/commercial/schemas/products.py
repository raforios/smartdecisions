'''
    Pydantic V2 DTOs for the product master: what describes a product is
    stated once, keyed by its SKU, and the sales lines only name it.
'''
from enum import Enum

from pydantic import BaseModel, Field

from schemas.clients import ClientUpsertResultSchema
from schemas.closed_options import ProductUnit


class ProductError(str, Enum):
    '''
        Why a product request could not be served.
    '''
    PRODUCT_NOT_FOUND = 'PRODUCT_NOT_FOUND'


class ProductSource(str, Enum):
    '''
        Where a product record came from.
    '''
    FILE = 'FILE'
    API = 'API'


class ProductBase(BaseModel):
    '''
        The attributes of a product, all optional but the identity.
    '''
    description: str | None = Field(None, max_length = 200)
    category: str | None = Field(None, max_length = 100)
    brand: str | None = Field(None, max_length = 100)
    supplier: str | None = Field(None, max_length = 150)
    unit: ProductUnit | None = None
    suggested_price: float | None = Field(
        None, ge = 0.0, description = "The supplier's suggested sale price.")


class ProductUpsertSchema(ProductBase):
    '''
        One product as the owner's system pushes it: a record created on
        purpose names the product.
    '''
    sku: str = Field(..., min_length = 1, max_length = 64,
                     description = 'SKU of the producer, distributor or supplier.')
    description: str = Field(..., min_length = 1, max_length = 200)


class ProductBulkUpsertSchema(BaseModel):
    '''
        A batch of products pushed in one call.
    '''
    products: list[ProductUpsertSchema] = Field(..., min_length = 1)


class ProductUpdateSchema(ProductBase):
    '''
        A correction to a product already in the master. Unlike a load, this
        one OVERWRITES what it names.
    '''


class ProductResponseSchema(ProductBase):
    '''
        One product of the master as it is stored.
    '''
    sku: str
    source: ProductSource
    created_at: str
    updated_at: str


class ProductListResponseSchema(BaseModel):
    '''
        The owner's products.
    '''
    products: list[ProductResponseSchema]
    total: int = Field(..., ge = 0)


class ProductUpsertResultSchema(ClientUpsertResultSchema):
    '''
        Outcome of a load into the product master: created, completed and
        unchanged, as every master counts it.
    '''
