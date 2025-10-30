'''
    Trade Controllers
'''
from sqlalchemy.orm import Session
from fastapi import Request
from services.utils import handle_service_errors
from services.trade import (
    create_product_service,
    create_pos_with_inventory_service
)
from schemas.trade import (
    ProductCreateSchema, ProductResponseSchema,
    PointOfSaleCreateSchema, PointOfSaleResponseSchema
)

@handle_service_errors('TRADE')
async def create_product_controller(
    product_data: ProductCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductResponseSchema:
    '''
        Controller that handles the creation of a new Product, including
        atomic SKU generation.
    '''
    # 1. Call the business logic service
    db_product = await create_product_service(
        db = db,
        product_data = product_data
    )

    # 2. Return the response model, ensuring data reflects the creation (including generated SKU)
    return ProductResponseSchema.model_validate(db_product, from_attributes = True)


@handle_service_errors('TRADE')
async def create_point_of_sale_controller(
    pos_data: PointOfSaleCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PointOfSaleResponseSchema:
    '''
        Controller that handles the creation of a new Point of Sale (POS)
        and its initial inventory.
    '''
    # 1. Call the business logic service
    db_pos = await create_pos_with_inventory_service(
        db = db,
        pos_data = pos_data
    )

    # 2. Return the response model, including the nested inventory details
    return PointOfSaleResponseSchema.model_validate(db_pos, from_attributes = True)
