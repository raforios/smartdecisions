'''
    Products Controllers
'''
from typing import Any, Dict
from sqlalchemy.orm import Session
from fastapi import Request
from services.utils import handle_service_errors
from services.products import (
    create_product_assignment_service,
    create_product_service,
    create_sku_equivalency_service,
    delete_product_assignment_service,
    delete_product_service,
    delete_sku_equivalency_service,
    get_product_assignment_by_id_service,
    get_product_assignments_list_service,
    get_product_by_id_service,
    get_products_list_service,
    get_sku_equivalency_by_id_service,
    update_product_assignment_service,
    update_product_service,
    update_sku_equivalency_service
)
from schemas.products import (
    ProductAssignmentPOSCreateSchema,
    ProductAssignmentPOSFilterSchema,
    ProductAssignmentPOSListResponseSchema,
    ProductAssignmentPOSResponseSchema,
    ProductAssignmentPOSUpdateSchema,
    ProductCreateSchema,
    ProductFilterSchema,
    ProductListResponseSchema,
    ProductResponseSchema,
    ProductUpdateSchema,
    SKUEquivalencyCreateSchema,
    SKUEquivalencyResponseSchema,
    SKUEquivalencyUpdateSchema
)

# --- POST Controllers ---
@handle_service_errors('TRADE')
async def create_product_controller(
    product_data: ProductCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductResponseSchema:
    '''
        Controller that handles the creation of a new Product.
    '''
    db_product = await create_product_service(
        db = db,
        product_data = product_data
    )
    return ProductResponseSchema.model_validate(db_product, from_attributes = True)

# --- GET Controllers ---

@handle_service_errors('TRADE')
async def get_product_by_id_controller(
    product_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductResponseSchema:
    '''
        Controller that handles the retrieval of a single Product by its ID.
    '''
    db_product = await get_product_by_id_service(
        db = db,
        product_id = product_id
    )
    return ProductResponseSchema.model_validate(db_product, from_attributes = True)

@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_products_list_controller(
    filters: ProductFilterSchema,
    db: Session,
    skip: int,
    limit: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductListResponseSchema:
    '''
        Controller for retrieving a paginated list of products based on filters.
    '''
    items, total = await get_products_list_service(
        db = db, filters = filters, skip = skip, limit = limit
    )
    return ProductListResponseSchema(items = items, total = total)

# --- PUT/PATCH Controllers ---

@handle_service_errors('TRADE')
async def update_product_controller(
    product_id: int,
    product_data: ProductUpdateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductResponseSchema:
    '''
        Controller for updating an existing product.
    '''
    db_product = await update_product_service(
        db = db,
        product_id = product_id,
        product_data = product_data
    )
    return ProductResponseSchema.model_validate(db_product, from_attributes = True)

# --- DELETE Controllers ---

@handle_service_errors('TRADE')
async def delete_product_controller(
    product_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller to delete a product by its ID.
    '''
    deleted_id, _ = await delete_product_service(
        db = db,
        product_id = product_id
    )
    return {
        'message': f'Product with ID {deleted_id} deleted successfully.',
        'id': deleted_id
    }

# --- SKU EQUIVALENCY Controllers ---

@handle_service_errors('TRADE')
async def create_sku_equivalency_controller(
    equivalency_data: SKUEquivalencyCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> SKUEquivalencyResponseSchema:
    '''
        Controller for creating a new SKU Equivalency.
    '''
    db_equivalency = await create_sku_equivalency_service(
        db = db,
        equivalency_data = equivalency_data
    )
    return SKUEquivalencyResponseSchema.model_validate(
        db_equivalency, from_attributes = True
    )

@handle_service_errors('TRADE')
async def get_sku_equivalency_by_id_controller(
    equivalency_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> SKUEquivalencyResponseSchema:
    '''
        Controller for retrieving a single SKU Equivalency by ID.
    '''
    db_equivalency = await get_sku_equivalency_by_id_service(
        db = db,
        equivalency_id = equivalency_id
    )
    return SKUEquivalencyResponseSchema.model_validate(
        db_equivalency, from_attributes = True
    )

@handle_service_errors('TRADE')
async def update_sku_equivalency_controller(
    equivalency_id: int,
    update_data: SKUEquivalencyUpdateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> SKUEquivalencyResponseSchema:
    '''
        Controller for updating an SKU Equivalency.
    '''
    db_equivalency, _ = await update_sku_equivalency_service(
        db = db,
        equivalency_id = equivalency_id,
        update_data = update_data
    )
    return SKUEquivalencyResponseSchema.model_validate(
        db_equivalency, from_attributes = True
    )

@handle_service_errors('TRADE')
async def delete_sku_equivalency_controller(
    equivalency_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller for deleting an SKU Equivalency.
    '''
    deleted_id, _ = await delete_sku_equivalency_service(
        db = db,
        equivalency_id = equivalency_id
    )
    return {
        'message': f'SKU Equivalency with ID {deleted_id} deleted successfully.',
        'id': deleted_id
    }

# --- PRODUCT ASSIGNMENT POS Controllers ---

@handle_service_errors('TRADE')
async def create_product_assignment_controller(
    assignment_data: ProductAssignmentPOSCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductAssignmentPOSResponseSchema:
    '''
        Controller for creating a new Product to POS Assignment.
    '''
    db_assignment = await create_product_assignment_service(
        db = db,
        assignment_data = assignment_data
    )
    return ProductAssignmentPOSResponseSchema.model_validate(
        db_assignment, from_attributes = True
    )

@handle_service_errors('TRADE')
async def get_product_assignment_by_id_controller(
    assignment_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductAssignmentPOSResponseSchema:
    '''
        Controller for retrieving a single Product to POS Assignment by ID.
    '''
    db_assignment = await get_product_assignment_by_id_service(
        db = db,
        assignment_id = assignment_id
    )
    return ProductAssignmentPOSResponseSchema.model_validate(
        db_assignment, from_attributes = True
    )

@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_product_assignments_list_controller(
    filters: ProductAssignmentPOSFilterSchema,
    db: Session,
    skip: int,
    limit: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductAssignmentPOSListResponseSchema:
    '''
        Controller for retrieving a paginated list of Product POS Assignments.
    '''
    items, total = await get_product_assignments_list_service(
        db = db, filters = filters, skip = skip, limit = limit
    )
    return ProductAssignmentPOSListResponseSchema(items = items, total = total)

@handle_service_errors('TRADE')
async def update_product_assignment_controller(
    assignment_id: int,
    update_data: ProductAssignmentPOSUpdateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductAssignmentPOSResponseSchema:
    '''
        Controller for updating a Product to POS Assignment.
    '''
    db_assignment, _ = await update_product_assignment_service(
        db = db,
        assignment_id = assignment_id,
        update_data = update_data
    )
    return ProductAssignmentPOSResponseSchema.model_validate(
        db_assignment, from_attributes = True
    )

@handle_service_errors('TRADE')
async def delete_product_assignment_controller(
    assignment_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller for deleting a Product to POS Assignment.
    '''
    deleted_id, _ = await delete_product_assignment_service(
        db = db,
        assignment_id = assignment_id
    )
    return {
        'message': f'Product Assignment POS with ID {deleted_id} deleted successfully.',
        'id': deleted_id
    }
