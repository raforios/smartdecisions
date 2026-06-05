'''
    Impulses Schemas (Request/Response)
'''
from typing import List, Literal, Optional
from datetime import datetime
from fastapi import Query
from pydantic import Field, BaseModel
from schemas.common import BaseSchema, PhotoResponseSchema

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
    start_date: datetime = Field(
        ...,
        description = 'Promotion start date (YYYY-MM-DD).'
    )
    end_date: datetime = Field(
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
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    status: Optional[str] = None

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

class TradePromotionFilterSchema(BaseModel):
    '''
        Schema to encapsulate filtering parameters for Promotions.
    '''
    company_id: int = Query(..., description = 'Company ID (Mandatory for filtering).')
    name: Optional[str] = Query(None, description = 'Filter by promotion name (partial match).')
    status: Optional[str] = Query(None, description = 'Filter by status (e.g., ACTIVE).')

    class Config: # pylint: disable=too-few-public-methods
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
    observations: Optional[str] = Field(
        None,
        description = 'Free-text notes captured by the operator for this line.',
    )

class ImpulseInventoryCreateSchema(BaseSchema):
    '''
        Schema for creating a list of inventory items (Start or End).
        UPDATED: Includes pos_id for validation.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company for this transaction (needed for SKU lookup).'
    )
    pos_id: int = Field(
        ...,
        description = 'ID of the Point of Sale (sent by frontend) to validate assortment.'
    )
    items: List[ImpulseInventoryItemSchema] = Field(
        ...,
        min_length = 1,
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
    observations: Optional[str] = None
    created_at: Optional[datetime]

class ImpulseInventoryListResponseSchema(BaseSchema):
    '''
        Response schema for a bulk creation of inventory items.
    '''
    items: List[ImpulseInventoryResponseItemSchema]
    total: int


class LatestInventoryItemSchema(BaseSchema):
    '''
        Single line of the latest-inventory response.
    '''
    product_id: int
    product_sku: Optional[str] = None
    product_name: Optional[str] = None
    quantity: int
    observations: Optional[str] = None


class LatestPOSInventoryResponseSchema(BaseSchema):
    '''
        Most recent impulse inventory snapshot bound to a POS. The
        `inventory_type` flag tells whether the snapshot came from the
        start or the end of the visit.
    '''
    pos_id: int
    inventory_type: str = Field(
        ..., description = 'Either "start" or "end".',
    )
    attendance_id: int
    created_at: datetime
    items: List[LatestInventoryItemSchema]

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
    promotion_id: Optional[int] = Field(
        None,
        description = 'Optional: ID of the Promotion (Bandeo) if this item is part of a pack.'
    )

class ImpulseSaleCreateSchema(BaseSchema):
    '''
        Schema for creating a new Sale transaction.
        UPDATED: Includes pos_id for validation.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company for this transaction (needed for SKU lookup).'
    )
    client_company_id: Optional[int] = Field(
        None,
        description = (
            'Client company (owner of the POS / products). Stored on the '
            'sale row for downstream reporting.'
        ),
    )
    pos_id: int = Field(
        ...,
        description = 'ID of the Point of Sale (sent by frontend) to validate assortment.'
    )
    observations: Optional[str] = Field(
        None,
        description = (
            'Optional free-text annotation captured at the sale level '
            '(promo applied, customer remark, delivery issue, etc.).'
        ),
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
    promotion_id: Optional[int]

class ImpulseSaleResponseSchema(BaseSchema):
    '''
        Response schema for a created Sale Header, including its details.
    '''
    id: int
    attendance_id: int
    company_id: Optional[int] = None
    client_company_id: Optional[int] = None
    observations: Optional[str] = None
    # photos removed (handled by common schema/endpoint structure generally)
    photos: List[PhotoResponseSchema] = []
    created_at: Optional[datetime]
    details: List[ImpulseSaleDetailResponseSchema]


# 2026-05-28 (Binaria): cross-attendance sales listing. Filterable by
# company, POS, user and date range; every filter is optional. The
# `type` field is included as a forward-compat slot so future
# replenishment-side sales can land in the same listing.
SaleType = Literal['IMPULSE']


class SaleListFilterSchema(BaseModel):
    '''
        Query filters for GET /v1/impulses/sales. All optional; an empty
        filter returns every sale the caller is authorized to see.
    '''
    company_id: Optional[int] = Query(None, description = 'Executor company.')
    client_company_id: Optional[int] = Query(None, description = 'Client company.')
    pos_id: Optional[int] = Query(None, description = 'Filter by point of sale.')
    user_id: Optional[int] = Query(None, description = 'Filter by operator user id.')
    date_from: Optional[datetime] = Query(
        None, description = 'Inclusive lower bound on created_at.',
    )
    date_to: Optional[datetime] = Query(
        None, description = 'Inclusive upper bound on created_at.',
    )
    type: SaleType = Query('IMPULSE', description = 'Sale type. Today only IMPULSE.')


class SaleListItemDetailSchema(BaseSchema):
    '''
        2026-05-31 (Binaria): per-product breakdown shipped on each row of
        the sales listing so reports can sum quantities by SKU without an
        extra round-trip.
    '''
    product_id: int
    product_sku: str
    product_name: str
    quantity: int
    promotion_id: Optional[int] = None


class SaleListItemSchema(BaseSchema):
    '''
        Row in the unified sales listing. Aggregated totals are
        precomputed so the frontend can render the table without a
        second round-trip per row; `details` ships the per-product
        breakdown for use cases that need to sum quantities per SKU.
    '''
    id: int
    # 2026-06-05 (Binaria): explicit alias of `id` so consumers can
    # group detail rows and look up photos (entity_type='IMPULSE_SALE',
    # entity_id=sale_id) without guessing what the generic `id` refers to.
    sale_id: int
    type: SaleType
    attendance_id: int
    pos_id: Optional[int]
    user_id: int
    company_id: Optional[int]
    client_company_id: Optional[int]
    observations: Optional[str]
    total_items: int = Field(..., description = 'Distinct product count.')
    total_quantity: int = Field(..., description = 'Sum of detail quantities.')
    details: List[SaleListItemDetailSchema] = Field(
        default_factory = list,
        description = 'Per-product breakdown of the sale.',
    )
    created_at: datetime


class SaleListResponseSchema(BaseSchema):
    '''
        Paginated container for the sales listing.
    '''
    items: List[SaleListItemSchema]
    total: int


# 2026-05-28 (Binaria): per-POS stock projection. Decides between the
# open-attendance computation (start - sales) and the closed-attendance
# snapshot (end inventory).
class POSStockItemSchema(BaseSchema):
    '''
        Available stock for a single product at a POS, with the product
        metadata needed by the frontend to render a row.
    '''
    product_id: int
    product_sku: str
    product_name: str
    available_qty: int


class POSStockResponseSchema(BaseSchema):
    '''
        Stock snapshot for a POS. `source` documents which formula was
        applied: 'inventory_start_minus_sales' when the latest visit is
        still open, 'inventory_end' when it was already closed.
    '''
    pos_id: int
    attendance_id: Optional[int] = None
    is_open: bool
    source: Literal['inventory_start_minus_sales', 'inventory_end', 'empty']
    computed_at: datetime
    items: List[POSStockItemSchema]


# 2026-05-20 (Binaria): per-visit GET endpoints (start/end). Returns the
# full list of products counted on that visit, with summary product
# fields so the frontend can build the cierre screen without extra
# calls.
class VisitInventoryResponseSchema(BaseSchema):
    '''
        Snapshot of all inventory lines tied to one Impulse visit (start
        or end). Used by the two new GET endpoints behind
        `/v1/impulses/visit/{attendance_id}/inventory-{start,end}`.
    '''
    attendance_id: int
    pos_id: Optional[int] = None
    inventory_type: str = Field(..., description = '"start" or "end".')
    created_at: Optional[datetime] = None
    items: List[LatestInventoryItemSchema]
