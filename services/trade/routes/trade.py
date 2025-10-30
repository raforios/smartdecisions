'''
    Trade: routes handler
'''
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.trade import (
    create_product_controller,
    create_point_of_sale_controller
)
from schemas.trade import (
    ProductCreateSchema,
    ProductResponseSchema,
    PointOfSaleCreateSchema,
    PointOfSaleResponseSchema
)

router = APIRouter(prefix = '/v1/trade', tags = ['Trade'])

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

