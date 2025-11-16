'''
    POS Schemas (Request/Response)
'''
from typing import List, Optional
from datetime import datetime
from fastapi import Query
from pydantic import BaseModel, Field, ConfigDict

# --- BASE SCHEMAS ---
class PosBaseSchema(BaseModel):
    '''
        Base schema with `from_attributes=True` enabled to handle
        ORM objects from SQLAlchemy.
    '''
    model_config = ConfigDict(from_attributes = True)


# --- POINT OF SALE (POS) INVENTORY SCHEMAS ---
class POSInventoryBaseSchema(PosBaseSchema):
    '''
        Base schema for detailed Point of Sale Inventory fields.
    '''
    product_sku: str = Field(
        ...,
        description = 'SKU of the product being tracked.'
    )
    location: str = Field(
        ...,
        max_length = 50,
        description = 'Location within the POS (e.g., Sala or Almacén).'
    )
    batch_number: str = Field(
        ...,
        max_length = 50,
        description = 'Batch or lot number of the product units.'
    )
    expiration_date: str = Field(
        ...,
        description = 'Expiration date of the product units (YYYY-MM-DD).'
    )
    is_short_date: Optional[bool] = Field(
        False,
        description = 'Flag indicating if the product is on short date (True/Red, False/Green).'
    )
    quantity: int = Field(
        ...,
        ge = 0,
        description = 'Total quantity of units for this specific batch/location/SKU.'
    )

class POSInventoryCreateSchema(POSInventoryBaseSchema):
    '''
        Schema for creating a new POS Inventory detail.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company owning this inventory record.'
    )

class POSInventoryUpdateSchema(PosBaseSchema):
    '''
        Schema for updating a POS Inventory detail.
    '''
    product_sku: Optional[str] = Field(
        None, description = 'SKU of the product being tracked.'
    )
    location: Optional[str] = Field(
        None, description = 'Location within the POS (e.g., Sala or Almacén).'
    )
    batch_number: Optional[str] = Field(
        None, description = 'Batch or lot number of the product units.'
    )
    expiration_date: Optional[str] = Field(
        None, description = 'Expiration date of the product units (YYYY-MM-DD).'
    )
    is_short_date: Optional[bool] = Field(
        None, description = 'Flag indicating if the product is on short date.'
    )
    quantity: Optional[int] = Field(
        None, description = 'Total quantity of units.'
    )

class POSInventoryResponseSchema(PosBaseSchema):
    '''
        Response schema for a POS Inventory detail, including ID and timestamps.
    '''
    id: int = Field(
        ...,
        description = 'Unique identifier for the inventory record.'
    )
    point_of_sale_id: int = Field(
        ...,
        description = 'ID of the parent Point of Sale.'
    )
    product_id: int = Field(
        ...,
        description = 'ID of the product being tracked.'
    )
    location: str = Field(
        ...,
        max_length = 50,
        description = 'Location within the POS (e.g., Sala or Almacén).'
    )
    batch_number: str = Field(
        ...,
        max_length = 50,
        description = 'Batch or lot number of the product units.'
    )
    expiration_date: datetime = Field(
        ...,
        description = 'Expiration date of the product units.'
    )
    is_short_date: Optional[bool] = Field(
        False,
        description = 'Flag indicating if the product is on short date (True/Red, False/Green).'
    )
    quantity: int = Field(
        ...,
        ge = 0,
        description = 'Total quantity of units for this specific batch/location/SKU.'
    )
    created_at: Optional[datetime] = Field(
        None,
        description = 'Timestamp when the record was created.'
    )

class POSInventoryListResponseSchema(PosBaseSchema):
    '''
        Response schema for a list of POS Inventory items.
    '''
    items: List[POSInventoryResponseSchema]
    total: int

# --- POINT OF SALE (POS) SCHEMAS ---

class PointOfSaleBaseSchema(PosBaseSchema):
    '''
        Base schema for Point of Sale (PDV) data.
    '''
    name: str = Field(
        ...,
        max_length = 255,
        description = 'Commercial name of the Point of Sale.'
    )
    external_code: Optional[str] = Field(
        None,
        max_length = 50,
        description = 'External code used by the client for this POS.'
    )
    address: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Physical address of the POS.'
    )
    is_active: Optional[bool] = Field(
        True,
        description = 'Status of the POS.'
    )
    latitude: float = Field(
        ...,
        description = 'Geographical latitude of the POS.'
    )
    longitude: float = Field(
        ...,
        description = 'Geographical longitude of the POS.'
    )

class PointOfSaleCreateSchema(PointOfSaleBaseSchema):
    '''
        Schema for creating a new Point of Sale.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company that owns the POS record.'
    )
    initial_inventory: Optional[List[POSInventoryBaseSchema]] = Field(
        None,
        description = 'Initial inventory details to be associated with this POS.'
    )

class PointOfSaleUpdateSchema(PosBaseSchema):
    '''
        Schema for updating an existing Point of Sale. All fields are optional.
    '''
    # Override fields from base to make them optional for updates
    name: Optional[str] = None
    is_active: Optional[bool] = None
    address: Optional[str] = None
    external_code: Optional[str] = None

class PointOfSaleResponseSchema(PointOfSaleBaseSchema):
    '''
        Response schema for a Point of Sale, including ID, timestamps, and inventory.
    '''
    id: int = Field(
        ...,
        description = 'Unique identifier for the POS record.'
    )
    company_id: int = Field(
        ...,
        description = 'ID of the company that owns the POS record.'
    )
    inventory: List[POSInventoryResponseSchema] = Field(
        [],
        description = 'Detailed local inventory associated with this Point of Sale.'
    )
    created_at: Optional[datetime] = Field(
        None,
        description = 'Timestamp when the record was created.'
    )

class POSListResponseSchema(PosBaseSchema):
    '''
        Response schema for a paginated list of Points of Sale.
    '''
    items: List[PointOfSaleResponseSchema]
    total: int

class POSFilterSchema(BaseModel):
    '''
        Schema to encapsulate filtering parameters for Points of Sale.
    '''
    company_id: int = Query(..., description = 'Company ID (Mandatory for filtering).')
    name: Optional[str] = Query(None, description = 'Filter by POS name (partial match).')
    external_code: Optional[str] = Query(None, description = 'Filter by exact external code.')
    is_active: Optional[bool] = Query(None, description = 'Filter by status (True/False).')

    class Config:# pylint: disable=too-few-public-methods
        '''
            'Pydantic config.'
        '''
        arbitrary_types_allowed = True
