'''
    POS Schemas (Request/Response)
'''
from typing import List, Optional
from datetime import datetime
from fastapi import Query
from pydantic import BaseModel, Field, ConfigDict

from schemas.common import (
    PhotoResponseSchema,
    BaseSchema
)
from models.pos import PointOfSaleStatus # Import the Enum

# --- POINT OF SALE (POS) INVENTORY SCHEMAS ---
class POSInventoryBaseSchema(BaseSchema):
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

class POSInventoryUpdateSchema(BaseSchema):
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

class POSInventoryResponseSchema(BaseSchema):
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
    product_sku: str = Field(
        ...,
        description = 'SKU of the product being tracked.'
    )
    product_name: str = Field(
        ...,
        description = 'Name of the product being tracked.'
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

    model_config = ConfigDict(from_attributes=True)

class POSInventoryListResponseSchema(BaseSchema):
    '''
        Response schema for a list of POS Inventory items.
    '''
    items: List[POSInventoryResponseSchema]
    total: int

# --- POINT OF SALE (POS) SCHEMAS ---

class PointOfSaleBaseSchema(BaseSchema):
    '''
        Base schema for Point of Sale (POS) data, including core identification and
        location details.
    '''
    # Identification and Location (Mandatory)
    code: str = Field(
        ...,
        max_length = 50,
        description = 'Unique code for the Point of Sale.'
    )
    name: str = Field(
        ...,
        max_length = 255,
        description = 'Commercial name of the Point of Sale.'
    )
    country_id: int = Field(
        ...,
        description = 'ID of the country where the POS is located.'
    )
    city_id: int = Field(
        ...,
        description = 'ID of the city where the POS is located.'
    )
    zone_id: int = Field(
        ...,
        description = 'ID of the geographical zone where the POS is located.'
    )
    address: str = Field(
        ...,
        max_length = 255,
        description = 'Physical address of the Point of Sale.'
    )
    latitude: float = Field(
        ...,
        description = 'Geographical latitude of the POS (Decimal 10,8 precision).'
    )
    longitude: float = Field(
        ...,
        description = 'Geographical longitude of the POS (Decimal 10,8 precision).'
    )
    max_checkin_distance: int = Field(
        0,
        ge = 0,
        description = 'Maximum allowed distance in meters for check-in/out registration.'
    )

    # Operation and Classification
    operating_hours: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Operating hours of the POS (e.g., "09:00-18:00").'
    )
    pos_type_id: int = Field(
        ...,
        description = 'ID of the Point of Sale type.'
    )
    channel_id: int = Field(
        ...,
        description = 'ID of the sales channel associated with the POS.'
    )
    status: PointOfSaleStatus = Field(
        PointOfSaleStatus.IN_CREATION,
        description = 'Current operational status of the POS.'
    )

    # Complementary Information (Optional)
    description: Optional[str] = Field(
        None,
        max_length = 500,
        description = 'Additional description for the POS.'
    )
    reference: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Reference details for arrival at the POS.'
    )
    contact_person: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Name of the contact person at the POS.'
    )
    contact_phone: Optional[str] = Field(
        None,
        max_length = 50,
        description = 'Contact phone number for the person at the POS.'
    )
    contact_role: Optional[str] = Field(
        None,
        max_length = 100,
        description = 'Role of the contact person at the POS.'
    )
    external_code: Optional[str] = Field(
        None,
        max_length = 50,
        description = 'External code used by the client for this POS.'
    )

class PointOfSaleCreateSchema(PointOfSaleBaseSchema):
    '''
        Schema for creating a new Point of Sale, including mandatory company ID
        and optional initial inventory.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company that owns the POS record.'
    )
    initial_inventory: Optional[List[POSInventoryBaseSchema]] = Field(
        None,
        description = 'Optional list of initial inventory items to be associated with this POS.'
    )

class PointOfSaleUpdateSchema(BaseSchema):
    '''
        Schema for updating an existing Point of Sale. All fields are optional.
    '''
    # Identification and Location
    code: Optional[str] = Field(
        None,
        max_length = 50,
        description = 'Unique code for the Point of Sale.'
    )
    name: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Commercial name of the Point of Sale.'
    )
    country_id: Optional[int] = Field(
        None,
        description = 'ID of the country where the POS is located.'
    )
    city_id: Optional[int] = Field(
        None,
        description = 'ID of the city where the POS is located.'
    )
    zone_id: Optional[int] = Field(
        None,
        description = 'ID of the geographical zone where the POS is located.'
    )
    address: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Physical address of the Point of Sale.'
    )
    latitude: Optional[float] = Field(
        None,
        description = 'Geographical latitude of the POS (Decimal 10,8 precision).'
    )
    longitude: Optional[float] = Field(
        None,
        description = 'Geographical longitude of the POS (Decimal 10,8 precision).'
    )
    max_checkin_distance: Optional[int] = Field(
        None,
        ge = 0,
        description = 'Maximum allowed distance in meters for check-in/out registration.'
    )

    # Operation and Classification
    operating_hours: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Operating hours of the POS (e.g., "09:00-18:00").'
    )
    pos_type_id: Optional[int] = Field(
        None,
        description = 'ID of the Point of Sale type.'
    )
    channel_id: Optional[int] = Field(
        None,
        description = 'ID of the sales channel associated with the POS.'
    )
    status: Optional[PointOfSaleStatus] = Field(
        None,
        description = 'Current operational status of the POS.'
    )

    # Complementary Information
    description: Optional[str] = Field(
        None,
        max_length = 500,
        description = 'Additional description for the POS.'
    )
    reference: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Reference details for arrival at the POS.'
    )
    contact_person: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Name of the contact person at the POS.'
    )
    contact_phone: Optional[str] = Field(
        None,
        max_length = 50,
        description = 'Contact phone number for the person at the POS.'
    )
    contact_role: Optional[str] = Field(
        None,
        max_length = 100,
        description = 'Role of the contact person at the POS.'
    )
    external_code: Optional[str] = Field(
        None,
        max_length = 50,
        description = 'External code used by the client for this POS.'
    )

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
    photos: List[PhotoResponseSchema] = Field(
        default = [],
        description = 'List of photos associated with the Point of Sale.'
    )
    created_at: Optional[datetime] = Field(
        None,
        description = 'Timestamp when the record was created.'
    )

    model_config = ConfigDict(from_attributes=True)

class POSListResponseSchema(BaseSchema):
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

    code: Optional[str] = Query(None, description = 'Filter by unique POS code.')
    name: Optional[str] = Query(None, description = 'Filter by POS name (partial match).')
    external_code: Optional[str] = Query(None, description = 'Filter by exact external code.')
    country_id: Optional[int] = Query(None, description = 'Filter by country ID.')
    city_id: Optional[int] = Query(None, description = 'Filter by city ID.')
    zone_id: Optional[int] = Query(None, description = 'Filter by geographical zone ID.')
    pos_type_id: Optional[int] = Query(None, description = 'Filter by Point of Sale type ID.')
    channel_id: Optional[int] = Query(None, description = 'Filter by sales channel ID.')
    status: Optional[PointOfSaleStatus] = Query(None,
                                        description = 'Filter by operational status of the POS.')

    model_config = ConfigDict(arbitrary_types_allowed=True)

class PointOfSaleBulkCreateSchema(BaseSchema):
    '''
        Schema for a single row in the Point of Sale bulk upload file.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company that owns the POS record.'
    )
    # Identification and Location (Mandatory)
    code: str = Field(
        ...,
        max_length = 50,
        description = 'Unique code for the Point of Sale.'
    )
    name: str = Field(
        ...,
        max_length = 255,
        description = 'Commercial name of the Point of Sale.'
    )
    country_id: int = Field(
        ...,
        description = 'ID of the country where the POS is located.'
    )
    city_id: int = Field(
        ...,
        description = 'ID of the city where the POS is located.'
    )
    zone_id: int = Field(
        ...,
        description = 'ID of the geographical zone where the POS is located.'
    )
    address: str = Field(
        ...,
        max_length = 255,
        description = 'Physical address of the Point of Sale.'
    )
    latitude: float = Field(
        ...,
        description = 'Geographical latitude of the POS (Decimal 10,8 precision).'
    )
    longitude: float = Field(
        ...,
        description = 'Geographical longitude of the POS (Decimal 10,8 precision).'
    )
    max_checkin_distance: int = Field(
        0,
        ge = 0,
        description = 'Maximum allowed distance in meters for check-in/out registration.'
    )

    # Operation and Classification
    operating_hours: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Operating hours of the POS (e.g., "09:00-18:00").'
    )
    pos_type_id: int = Field(
        ...,
        description = 'ID of the Point of Sale type.'
    )
    channel_id: int = Field(
        ...,
        description = 'ID of the sales channel associated with the POS.'
    )
    status: PointOfSaleStatus = Field(
        PointOfSaleStatus.IN_CREATION, # Default for bulk creation
        description = 'Current operational status of the POS.'
    )

    # Complementary Information (Optional)
    description: Optional[str] = Field(
        None,
        max_length = 500,
        description = 'Additional description for the POS.'
    )
    reference: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Reference details for arrival at the POS.'
    )
    contact_person: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Name of the contact person at the POS.'
    )
    contact_phone: Optional[str] = Field(
        None,
        max_length = 50,
        description = 'Contact phone number for the person at the POS.'
    )
    contact_role: Optional[str] = Field(
        None,
        max_length = 100,
        description = 'Role of the contact person at the POS.'
    )
    external_code: Optional[str] = Field(
        None,
        max_length = 50,
        description = 'External code used by the client for this POS.'
    )

class POSInventoryBulkCreateSchema(POSInventoryBaseSchema):
    '''
        Schema for a single row in the POS Inventory bulk upload file.
        Includes identifiers for the POS and Company.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company that owns the POS and product.'
    )
    pos_external_code: str = Field(
        ...,
        max_length = 50,
        description = 'External code of the POS where the inventory is located.'
    )

class PointOfSaleNestedResponseSchema(PointOfSaleBaseSchema):
    '''
        Simplified response schema for Point of Sale when nested inside other entities
        like TradePlanning. Includes core POS details but excludes the detailed 'inventory'
        relationship.
    '''
    id: int = Field(
        ...,
        description = 'Unique identifier for the POS record.'
    )
    company_id: int = Field(
        ...,
        description = 'ID of the company that owns the POS record.'
    )
    created_at: Optional[datetime] = Field(
        None,
        description = 'Timestamp when the record was created.'
    )
    # NOTE: 'inventory: List[POSInventoryResponseSchema]' is deliberately omitted here.

    model_config = ConfigDict(from_attributes=True)
