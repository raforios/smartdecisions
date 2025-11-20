'''
    Impulses Schemas (Request/Response)
'''
from typing import List, Optional
from datetime import datetime
from fastapi import Query
from pydantic import BaseModel, Field
from schemas.common import BaseSchema

# --- TRADE PROMOTION (BANDEO) SCHEMAS ---

class TradePromotionDetailBaseSchema(BaseSchema):
    '''
        Base schema for Promotion Detail (SKU list).
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) included in the promotion.'
    )

class TradePromotionDetailResponseSchema(BaseSchema):
    '''
        Response schema for a Promotion Detail.
    '''
    id: int
    promotion_id: int
    product_id: int # Returns the internal ID

class TradePromotionBaseSchema(BaseSchema):
    '''
        Base schema for Trade Promotion (Bandeo) fields.
    '''
    name: str = Field(
        ...,
        max_length = 255,
        description = 'Name of the promotion (Bandeo).'
    )
    description: Optional[str] = Field(
        None,
        description = 'Detailed description of the promotion.'
    )
    start_date: str = Field(
        ...,
        description = 'Promotion start date (YYYY-MM-DD).'
    )
    end_date: str = Field(
        ...,
        description = 'Promotion end date (YYYY-MM-DD).'
    )
    status: Optional[str] = Field(
        'ACTIVE',
        max_length = 20,
        description = 'Status of the promotion (e.g., ACTIVE, INACTIVE, DRAFT).'
    )

class TradePromotionCreateSchema(TradePromotionBaseSchema):
    '''
        Schema for creating a new Promotion, including its nested SKUs.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company owning this promotion.'
    )
    details: List[TradePromotionDetailBaseSchema] = Field(
        ...,
        description = 'List of SKUs included in this promotion.'
    )

class TradePromotionUpdateSchema(BaseSchema):
    '''
        Schema for updating an existing Promotion (Header only).
    '''
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    status: Optional[str] = None
    # Note: Updating details (SKUs) should be handled by separate endpoints.

class TradePromotionResponseSchema(TradePromotionBaseSchema):
    '''
        Response schema for a Promotion, including its details (SKUs).
    '''
    id: int
    company_id: int
    details: List[TradePromotionDetailResponseSchema] = Field(
        [],
        description = 'List of SKU details included in this promotion.'
    )
    created_at: Optional[datetime]
    # updated_at is omitted (handled by EVENTS)

class TradePromotionFilterSchema(BaseModel):
    '''
        Schema to encapsulate filtering parameters for Promotions.
    '''
    company_id: int = Query(..., description = 'Company ID (Mandatory for filtering).')
    name: Optional[str] = Query(None, description = 'Filter by promotion name (partial match).')
    status: Optional[str] = Query(None, description = 'Filter by status (e.g., ACTIVE).')

    class Config:# pylint: disable=too-few-public-methods
        '''
            Pydantic config.
        '''
        arbitrary_types_allowed = True

class TradePromotionListResponseSchema(BaseSchema):
    '''
        Response schema for a paginated list of Promotions.
    '''
    items: List[TradePromotionResponseSchema]
    total: int

# --- B.1. IMPULSE ACTIVITIES SCHEMAS ---

# --- Schemas for Inventory Start and End ---

class ImpulseInventoryItemSchema(BaseSchema):
    '''
        Base schema for a single item in an inventory report (Start or End).
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) being reported.'
    )
    quantity: int = Field(
        ...,
        ge = 0, # Quantity cannot be negative
        description = 'Quantity counted for this SKU.'
    )

class ImpulseInventoryCreateSchema(BaseSchema):
    '''
        Schema for creating a list of inventory items (Start or End).
        The attendance_id will be passed in the URL path.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company for this transaction (needed for SKU lookup).'
    )
    items: List[ImpulseInventoryItemSchema] = Field(
        ...,
        min_length = 1, # 'min_items' is deprecated, use 'min_length'
        description = 'List of SKUs and their quantities.'
    )

class ImpulseInventoryResponseItemSchema(BaseSchema):
    '''
        Response schema for a single created inventory item.
    '''
    id: int
    attendance_id: int
    product_id: int
    quantity: int
    created_at: Optional[datetime]

class ImpulseInventoryListResponseSchema(BaseSchema):
    '''
        Response schema for a bulk creation of inventory items.
    '''
    items: List[ImpulseInventoryResponseItemSchema]
    total: int

# --- Schemas for Sale ---

class ImpulseSaleDetailCreateSchema(BaseSchema):
    '''
        Base schema for a single item (SKU) in a Sale transaction.
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) sold.'
    )
    quantity: int = Field(
        ...,
        gt = 0, # Sale quantity must be greater than 0
        description = 'Quantity sold for this SKU.'
    )

class ImpulseSaleCreateSchema(BaseSchema):
    '''
        Schema for creating a new Sale transaction.
        The attendance_id will be passed in the URL path.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company for this transaction (needed for SKU lookup).'
    )
    details: List[ImpulseSaleDetailCreateSchema] = Field(
        ...,
        min_length = 1,
        description = 'List of SKUs and quantities sold in this transaction.'
    )

class ImpulseSaleDetailResponseSchema(BaseSchema):
    '''
        Response schema for a created Sale detail.
    '''
    id: int
    impulse_sale_id: int
    product_id: int
    quantity: int

class ImpulseSaleResponseSchema(BaseSchema):
    '''
        Response schema for a created Sale Header, including its details.
    '''
    id: int
    attendance_id: int
    file_path: Optional[str]
    created_at: Optional[datetime]
    details: List[ImpulseSaleDetailResponseSchema]
