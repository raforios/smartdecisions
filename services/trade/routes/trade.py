'''
    Trade: routes handler
'''
from typing import Any, Dict
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.trade import (
    create_product_assignment_controller,
    create_product_controller,
    create_point_of_sale_controller,
    create_sku_equivalency_controller,
    delete_pos_controller,
    delete_product_assignment_controller,
    delete_product_controller,
    delete_sku_equivalency_controller,
    get_point_of_sale_controller,
    get_pos_list_controller,
    get_product_assignment_by_id_controller,
    get_product_assignments_list_controller,
    get_product_by_id_controller,
    get_products_list_controller,
    get_sku_equivalency_by_id_controller,
    update_pos_controller,
    update_product_assignment_controller,
    update_product_controller,
    update_sku_equivalency_controller
)
from schemas.trade import (
    POSFilterSchema,
    POSListResponseSchema,
    PointOfSaleUpdateSchema,
    ProductAssignmentPOSCreateSchema,
    ProductAssignmentPOSFilterSchema,
    ProductAssignmentPOSListResponseSchema,
    ProductAssignmentPOSResponseSchema,
    ProductAssignmentPOSUpdateSchema,
    ProductCreateSchema,
    ProductFilterSchema,
    ProductListResponseSchema,
    ProductResponseSchema,
    PointOfSaleCreateSchema,
    PointOfSaleResponseSchema,
    ProductUpdateSchema,
    SKUEquivalencyCreateSchema,
    SKUEquivalencyResponseSchema,
    SKUEquivalencyUpdateSchema,
)

router = APIRouter(prefix = '/v1/trade', tags = ['Trade'])

# --- 1. PRODUCT ENDPOINTS ---

@router.post(
    '/products',
    response_model = ProductResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new product with atomic SKU generation',
    description = '''Creates a new product record and atomically generates a unique SKU
                 based on its category codes.'''
)
async def create_product_endpoint(
    product_data: ProductCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new Product.
    '''
    message = f'User: {current_user}. Received request to create product: {product_data.name}.'
    logger.info(message)
    return await create_product_controller(
        product_data = product_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/products/{product_id}',
    response_model = ProductResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Retrieve a product by ID'
)
async def get_product_by_id_endpoint(
    product_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a Product by ID.
    '''
    message = f'User: {current_user}. Received request to get product ID: {product_id}.'
    logger.info(message)
    return await get_product_by_id_controller(
        product_id = product_id,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/products',
    response_model = ProductListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List and filter products (paginated)'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments, disable=duplicate-code
async def get_products_list_endpoint(
    request: Request,
    filters: ProductFilterSchema = Depends(),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a paginated list of products based on filters.
    '''
    message = f'User: {current_user}. Received request to list products.'
    logger.info(message)
    return await get_products_list_controller(
        filters = filters,
        db = db,
        skip = skip,
        limit = limit,
        request = request,
        current_user = current_user
    )

@router.put(
    '/products/{product_id}',
    response_model = ProductResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update a product'
)
async def update_product_endpoint(
    product_id: int,
    product_data: ProductUpdateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        'Endpoint to update an existing product.'
    '''
    message = f'User: {current_user}. Received request to update product ID: {product_id}.'
    logger.info(message)
    return await update_product_controller(
        product_id = product_id,
        product_data = product_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/products/{product_id}',
    response_model = Dict[str, Any],
    status_code = status.HTTP_200_OK,
    summary = 'Delete a product'
)
async def delete_product_endpoint(
    product_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        'Endpoint to delete a product by ID.'
    '''
    message = f"'User: {current_user}. Received request to delete product ID: {product_id}.'"
    logger.info(message)
    return await delete_product_controller(
        product_id = product_id,
        db = db,
        request = request,
        current_user = current_user
    )

# --- 2. POINT OF SALE (POS) ENDPOINTS ---

@router.post(
    '/pos',
    response_model = PointOfSaleResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new Point of Sale with initial inventory',
    description = '''Creates a new Point of Sale record and its associated initial inventory
                 in a single transactional block.'''
)
async def create_point_of_sale_endpoint(
    pos_data: PointOfSaleCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new Point of Sale (POS).
    '''
    message = f'User: {current_user}. Received request to create POS: {pos_data.name}.'
    logger.info(message)
    return await create_point_of_sale_controller(
        pos_data = pos_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/pos/{pos_id}',
    response_model = PointOfSaleResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Retrieve a Point of Sale (POS) by ID'
)
async def get_point_of_sale_endpoint(
    pos_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a Point of Sale (POS) by ID.
    '''
    message = f'User: {current_user}. Received request to get POS ID: {pos_id}.'
    logger.info(message)
    return await get_point_of_sale_controller(
        pos_id = pos_id,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/pos',
    response_model = POSListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List and filter Points of Sale (paginated)'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments, disable=duplicate-code
async def get_pos_list_endpoint(
    request: Request,
    filters: POSFilterSchema = Depends(),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a paginated list of Points of Sale based on filters.
    '''
    message = f'User: {current_user}. Received request to list POS.'
    logger.info(message)
    return await get_pos_list_controller(
        filters = filters,
        db = db,
        skip = skip,
        limit = limit,
        request = request,
        current_user = current_user
    )

@router.put(
    '/pos/{pos_id}',
    response_model = PointOfSaleResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update a Point of Sale'
)
async def update_pos_endpoint(
    pos_id: int,
    pos_data: PointOfSaleUpdateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update an existing Point of Sale.
    '''
    message = f'User: {current_user}. Received request to update POS ID: {pos_id}.'
    logger.info(message)
    return await update_pos_controller(
        pos_id = pos_id,
        pos_data = pos_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/pos/{pos_id}',
    response_model = Dict[str, Any],
    status_code = status.HTTP_200_OK,
    summary = 'Delete a Point of Sale'
)
async def delete_pos_endpoint(
    pos_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a Point of Sale by ID.
    '''
    message = f'User: {current_user}. Received request to delete POS ID: {pos_id}.'
    logger.info(message)
    return await delete_pos_controller(
        pos_id = pos_id,
        db = db,
        request = request,
        current_user = current_user
    )

# --- 3. SKU EQUIVALENCY ENDPOINTS ---

@router.post(
    '/sku-equivalencies',
    response_model = SKUEquivalencyResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create SKU Equivalency'
)
async def create_sku_equivalency_endpoint(
    equivalency_data: SKUEquivalencyCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new SKU equivalency mapping.
    '''
    message = f'User: {current_user}. Received request to create SKU Equivalency.'
    logger.info(message)
    return await create_sku_equivalency_controller(
        equivalency_data = equivalency_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/sku-equivalencies/{equivalency_id}',
    response_model = SKUEquivalencyResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get SKU Equivalency by ID'
)
async def get_sku_equivalency_by_id_endpoint(
    equivalency_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a single SKU Equivalency by its ID.
    '''
    message = f'User: {current_user}. Request GET SKU Equivalency ID: {equivalency_id}.'
    logger.info(message)
    return await get_sku_equivalency_by_id_controller(
        equivalency_id = equivalency_id,
        db = db,
        request = request,
        current_user = current_user
    )

@router.put(
    '/sku-equivalencies/{equivalency_id}',
    response_model = SKUEquivalencyResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update SKU Equivalency'
)
async def update_sku_equivalency_endpoint(
    equivalency_id: int,
    update_data: SKUEquivalencyUpdateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update an SKU Equivalency mapping.
    '''
    message = f'User: {current_user}. Request UPDATE SKU Equivalency ID: {equivalency_id}.'
    logger.info(message)
    return await update_sku_equivalency_controller(
        equivalency_id = equivalency_id,
        update_data = update_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/sku-equivalencies/{equivalency_id}',
    response_model = Dict[str, Any],
    status_code = status.HTTP_200_OK,
    summary = 'Delete SKU Equivalency'
)
async def delete_sku_equivalency_endpoint(
    equivalency_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete an SKU Equivalency mapping.
    '''
    message = f'User: {current_user}. Request DELETE SKU Equivalency ID: {equivalency_id}.'
    logger.info(message)
    return await delete_sku_equivalency_controller(
        equivalency_id = equivalency_id,
        db = db,
        request = request,
        current_user = current_user
    )

# --- 4. PRODUCT ASSIGNMENT POS ENDPOINTS ---

@router.post(
    '/pos-assignments',
    response_model = ProductAssignmentPOSResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Assign Product to POS'
)
async def create_product_assignment_endpoint(
    assignment_data: ProductAssignmentPOSCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to assign a Product to a Point of Sale.
    '''
    message = f'User: {current_user}. Received request to create Product POS Assignment.'
    logger.info(message)
    return await create_product_assignment_controller(
        assignment_data = assignment_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/pos-assignments/{assignment_id}',
    response_model = ProductAssignmentPOSResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get Product POS Assignment by ID'
)
async def get_product_assignment_by_id_endpoint(
    assignment_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a single Product POS Assignment by its ID.
    '''
    message = f'User: {current_user}. Request GET Product POS Assignment ID: {assignment_id}.'
    logger.info(message)
    return await get_product_assignment_by_id_controller(
        assignment_id = assignment_id,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/pos-assignments',
    response_model = ProductAssignmentPOSListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List and filter Product POS Assignments'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments, disable=duplicate-code
async def get_product_assignments_list_endpoint(
    request: Request,
    filters: ProductAssignmentPOSFilterSchema = Depends(),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a paginated list of Product POS Assignments.
    '''
    message = f'User: {current_user}. Request list Product POS Assignments.'
    logger.info(message)
    return await get_product_assignments_list_controller(
        filters = filters,
        db = db,
        skip = skip,
        limit = limit,
        request = request,
        current_user = current_user
    )

@router.put(
    '/pos-assignments/{assignment_id}',
    response_model = ProductAssignmentPOSResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update Product POS Assignment'
)
async def update_product_assignment_endpoint(
    assignment_id: int,
    update_data: ProductAssignmentPOSUpdateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update a Product POS Assignment (e.g., status).
    '''
    message = f'User: {current_user}. Request UPDATE Product POS Assignment ID: {assignment_id}.'
    logger.info(message)
    return await update_product_assignment_controller(
        assignment_id = assignment_id,
        update_data = update_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/pos-assignments/{assignment_id}',
    response_model = Dict[str, Any],
    status_code = status.HTTP_200_OK,
    summary = 'Delete Product POS Assignment'
)
async def delete_product_assignment_endpoint(
    assignment_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a Product POS Assignment.
    '''
    message = f'User: {current_user}. Request DELETE Product POS Assignment ID: {assignment_id}.'
    logger.info(message)
    return await delete_product_assignment_controller(
        assignment_id = assignment_id,
        db = db,
        request = request,
        current_user = current_user
    )
