'''
    POS: routes handler
'''
from typing import Any, Dict
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
    status
)
from sqlalchemy.orm import Session
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.pos import (
    create_point_of_sale_controller,
    delete_pos_controller,
    get_point_of_sale_controller,
    get_pos_list_controller,
    update_pos_controller,
    create_inventory_item_controller,
    get_inventory_for_pos_controller,
    update_inventory_item_controller,
    delete_inventory_item_controller
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

router = APIRouter(prefix = '/v1/pos', tags = ['POS'])

# --- 1. POINT OF SALE (POS) ENDPOINTS ---

@router.post(
    '/',
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
    '/{pos_id}',
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
    '/',
    response_model = POSListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List and filter Points of Sale (paginated)'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments, duplicate-code
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
    '/{pos_id}',
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
    '/{pos_id}',
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

# --- 2. POS INVENTORY ENDPOINTS ---

@router.post(
    '/{pos_id}/inventory',
    response_model = POSInventoryResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Add a new inventory item to a POS'
)
async def create_inventory_item_endpoint(
    pos_id: int,
    inventory_data: POSInventoryCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to add a new inventory item (SKU, batch, location)
        to an existing Point of Sale.
    '''
    message = f'User: {current_user}. Request to add inventory to POS ID: {pos_id}.'
    logger.info(message)
    return await create_inventory_item_controller(
        pos_id = pos_id,
        inventory_data = inventory_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/{pos_id}/inventory',
    response_model = POSInventoryListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List all inventory items for a POS'
)
async def get_inventory_for_pos_endpoint(
    pos_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to list all inventory items associated with a
        specific Point of Sale.
    '''
    message = f'User: {current_user}. Request to list inventory for POS ID: {pos_id}.'
    logger.info(message)
    return await get_inventory_for_pos_controller(
        pos_id = pos_id,
        db = db,
        request = request,
        current_user = current_user
    )

@router.patch(
    '/inventory/{inventory_id}',
    response_model = POSInventoryResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update a specific inventory item'
)
async def update_inventory_item_endpoint(
    inventory_id: int,
    update_data: POSInventoryUpdateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update a specific inventory item by its ID
        (e.g., update quantity, change batch).
    '''
    message = f'User: {current_user}. Request to update inventory item ID: {inventory_id}.'
    logger.info(message)
    return await update_inventory_item_controller(
        inventory_id = inventory_id,
        update_data = update_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/inventory/{inventory_id}',
    response_model = Dict[str, Any],
    status_code = status.HTTP_200_OK,
    summary = 'Delete a specific inventory item'
)
async def delete_inventory_item_endpoint(
    inventory_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a specific inventory item by its ID.
    '''
    message = f'User: {current_user}. Request to delete inventory item ID: {inventory_id}.'
    logger.info(message)
    return await delete_inventory_item_controller(
        inventory_id = inventory_id,
        db = db,
        request = request,
        current_user = current_user
    )
