'''
    Replenishments Schemas (Request/Response)
'''
from typing import List, Optional
from datetime import datetime
from pydantic import Field
from schemas.common import BaseSchema

# --- B.2. REPLENISHMENT ACTIVITIES SCHEMAS ---

# --- Schemas for Replenishment Report ---

class ReplenishmentReportCreateSchema(BaseSchema):
    '''
        Schema for creating a Replenishment Report (Success Photos).
        The attendance_id will be passed in the URL path.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company for this transaction.'
    )
    comments: Optional[str] = Field(
        None,
        description = 'Optional comments from the user.'
    )

class ReplenishmentReportResponseSchema(BaseSchema):
    '''
        Response schema for a created Replenishment Report.
    '''
    id: int
    attendance_id: int
    file_path_1: Optional[str]
    file_path_2: Optional[str]
    file_path_3: Optional[str]
    comments: Optional[str]
    created_at: Optional[datetime]

# --- Schemas for Replenishment Inventory ---

class ReplenishmentInventoryItemSchema(BaseSchema):
    '''
        Base schema for a single item in a Replenishment Inventory report.
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) being reported.'
    )
    batch_number: str = Field(
        ...,
        max_length = 50,
        description = 'Batch or lot number of the product.'
    )
    expiration_date: str = Field(
        ...,
        description = 'Expiration date of the product (YYYY-MM-DD).'
    )
    quantity: int = Field(
        ...,
        ge = 0, # Quantity cannot be negative
        description = 'Quantity counted for this SKU/Batch/Expiration.'
    )

class ReplenishmentInventoryCreateSchema(BaseSchema):
    '''
        Schema for creating a list of detailed inventory items (Replenishment).
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company (needed for SKU lookup).'
    )
    items: List[ReplenishmentInventoryItemSchema] = Field(
        ...,
        min_length = 1,
        description = 'List of SKUs and their quantities/batches/expirations.'
    )

class ReplenishmentInventoryResponseItemSchema(BaseSchema):
    '''
        Response schema for a single created replenishment inventory item.
    '''
    id: int
    attendance_id: int
    product_id: int
    batch_number: str
    expiration_date: datetime # Returns as datetime
    quantity: int
    created_at: Optional[datetime]

class ReplenishmentInventoryListResponseSchema(BaseSchema):
    '''
        Response schema for a bulk creation of replenishment inventory items.
    '''
    items: List[ReplenishmentInventoryResponseItemSchema]
    total: int

# --- Schemas for Replenishment Reception ---

class ReplenishmentReceptionItemSchema(BaseSchema):
    '''
        Base schema for a single item received from a supplier.
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) received.'
    )
    quantity_received: int = Field(
        ...,
        gt = 0, # Received quantity must be greater than 0
        description = 'Quantity received for this SKU.'
    )
    comments: Optional[str] = Field(
        None,
        description = 'Optional comments for this specific item.'
    )

class ReplenishmentReceptionCreateSchema(BaseSchema):
    '''
        Schema for creating a list of received items (Supplier Reception).
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company (needed for SKU lookup).'
    )
    items: List[ReplenishmentReceptionItemSchema] = Field(
        ...,
        min_length = 1,
        description = 'List of SKUs and quantities received.'
    )

class ReplenishmentReceptionResponseItemSchema(BaseSchema):
    '''
        Response schema for a single created reception item.
    '''
    id: int
    attendance_id: int
    product_id: int
    quantity_received: int
    comments: Optional[str]
    created_at: Optional[datetime]

class ReplenishmentReceptionListResponseSchema(BaseSchema):
    '''
        Response schema for a bulk creation of reception items.
    '''
    items: List[ReplenishmentReceptionResponseItemSchema]
    total: int

# --- B.3. COMPLEMENTARY ACTIVITIES SCHEMAS ---

# --- Schemas for Bandeo Report ---

class ComplementaryBandeoDetailCreateSchema(BaseSchema):
    '''
        Base schema for a single item (SKU) returned in a Bandeo report.
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) being returned.'
    )
    quantity_returned: int = Field(
        ...,
        gt = 0, # Returned quantity must be greater than 0
        description = 'Quantity returned for this SKU.'
    )

class ComplementaryBandeoCreateSchema(BaseSchema):
    '''
        Schema for creating a new Bandeo Report (Returns and Photos).
        The attendance_id will be passed in the URL path.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company (needed for SKU lookup).'
    )
    comments: Optional[str] = Field(
        None,
        description = 'Optional comments for the bandeo report.'
    )
    details: List[ComplementaryBandeoDetailCreateSchema] = Field(
        ...,
        min_length = 1,
        description = 'List of SKUs and quantities returned.'
    )

class ComplementaryBandeoDetailResponseSchema(BaseSchema):
    '''
        Response schema for a created Bandeo detail (returned item).
    '''
    id: int
    bandeo_header_id: int
    product_id: int
    quantity_returned: int

class ComplementaryBandeoResponseSchema(BaseSchema):
    '''
        Response schema for a created Bandeo Header, including its details.
    '''
    id: int
    attendance_id: int
    file_path_1: Optional[str]
    file_path_2: Optional[str]
    comments: Optional[str]
    created_at: Optional[datetime]
    details: List[ComplementaryBandeoDetailResponseSchema]

# --- Schemas for Promotional Point Report ---

class ComplementaryPromoPointCreateSchema(BaseSchema):
    '''
        Schema for creating a Promotional Point Report (Photos).
        The attendance_id will be passed in the URL path.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company for this transaction.'
    )
    comments: Optional[str] = Field(
        None,
        description = 'Optional comments from the user.'
    )

class ComplementaryPromoPointResponseSchema(BaseSchema):
    '''
        Response schema for a created Promotional Point Report.
    '''
    id: int
    attendance_id: int
    file_path_1: Optional[str]
    file_path_2: Optional[str]
    comments: Optional[str]
    created_at: Optional[datetime]

# --- Schemas for Competition Report ---

class ComplementaryCompetitionCreateSchema(BaseSchema):
    '''
        Schema for creating a general Competition Report.
        This is not tied to a specific attendance_id.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company this report belongs to.'
    )
    user_id: int = Field(
        ...,
        description = 'ID of the user creating the report (from frontend session).'
    )
    point_of_sale_id: Optional[int] = Field(
        None,
        description = 'Optional: ID of the POS where the activity was observed.'
    )
    competitor_name: str = Field(
        ...,
        max_length = 255,
        description = 'Name of the competitor.'
    )
    activity_type: Optional[str] = Field(
        None,
        max_length = 255,
        description = 'Type of activity observed (e.g., "New Product", "Discount").'
    )
    product_name: Optional[str] = Field(
        None,
        max_length = 255,
        description = "Competitor's product name, if applicable."
    )
    details: Optional[str] = Field(
        None,
        description = 'General comments or details about the activity.'
    )

class ComplementaryCompetitionResponseSchema(BaseSchema):
    '''
        Response schema for a created Competition Report.
    '''
    id: int
    user_id: int
    company_id: int
    point_of_sale_id: Optional[int]
    competitor_name: str
    activity_type: Optional[str]
    product_name: Optional[str]
    details: Optional[str]
    file_path_1: Optional[str]
    created_at: Optional[datetime]
