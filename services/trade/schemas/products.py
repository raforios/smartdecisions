'''
    Products Schemas (Request/Response)
'''
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field

from schemas.common import (
    PhotoResponseSchema,
    BaseSchema
)

# --- PRODUCT CATEGORY SCHEMAS (NEW) ---

class ProductCategoryBaseSchema(BaseSchema):
    '''
        Base schema for a product's category code.
    '''
    category_id: int = Field(..., gt = 0,
                        description = 'Numeric identifier of the category from the source system.')
    category_code: str = Field(..., max_length = 50,
                        description = 'The actual code from the external system. Feeds the SKU.')

class ProductCategoryCreateSchema(ProductCategoryBaseSchema):
    '''
        Schema for providing category codes when creating a product.
    '''

class ProductCategoryResponseSchema(ProductCategoryBaseSchema):
    '''
        Response schema for a product's category.
    '''
    id: int
    product_id: int

    class Config:# pylint: disable=too-few-public-methods
        '''
            Pydantic config.
        '''
        model_config = ConfigDict(arbitrary_types_allowed=True)

# --- PRODUCT SCHEMAS (UPDATED) ---

class ProductBaseSchema(BaseSchema):
    '''
        Base schema for product data fields, updated for flexible categories.
    '''
    name: str = Field(..., max_length = 255)
    description: Optional[str] = Field(None)

    # --- Fields from section 5.3 ---
    product_type: str = Field(..., max_length = 50) # Venta / Promocional

    # Units of Measure
    stock_unit: str = Field(..., max_length = 10)
    replenishment_unit: str = Field(..., max_length = 10)
    purchase_unit: Optional[str] = Field(None, max_length = 10)
    sale_unit: Optional[str] = Field(None, max_length = 10)

    # Stock Control thresholds live in ProductAssignmentPOS (per POS).

    # Pricing
    stock_value: Optional[Decimal] = Field(None, description = 'Decimal(10, 2)')
    purchase_price: Optional[Decimal] = Field(None, description = 'Decimal(10, 2)')
    sale_price: Optional[Decimal] = Field(None, description = 'Decimal(10, 2)')
    currency: Optional[int] = Field(None, description = 'ID from frontend app')

    # Other Data
    manufacturer: Optional[str] = Field(None, max_length = 255)
    country_of_origin: Optional[str] = Field(None, max_length = 10)
    handling_instructions: Optional[str] = None
    storage_conditions: Optional[str] = None
    special_precautions: Optional[str] = None

    status: Optional[str] = Field('ACTIVE', max_length = 20)

class ProductCreateSchema(ProductBaseSchema):
    '''
        Schema for creating a new product with its category codes.
    '''
    company_id: int
    categories: List[ProductCategoryCreateSchema] = Field(...,
                min_items = 4, description = 'List of category names and codes for this product.')

class ProductUpdateSchema(BaseSchema):
    '''
        Schema for updating an existing product. All fields are optional.
    '''
    name: Optional[str] = Field(None, max_length = 255)
    description: Optional[str] = None
    product_type: Optional[str] = Field(None, max_length = 50)
    stock_unit: Optional[str] = Field(None, max_length = 10)
    replenishment_unit: Optional[str] = Field(None, max_length = 10)
    purchase_unit: Optional[str] = Field(None, max_length = 10)
    sale_unit: Optional[str] = Field(None, max_length = 10)
    stock_value: Optional[Decimal] = Field(None, description = 'Decimal(10, 2)')
    purchase_price: Optional[Decimal] = Field(None, description = 'Decimal(10, 2)')
    sale_price: Optional[Decimal] = Field(None, description = 'Decimal(10, 2)')
    currency: Optional[int] = Field(None, description = 'Currency ID from frontend app.')
    manufacturer: Optional[str] = Field(None, max_length = 255)
    country_of_origin: Optional[str] = Field(None, max_length = 10)
    handling_instructions: Optional[str] = None
    storage_conditions: Optional[str] = None
    special_precautions: Optional[str] = None
    status: Optional[str] = Field(None, max_length = 20)
    # Categories are managed separately via their own endpoints after creation.

class ProductResponseSchema(ProductBaseSchema):
    '''
        Response schema for a product, including generated fields and relationships.
    '''
    id: int
    company_id: int = Field(..., description = 'Owner company of the product.')
    sku: str = Field(..., description = 'System-generated Stock Keeping Unit.')

    categories: List[ProductCategoryResponseSchema] = []

    photos: List[PhotoResponseSchema] = Field(default = [],
                                    description = 'List of associated photos.')
    created_at: Optional[datetime]

    class Config:# pylint: disable=too-few-public-methods
        '''
            Pydantic config.
        '''
        model_config = ConfigDict(arbitrary_types_allowed=True)

class ProductListResponseSchema(BaseSchema):
    '''
        Response schema for a paginated list of products.
    '''
    items: List[ProductResponseSchema]
    total: int

class ProductFilterSchema(BaseModel):
    '''
        Schema to encapsulate filtering parameters for Products.
    '''
    company_id: int = Query(..., description = 'Company ID (Mandatory for filtering).')
    name: Optional[str] = Query(None, description = 'Filter by product name (partial match).')
    sku: Optional[str] = Query(None, description = 'Filter by exact SKU.')
    status: Optional[str] = Query(None, description = 'Filter by status (e.g., ACTIVE).')

    class Config:# pylint: disable=too-few-public-methods
        '''
            'Pydantic config.'
        '''
        arbitrary_types_allowed = True

class ProductBulkCreateSchema(BaseSchema):
    '''
        Schema for a single row in the Product bulk upload file.
        Matches the new flat CSV structure with multiple category columns.
    '''
    company_id: int
    name: str
    description: Optional[str] = None
    product_type: str
    stock_unit: str
    replenishment_unit: str
    purchase_unit: Optional[str] = None
    sale_unit: Optional[str] = None
    stock_value: Optional[Decimal] = None
    purchase_price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    currency: Optional[int] = None
    manufacturer: Optional[str] = None
    country_of_origin: Optional[str] = None
    handling_instructions: Optional[str] = None
    storage_conditions: Optional[str] = None
    special_precautions: Optional[str] = None
    status: Optional[str] = 'ACTIVE'
    category_1_id: int
    category_1_code: str
    category_2_id: Optional[int] = None
    category_2_code: Optional[str] = None
    category_3_id: Optional[int] = None
    category_3_code: Optional[str] = None
    category_4_id: Optional[int] = None
    category_4_code: Optional[str] = None


# --- SKU EQUIVALENCY SCHEMAS ---
class SKUEquivalencyBaseSchema(BaseSchema):
    '''
        Base schema for SKU Equivalency fields.
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) to map.'
    )
    external_system_name: str = Field(
        ...,
        max_length = 100,
        description = 'Name of the external system (e.g., SAP, CLIENT_ERP).'
    )
    external_product_code: str = Field(
        ...,
        max_length = 50,
        description = 'Code of the product in the external system.'
    )
    status: Optional[str] = Field(
        'ACTIVE',
        max_length = 20,
        description = 'Status of the equivalency (e.g., ACTIVE, INACTIVE).'
    )

class SKUEquivalencyCreateSchema(SKUEquivalencyBaseSchema):
    '''
        Schema for creating a new SKU Equivalency.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company owning this mapping.'
    )

class SKUEquivalencyUpdateSchema(BaseSchema):
    '''
        Schema for updating an SKU Equivalency. All fields are optional.
    '''
    product_sku: Optional[str] = None
    external_system_name: Optional[str] = None
    external_product_code: Optional[str] = None
    status: Optional[str] = None

class SKUEquivalencyResponseSchema(SKUEquivalencyBaseSchema):
    '''
        Response schema for an SKU Equivalency.
    '''
    id: int
    company_id: int
    product_id: int
    created_at: Optional[datetime]

    class Config:# pylint: disable=too-few-public-methods
        '''
            Pydantic config.
        '''
        model_config = ConfigDict(arbitrary_types_allowed=True)

class SKUEquivalencyListResponseSchema(BaseSchema):
    '''
        Response schema for a paginated list of SKU Equivalencies.
    '''
    items: List[SKUEquivalencyResponseSchema]
    total: int

class SKUEquivalencyBulkItemSchema(BaseSchema):
    '''
        Schema for a single row in the SKU Equivalency bulk upload file.
    '''
    company_id: int
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code to map.'
    )
    external_system_name: str = Field(
        ...,
        max_length = 100,
        description = 'Name of the external system.'
    )
    external_product_code: str = Field(
        ...,
        max_length = 50,
        description = 'Code of the product in the external system.'
    )
    status: Optional[str] = Field('ACTIVE', max_length = 20)

# --- PRODUCT ASSIGNMENT POS SCHEMAS ---

class ProductAssignmentPOSBaseSchema(BaseSchema):
    '''
        Base schema for Product to POS Assignment fields.
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) to assign.'
    )
    point_of_sale_id: int = Field(
        ...,
        description = 'ID of the Point of Sale to assign the product to.'
    )
    near_expiration_days: int = Field(
        ...,
        ge = 0,
        description = 'Threshold in days to flag near-expiration stock at this POS.'
    )
    minimum_stock: int = Field(
        ...,
        ge = 0,
        description = 'Minimum stock level for this product at this POS.'
    )
    status: Optional[str] = Field(
        'ACTIVE',
        max_length = 20,
        description = 'Status of the assignment (e.g., ACTIVE, INACTIVE).'
    )
    observations: Optional[str] = Field(
        None,
        description = 'Free-text notes captured by the operator.',
    )

class ProductAssignmentPOSCreateSchema(ProductAssignmentPOSBaseSchema):
    '''
        Schema for creating a new Product to POS Assignment.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company owning this assignment.'
    )

class ProductAssignmentPOSUpdateSchema(BaseSchema):
    '''
        Schema for updating a Product to POS Assignment. To change product/pos
        identity, delete the assignment and recreate. Stock thresholds and
        status are editable.
    '''
    near_expiration_days: Optional[int] = Field(
        None,
        ge = 0,
        description = 'Threshold in days to flag near-expiration stock at this POS.'
    )
    minimum_stock: Optional[int] = Field(
        None,
        ge = 0,
        description = 'Minimum stock level for this product at this POS.'
    )
    status: Optional[str] = Field(
        None,
        max_length = 20,
        description = 'New status for the assignment.'
    )
    observations: Optional[str] = Field(
        None,
        description = 'Free-text notes captured by the operator.',
    )

class ProductSummarySchema(BaseSchema):
    '''
        Minimal product fields shipped alongside a POS assignment so the
        frontend can render the inventory grid without follow-up calls.
    '''
    sku: str
    name: str
    stock_unit: str


class ProductAssignmentPOSResponseSchema(BaseSchema):
    '''
        Response schema for a Product to POS Assignment.

        2026-05-20 (Binaria): now returns the related product summary
        (sku / name / stock_unit) so the inventory screen doesn't need
        an extra round-trip per row.
    '''
    id: int
    company_id: int
    product_id: int # Returns the internal ID
    product: Optional[ProductSummarySchema] = None
    point_of_sale_id: int
    near_expiration_days: int
    minimum_stock: int
    status: str
    observations: Optional[str] = None
    created_at: Optional[datetime]
    class Config:# pylint: disable=too-few-public-methods
        '''
            Pydantic config.
        '''
        model_config = ConfigDict(arbitrary_types_allowed=True)

class ProductAssignmentPOSFilterSchema(BaseModel):
    '''
        Schema to encapsulate filtering parameters for Product POS Assignments.
    '''
    # 2026-05-20 (Binaria): company_id pasa a opcional. Cuando no viene,
    # el listado se acota por point_of_sale_id (suficiente para pantalla
    # de inventario donde el POS implica la compañía cliente).
    company_id: Optional[int] = Query(None, description = 'Optional company filter.')
    product_id: Optional[int] = Query(None, description = 'Filter by internal Product ID.')
    point_of_sale_id: Optional[int] = Query(None, description = 'Filter by Point of Sale ID.')
    status: Optional[str] = Query(None, description = 'Filter by status (e.g., ACTIVE).')

    class Config:# pylint: disable=too-few-public-methods
        '''
            Pydantic config.
        '''
        arbitrary_types_allowed = True

class ProductAssignmentPOSListResponseSchema(BaseSchema):
    '''
        Response schema for a paginated list of Product POS Assignments.
    '''
    items: List[ProductAssignmentPOSResponseSchema]
    total: int

# --- BULK ASSIGNMENT SCHEMAS ---

class ProductAssignmentPOSBulkItemSchema(BaseSchema):
    '''
        Schema for a single row in the Product Assignment bulk upload file.
        Users typically work with Codes (SKU, POS External Code) rather than IDs.
    '''
    company_id: int
    product_sku: str = Field(
        ...,
        description = 'Internal SKU of the product to assign.'
    )
    # Opción A: Usar ID del POS (más seguro si el sistema lo conoce)
    point_of_sale_id: Optional[int] = Field(
        None,
        description = 'Internal ID of the POS.'
    )
    # Opción B: Usar código externo del POS (común en cargas masivas)
    pos_external_code: Optional[str] = Field(
        None,
        description = 'External code of the POS (alternative to ID).'
    )
    near_expiration_days: int = Field(
        ...,
        ge = 0,
        description = 'Threshold in days to flag near-expiration stock at this POS.'
    )
    minimum_stock: int = Field(
        ...,
        ge = 0,
        description = 'Minimum stock level for this product at this POS.'
    )
    status: Optional[str] = Field('ACTIVE', max_length = 20)
