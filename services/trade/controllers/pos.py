'''
    POS Controllers
'''
from typing import Any, Dict
from sqlalchemy.orm import Session
from fastapi import Request
from services.utils import handle_service_errors
from services.pos import (
    create_pos_with_inventory_service,
    delete_pos_service,
    get_pos_by_id_service,
    get_pos_list_service,
    update_pos_service
)
from schemas.pos import (
    POSFilterSchema,
    POSListResponseSchema,
    PointOfSaleUpdateSchema,
    PointOfSaleCreateSchema,
    PointOfSaleResponseSchema
)

# --- POST Controllers ---
@handle_service_errors('TRADE')
async def create_point_of_sale_controller(
    pos_data: PointOfSaleCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PointOfSaleResponseSchema:
    '''
        Controller that handles the creation of a new Point of Sale (POS).
    '''
    db_pos = await create_pos_with_inventory_service(
        db = db,
        pos_data = pos_data
    )
    return PointOfSaleResponseSchema.model_validate(db_pos, from_attributes = True)

# --- GET Controllers ---
@handle_service_errors('TRADE')
async def get_point_of_sale_controller(
    pos_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PointOfSaleResponseSchema:
    '''
        Controller that handles the retrieval of a single Point of Sale (POS).
    '''
    db_pos = await get_pos_by_id_service(
        db = db,
        pos_id = pos_id
    )
    return PointOfSaleResponseSchema.model_validate(db_pos, from_attributes = True)

@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_pos_list_controller(
    filters: POSFilterSchema,
    db: Session,
    skip: int,
    limit: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> POSListResponseSchema:
    '''
        Controller for retrieving a paginated list of Points of Sale based on filters.
    '''
    items, total = await get_pos_list_service(
        db = db, filters = filters, skip = skip, limit = limit
    )
    return POSListResponseSchema(items = items, total = total)

# --- PUT/PATCH Controllers ---
@handle_service_errors('TRADE')
async def update_pos_controller(
    pos_id: int,
    pos_data: PointOfSaleUpdateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PointOfSaleResponseSchema:
    '''
        Controller for updating an existing Point of Sale.
    '''
    db_pos = await update_pos_service(
        db = db,
        pos_id = pos_id,
        pos_data = pos_data
    )
    return PointOfSaleResponseSchema.model_validate(db_pos, from_attributes = True)

# --- DELETE Controllers ---
@handle_service_errors('TRADE')
async def delete_pos_controller(
    pos_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller to delete a Point of Sale by its ID.
    '''
    deleted_id, _ = await delete_pos_service(
        db = db,
        pos_id = pos_id
    )
    return {
        'message': f'Point of Sale with ID {deleted_id} deleted successfully.',
        'id': deleted_id
    }
