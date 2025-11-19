'''
    Products Controllers
'''
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from fastapi import Request
from services.logger_config import custom_logger as logger
from services.utils import (
    generic_bulk_controller_wrapper,
    handle_service_errors
)
from services.products import (
    bulk_create_products_service,
    bulk_create_sku_equivalencies_service,
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
    get_sku_equivalencies_list_service,
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
        db = db,
        filters = filters,
        skip = skip,
        limit = limit
    )
    serialized_items = [
        ProductResponseSchema.model_validate(item, from_attributes=True) for item in items
    ]

    return ProductListResponseSchema(items = serialized_items, total = total)

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
    result = await delete_product_service(
        db = db,
        product_id = product_id
    )

    deleted_id = result[0] if isinstance(result, tuple) else result

    return {
        'message': f'Product with ID {deleted_id} deleted successfully.',
        'id': deleted_id
    }

@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
async def bulk_upload_products_controller(
    db: Session,
    request: Request,
    current_user: str,
    file_name: str,
    delimiter: Optional[str] = ',',
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Controller to handle the bulk upload of Products from a file.
    '''
    message = f'Starting bulk upload for Products from file: {file_name}'
    logger.info(message)

    return await generic_bulk_controller_wrapper(
        db = db,
        request = request,
        current_user = current_user,
        file_name = file_name,
        microservice_name = 'TRADE',
        entity_name = 'Product',
        service_func = bulk_create_products_service,
        delimiter = delimiter,
        auth_token = auth_token
    )

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
    db_equivalency.product_sku = equivalency_data.product_sku

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
    db_equivalency = await update_sku_equivalency_service(
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
    deleted_id = await delete_sku_equivalency_service(
        db = db,
        equivalency_id = equivalency_id
    )
    return {
        'message': f'SKU Equivalency with ID {deleted_id} deleted successfully.',
        'id': deleted_id
    }

@handle_service_errors('TRADE')
async def get_sku_equivalencies_list_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    skip: int,
    limit: int
) -> Dict[str, Any]:
    '''
        Controller for retrieving a paginated list of SKU Equivalencies.
    '''
    items, total = await get_sku_equivalencies_list_service(
        db = db,
        skip = skip,
        limit = limit
    )

    result_items = [
        SKUEquivalencyResponseSchema.model_validate(item, from_attributes = True)
        for item in items
    ]

    return {
        'items': result_items,
        'total': total
    }

@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
async def bulk_upload_sku_equivalencies_controller(
    db: Session,
    request: Request,
    current_user: str,
    file_name: str,
    delimiter: Optional[str] = ',',
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Controller to handle the bulk upload of SKU Equivalencies from a file.
        Uses the localization pattern for manual logging.
    '''
    message = f'Starting bulk upload for SKU Equivalencies from file: {file_name}'
    logger.info(message)

    return await generic_bulk_controller_wrapper(
        db = db,
        request = request,
        current_user = current_user,
        file_name = file_name,
        microservice_name = 'TRADE',
        entity_name = 'SKUEquivalency',
        service_func = bulk_create_sku_equivalencies_service,
        delimiter = delimiter,
        auth_token = auth_token
    )

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
        db = db,
        filters = filters,
        skip = skip,
        limit = limit
    )
    serialized_items = [
        ProductAssignmentPOSResponseSchema.model_validate(item, from_attributes=True)
        for item in items
    ]

    return ProductAssignmentPOSListResponseSchema(items = serialized_items, total = total)

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
    result = await delete_product_assignment_service(
        db = db,
        assignment_id = assignment_id
    )

    deleted_id = result[0] if isinstance(result, tuple) else result

    return {
        'message': f'Product Assignment POS with ID {deleted_id} deleted successfully.',
        'id': deleted_id
    }
