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
    update_pos_service,
    create_inventory_item_service,
    get_inventory_for_pos_service,
    update_inventory_item_service,
    delete_inventory_item_service
)
from schemas.pos import (
    POSFilterSchema,
    POSListResponseSchema,
    PointOfSaleUpdateSchema,
    PointOfSaleCreateSchema,
    PointOfSaleResponseSchema,
    POSInventoryCreateSchema,
    POSInventoryListResponseSchema,
    POSInventoryResponseSchema,
    POSInventoryUpdateSchema
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
    serialized_items = [
        PointOfSaleResponseSchema.model_validate(item, from_attributes=True) for item in items
    ]
    return POSListResponseSchema(items = serialized_items, total = total)


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
    result = await delete_pos_service(
        db = db,
        pos_id = pos_id
    )

    deleted_id = result[0] if isinstance(result, tuple) else result

    return {
        'message': f'Point of Sale with ID {deleted_id} deleted successfully.',
        'id': deleted_id
    }

# --- INVENTORY ---

@handle_service_errors('TRADE')
async def create_inventory_item_controller(
    pos_id: int,
    inventory_data: POSInventoryCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> POSInventoryResponseSchema:
    '''
        Controller to add a new inventory item to a POS.
    '''
    db_item = await create_inventory_item_service(
        db = db,
        pos_id = pos_id,
        inventory_data = inventory_data
    )
    return POSInventoryResponseSchema.model_validate(db_item, from_attributes = True)

@handle_service_errors('TRADE')
async def get_inventory_for_pos_controller(
    pos_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> POSInventoryListResponseSchema:
    '''
        Controller to list all inventory items for a specific POS.
    '''
    items, total = await get_inventory_for_pos_service(
        db = db,
        pos_id = pos_id
    )
    serialized_items = [
        POSInventoryResponseSchema.model_validate(item, from_attributes=True) for item in items
    ]
    return POSInventoryListResponseSchema(items = serialized_items, total = total)

@handle_service_errors('TRADE')
async def update_inventory_item_controller(
    inventory_id: int,
    update_data: POSInventoryUpdateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> POSInventoryResponseSchema:
    '''
        Controller to update a specific inventory item.
    '''
    db_item = await update_inventory_item_service(
        db = db,
        inventory_id = inventory_id,
        update_data = update_data
    )
    return POSInventoryResponseSchema.model_validate(db_item, from_attributes = True)

@handle_service_errors('TRADE')
async def delete_inventory_item_controller(
    inventory_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller to delete a specific inventory item.
    '''
    result = await delete_inventory_item_service(
        db = db,
        inventory_id = inventory_id
    )

    deleted_id = result[0] if isinstance(result, tuple) else result

    return {
        'message': f'Inventory item with ID {deleted_id} deleted successfully.',
        'id': deleted_id
    }
