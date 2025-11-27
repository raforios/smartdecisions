'''
    POS Controllers
'''
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from fastapi import Request
from services.logger_config import custom_logger as logger
from services.utils import (
    generic_bulk_controller_wrapper,
    handle_service_errors
)
from services.pos import (
    bulk_create_points_of_sale_service,
    bulk_create_pos_inventory_service,
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

def _map_inventory_item_to_schema(
    item: Any
) -> POSInventoryResponseSchema:
    '''
        Mapea manualmente el objeto de BD al schema de respuesta Pydantic.
    '''
    return POSInventoryResponseSchema(
        **item.__dict__,
        product_sku = item.product.sku if item.product else 'N/A',
        product_name = item.product.name if item.product else 'N/A'
    )

def _map_pos_to_schema(
    db_pos: Any
) -> PointOfSaleResponseSchema:
    '''
        Mapea manualmente el objeto POS de BD al schema de respuesta Pydantic,
        incluyendo su inventario anidado.
    '''
    pos_dict = db_pos.__dict__

    pos_dict['inventory'] = [
        _map_inventory_item_to_schema(item) for item in db_pos.inventory
    ]

    return PointOfSaleResponseSchema.model_validate(pos_dict, from_attributes = True)


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
    return _map_pos_to_schema(db_pos)

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
    return _map_pos_to_schema(db_pos)

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
        _map_pos_to_schema(item) for item in items
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
    return _map_pos_to_schema(db_pos)

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

@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def bulk_upload_pos_controller(
    db: Session,
    request: Request,
    current_user: str,
    file_name: str,
    delimiter: Optional[str] = ',',
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Controller to handle the bulk upload of Points of Sale from a file.
    '''
    message = f'Starting bulk upload for POS from file: {file_name}'
    logger.info(message)

    # Argumentos reordenados para evitar R0801 (código duplicado) con products.py
    return await generic_bulk_controller_wrapper(
        service_func = bulk_create_points_of_sale_service,
        entity_name = 'PointOfSale',
        microservice_name = 'TRADE',
        file_name = file_name,
        delimiter = delimiter,
        auth_token = auth_token,
        request = request,
        current_user = current_user,
        db = db
    )

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
    return _map_inventory_item_to_schema(db_item)

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
        _map_inventory_item_to_schema(item) for item in items
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
    return _map_inventory_item_to_schema(db_item)

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

@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def bulk_upload_pos_inventory_controller(
    db: Session,
    request: Request,
    current_user: str,
    file_name: str,
    delimiter: Optional[str] = ',',
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Controller to handle the bulk upload of POS Inventory from a file.
    '''
    # Argumentos reordenados para evitar R0801 (código duplicado) con products.py
    return await generic_bulk_controller_wrapper(
        service_func = bulk_create_pos_inventory_service,
        entity_name = 'POSInventory',
        microservice_name = 'TRADE',
        file_name = file_name,
        delimiter = delimiter,
        auth_token = auth_token,
        request = request,
        current_user = current_user,
        db = db
    )
