'''
    Products: routes handler
'''
from typing import Any, Dict, Optional
from fastapi import (
    APIRouter,
    Depends,
    Header,
    Query,
    Request,
    status
)
from sqlalchemy.orm import Session
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.products import (
    bulk_upload_product_assignments_controller,
    bulk_upload_products_controller,
    bulk_upload_sku_equivalencies_controller,
    create_product_assignment_controller,
    create_product_controller,
    create_sku_equivalency_controller,
    delete_product_assignment_controller,
    delete_product_controller,
    delete_sku_equivalency_controller,
    get_product_assignment_by_id_controller,
    get_product_assignments_list_controller,
    get_product_by_id_controller,
    get_products_list_controller,
    get_sku_equivalencies_list_controller,
    get_sku_equivalency_by_id_controller,
    update_product_assignment_controller,
    update_product_controller,
    update_sku_equivalency_controller
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
    SKUEquivalencyListResponseSchema,
    SKUEquivalencyResponseSchema,
    SKUEquivalencyUpdateSchema,
)

router = APIRouter(prefix = '/v1/products', tags = ['Products'])

# --- 1. STATIC PRODUCT ENDPOINTS ---

@router.post(
    '/',
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
        request = request,
        db = db,
        current_user = current_user
    )

@router.get(
    '/',
    response_model = ProductListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List and filter products (paginated)'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
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
        request = request,
        db = db,
        skip = skip,
        limit = limit,
        current_user = current_user
    )

# --- BULK PRODUCT ---

@router.post(
    '/bulk-upload',
    response_model = Dict[str, Any],
    status_code = status.HTTP_201_CREATED,
    summary = 'Bulk upload Products with atomic SKU generation'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def bulk_upload_products_endpoint(
    request: Request,
    file_name: str = Query(...,
            description = 'Name of the file to process (from FILES microservice).'),
    delimiter: Optional[str] = Query(
        ',', description = 'The delimiter used in the file. Defaults to a comma (,).'
    ),
    db: Session = Depends(GET_DB_DEPENDENCY),
    auth_token: str = Header(..., alias = 'Authorization'),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to trigger a bulk upload of Product data from a file, generating SKUs atomically.
    '''
    message = f'User: {current_user}. Processing bulk upload for Products from: {file_name}'
    logger.info(message)

    # Reordered arguments to avoid code duplication detection with POS
    return await bulk_upload_products_controller(
        request = request,
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        delimiter = delimiter,
        current_user = current_user
    )

# --- 2. STATIC SKU EQUIVALENCY ENDPOINTS ---

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
        request = request,
        db = db,
        current_user = current_user
    )

@router.get(
    '/sku-equivalencies',
    response_model = SKUEquivalencyListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List SKU Equivalencies'
)
async def get_sku_equivalencies_list_endpoint(
    request: Request,
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to list SKU equivalencies.
    '''
    message = f'User: {current_user}. Request list SKU Equivalencies.'
    logger.info(message)

    return await get_sku_equivalencies_list_controller(
        request = request,
        db = db,
        skip = skip,
        limit = limit,
        current_user = current_user
    )

# --- BULK SKU EQUIVALENCY ---

@router.post(
    '/sku-equivalencies/bulk-upload',
    response_model = Dict[str, Any],
    status_code = status.HTTP_201_CREATED,
    summary = 'Bulk upload SKU Equivalencies from a file'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def bulk_upload_sku_equivalencies_endpoint(
    request: Request,
    file_name: str = Query(...,
            description = 'Name of the file to process (from FILES microservice).'),
    delimiter: Optional[str] = Query(
        ',', description = 'The delimiter used in the file. Defaults to a comma (,).'
    ),
    db: Session = Depends(GET_DB_DEPENDENCY),
    auth_token: str = Header(..., alias = 'Authorization'),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to trigger a bulk upload of SKU Equivalency data from a file.
    '''
    message = f'User: {current_user}. Processing bulk upload for SKU Equivalencies from: {
            file_name}'
    logger.info(message)

    return await bulk_upload_sku_equivalencies_controller(
        request = request,
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        delimiter = delimiter,
        current_user = current_user
    )

# --- 3. STATIC POS ASSIGNMENTS ENDPOINTS ---
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
        request = request,
        db = db,
        current_user = current_user
    )

@router.post(
    '/pos-assignments/bulk-upload',
    response_model = Dict[str, Any],
    status_code = status.HTTP_201_CREATED,
    summary = 'Bulk upload Product Assignments from a file'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def bulk_upload_product_assignments_endpoint(
    request: Request,
    file_name: str = Query(...,
            description = 'Name of the file to process (from FILES microservice).'),
    delimiter: Optional[str] = Query(
        ',', description = 'The delimiter used in the file. Defaults to a comma (,).'
    ),
    db: Session = Depends(GET_DB_DEPENDENCY),
    auth_token: str = Header(..., alias = 'Authorization'),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to trigger a bulk upload of Product Assignments.
        Accepts CSV with 'product_sku' and either 'point_of_sale_id' or 'pos_external_code'.
    '''
    message = f'User: {current_user}. Processing bulk upload for Product Assignments.'
    logger.info(message)

    return await bulk_upload_product_assignments_controller(
        request = request,
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        delimiter = delimiter,
        current_user = current_user
    )

@router.get(
    '/pos-assignments',
    response_model = ProductAssignmentPOSListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List and filter Product POS Assignments'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
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
        request = request,
        db = db,
        skip = skip,
        limit = limit,
        current_user = current_user
    )

# --- 1. DYNAMIC PRODUCT ENDPOINTS ---
@router.get(
    '/{product_id}',
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
        request = request,
        db = db,
        current_user = current_user
    )

@router.patch(
    '/{product_id}',
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
        Endpoint to update an existing product.
    '''
    message = f'User: {current_user}. Received request to update product ID: {product_id}.'
    logger.info(message)
    return await update_product_controller(
        product_id = product_id,
        product_data = product_data,
        request = request,
        db = db,
        current_user = current_user
    )

@router.delete(
    '/{product_id}',
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
        Endpoint to delete a product by ID.
    '''
    message = f'User: {current_user}. Received request to delete product ID: {product_id}.'
    logger.info(message)
    return await delete_product_controller(
        product_id = product_id,
        request = request,
        db = db,
        current_user = current_user
    )

# --- 2. DYNAMIC SKU EQUIVALENCY ENDPOINTS ---

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
        request = request,
        db = db,
        current_user = current_user
    )

@router.patch(
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
        request = request,
        db = db,
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
        request = request,
        db = db,
        current_user = current_user
    )

# --- 3. DYNAMIC PRODUCT ASSIGNMENT POS ENDPOINTS ---

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
        request = request,
        db = db,
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
        request = request,
        db = db,
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
        request = request,
        db = db,
        current_user = current_user
    )
