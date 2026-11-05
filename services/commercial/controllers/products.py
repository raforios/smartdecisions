'''
    The product master: the API door and the reading side. The other door,
    the sales file, feeds the same service from the load. Everything that
    changes the master is audited.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.products import (
    ProductBulkUpsertSchema,
    ProductListResponseSchema,
    ProductResponseSchema,
    ProductSource,
    ProductUpdateSchema,
    ProductUpsertResultSchema
)
from services.products import (
    get_product,
    list_products,
    to_product_response,
    update_product,
    upsert_products
)
from services.utils import audit_event, handle_service_errors


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Product', 'UPLOAD')
async def upsert_products_controller(
    dynamodb_resource: ServiceResource,
    payload: ProductBulkUpsertSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ProductUpsertResultSchema:
    '''
        Feeds the master from the owner's system: creates what is missing and
        completes what is empty, so the call is safe to repeat.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            payload (ProductBulkUpsertSchema): Products pushed by the system.
            current_user (str): Authenticated caller and owner of the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ProductUpsertResultSchema: Created, completed and unchanged counts.
    '''
    return upsert_products(dynamodb_resource, current_user, payload.products,
                           ProductSource.API)


@handle_service_errors('COMMERCIAL')
async def list_products_controller(
    dynamodb_resource: ServiceResource,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ProductListResponseSchema:
    '''
        The owner's products.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            current_user (str): Authenticated caller and owner of the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ProductListResponseSchema: The products and how many.
    '''
    return list_products(dynamodb_resource, current_user)


@handle_service_errors('COMMERCIAL')
async def get_product_controller(
    dynamodb_resource: ServiceResource,
    sku: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ProductResponseSchema:
    '''
        One product of the owner's master.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            sku (str): The product's SKU.
            current_user (str): Authenticated caller and owner of the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ProductResponseSchema: The stored product.
    '''
    return to_product_response(get_product(dynamodb_resource, current_user, sku))


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Product', 'UPDATE')
async def update_product_controller(
    dynamodb_resource: ServiceResource,
    sku: str,
    changes: ProductUpdateSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ProductResponseSchema:
    '''
        Corrects a product, overwriting what the payload names.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            sku (str): The product's SKU.
            changes (ProductUpdateSchema): Attributes to overwrite.
            current_user (str): Authenticated caller and owner of the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ProductResponseSchema: The product after the change.
    '''
    return to_product_response(update_product(dynamodb_resource, current_user, sku, changes))
