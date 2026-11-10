'''
    Product master — HTTP layer: the owner's system pushes its products, keyed
    by the SKU of the producer, distributor or supplier, and every later sale
    only names them.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path as PathParam, Request, status

from core.db_connection import GET_DB_DEPENDENCY
from core.logger_config import custom_logger as logger
from core.security import get_current_owner
from controllers.products import (
    get_product_controller,
    list_products_controller,
    update_product_controller,
    upsert_products_controller
)
from schemas.products import (
    ProductBulkUpsertSchema,
    ProductListResponseSchema,
    ProductResponseSchema,
    ProductUpdateSchema,
    ProductUpsertResultSchema
)

router = APIRouter(prefix = '/v1/commercial/products', tags = ['Product master'])

_SKU = PathParam(..., min_length = 1, max_length = 64)


@router.post(
    '',
    response_model = ProductUpsertResultSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Push the product master from the owner\'s system',
    description = ('Creates the products it does not know and completes the fields it has '
                   'empty; it never overwrites a stored value, so the call is safe to repeat. '
                   'Correcting a stored value is PATCH.')
)
async def upsert_products_endpoint(
    request: Request,
    payload: ProductBulkUpsertSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ProductUpsertResultSchema:
    '''
        Feeds the product master.
    '''
    message = f'User: {current_user}. Feeding {len(payload.products)} product(s) into the master.'
    logger.info(message)
    return await upsert_products_controller(dynamodb_resource, payload, current_user, request)


@router.get(
    '',
    response_model = ProductListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The products of the account'
)
async def list_products_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ProductListResponseSchema:
    '''
        Lists the product master.
    '''
    message = f'User: {current_user}. Reading the product master.'
    logger.info(message)
    return await list_products_controller(dynamodb_resource, current_user, request)


@router.get(
    '/{sku}',
    response_model = ProductResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'One product of the account'
)
async def get_product_endpoint(
    request: Request,
    sku: str = _SKU,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ProductResponseSchema:
    '''
        Reads one product of the master.
    '''
    message = f'User: {current_user}. Reading product {sku}.'
    logger.info(message)
    return await get_product_controller(dynamodb_resource, sku, current_user, request)


@router.patch(
    '/{sku}',
    response_model = ProductResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Correct a product',
    description = 'Overwrites the attributes it names, and only those.'
)
async def update_product_endpoint(
    request: Request,
    changes: ProductUpdateSchema,
    sku: str = _SKU,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ProductResponseSchema:
    '''
        Corrects one product of the master.
    '''
    message = f'User: {current_user}. Correcting product {sku}.'
    logger.info(message)
    return await update_product_controller(dynamodb_resource, sku, changes, current_user,
                                           request)
