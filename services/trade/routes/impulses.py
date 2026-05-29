'''
    Impulses: routes handler
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
from controllers.impulses import (
    create_impulse_inventory_end_controller,
    create_impulse_inventory_start_controller,
    create_impulse_sale_controller,
    create_promotion_controller,
    delete_promotion_controller,
    get_promotion_by_id_controller,
    get_promotions_list_controller,
    list_impulse_sales_controller,
    update_promotion_controller,
    get_impulse_inventory_start_by_attendance_controller,
    get_impulse_inventory_end_by_attendance_controller,
)
from schemas.impulses import (
    ImpulseInventoryCreateSchema,
    ImpulseInventoryListResponseSchema,
    ImpulseSaleCreateSchema,
    ImpulseSaleResponseSchema,
    SaleListFilterSchema,
    SaleListResponseSchema,
    TradePromotionCreateSchema,
    TradePromotionFilterSchema,
    TradePromotionListResponseSchema,
    TradePromotionResponseSchema,
    TradePromotionUpdateSchema,
    VisitInventoryResponseSchema,
)

router = APIRouter(prefix = '/v1/impulses', tags = ['Impulses'])

# --- 5. TRADE PROMOTION (BANDEO) ENDPOINTS ---

@router.post(
    '/promotions',
    response_model = TradePromotionResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create Promotion (Bandeo)'
)
async def create_promotion_endpoint(
    promotion_data: TradePromotionCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new Promotion (Bandeo) with its SKUs.
    '''
    message = f'User: {current_user}. Received request to create Promotion.'
    logger.info(message)
    return await create_promotion_controller(
        promotion_data = promotion_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/promotions/{promotion_id}',
    response_model = TradePromotionResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get Promotion by ID'
)
async def get_promotion_by_id_endpoint(
    promotion_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a single Promotion by its ID.
    '''
    message = f'User: {current_user}. Request GET Promotion ID: {promotion_id}.'
    logger.info(message)
    return await get_promotion_by_id_controller(
        promotion_id = promotion_id,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/promotions',
    response_model = TradePromotionListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List and filter Promotions'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_promotions_list_endpoint(
    request: Request,
    filters: TradePromotionFilterSchema = Depends(),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve a paginated list of Promotions.
    '''
    message = f'User: {current_user}. Request list Promotions.'
    logger.info(message)
    return await get_promotions_list_controller(
        filters = filters,
        db = db,
        skip = skip,
        limit = limit,
        request = request,
        current_user = current_user
    )

@router.put(
    '/promotions/{promotion_id}',
    response_model = TradePromotionResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update Promotion (Header only)'
)
async def update_promotion_endpoint(
    promotion_id: int,
    update_data: TradePromotionUpdateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update a Promotion Header (name, dates, status).
    '''
    message = f'User: {current_user}. Request UPDATE Promotion ID: {promotion_id}.'
    logger.info(message)
    return await update_promotion_controller(
        promotion_id = promotion_id,
        update_data = update_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/promotions/{promotion_id}',
    response_model = Dict[str, Any],
    status_code = status.HTTP_200_OK,
    summary = 'Delete Promotion'
)
async def delete_promotion_endpoint(
    promotion_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a Promotion.
    '''
    message = f'User: {current_user}. Request DELETE Promotion ID: {promotion_id}.'
    logger.info(message)
    return await delete_promotion_controller(
        promotion_id = promotion_id,
        db = db,
        request = request,
        current_user = current_user
    )

# --- 6. IMPULSE ACTIVITIES ENDPOINTS ---
# These endpoints are linked to the visit ID (attendance_id) from LOCALIZATION

@router.post(
    '/visit/{attendance_id}/inventory-start',
    response_model = ImpulseInventoryListResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register Impulse Inventory Start'
)
async def create_impulse_inventory_start_endpoint(
    attendance_id: int,
    inventory_data: ImpulseInventoryCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register the initial inventory count for an Impulse visit.
    '''
    message = f'User: {current_user}. Request Impulse Inventory Start for attendance ID: {
            attendance_id}.'
    logger.info(message)
    return await create_impulse_inventory_start_controller(
        attendance_id = attendance_id,
        inventory_data = inventory_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.get(
    '/sales',
    response_model = SaleListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List impulse sales with optional filters',
    description = (
        'Lists impulse sales across attendances. Every filter is optional: '
        'company_id, client_company_id, pos_id, user_id, date_from, date_to. '
        'Each row aggregates the total number of distinct products and the '
        'sum of detail quantities so the frontend can render the listing '
        'without extra calls.'
    ),
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def list_impulse_sales_endpoint(
    request: Request,
    filters: SaleListFilterSchema = Depends(),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user),
):
    '''
        GET endpoint for the unified sales listing demanded by Binaria
        for the 2026-06-03 go-live.
    '''
    message = f'User: {current_user}. Listing impulse sales (filters={filters}).'
    logger.info(message)
    return await list_impulse_sales_controller(
        filters = filters,
        skip = skip, limit = limit,
        db = db, request = request, current_user = current_user,
    )


@router.post(
    '/visit/{attendance_id}/sale',
    response_model = ImpulseSaleResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register Impulse Sale'
)
async def create_impulse_sale_endpoint(
    attendance_id: int,
    sale_data: ImpulseSaleCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register a Sale transaction (Impulse).
        Expects a clean JSON body with POS ID and sale details (including optional promotion_id).
    '''
    message = f'User: {current_user}. Request Impulse Sale for attendance ID: {attendance_id}.'
    logger.info(message)

    return await create_impulse_sale_controller(
        attendance_id = attendance_id,
        sale_data = sale_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.post(
    '/visit/{attendance_id}/inventory-end',
    response_model = ImpulseInventoryListResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register Impulse Inventory End'
)
async def create_impulse_inventory_end_endpoint(
    attendance_id: int,
    inventory_data: ImpulseInventoryCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register the final inventory count for an Impulse visit.
    '''
    message = f'User: {current_user}. Request Impulse Inventory End for attendance ID: {
            attendance_id}.'
    logger.info(message)
    return await create_impulse_inventory_end_controller(
        attendance_id = attendance_id,
        inventory_data = inventory_data,
        db = db,
        request = request,
        current_user = current_user
    )


# --- 5.X. GET INVENTORY SNAPSHOT FOR A VISIT (Binaria 2026-05-20) ---

@router.get(
    '/visit/{attendance_id}/inventory-start',
    response_model = VisitInventoryResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Retrieve start inventory for an Impulse visit',
    description = (
        'Returns every line of the initial inventory captured at the '
        'start of the given visit, together with summary product info '
        '(sku, name). Drives the closing-inventory screen, sales screen '
        'and final reports.'
    ),
)
async def get_impulse_inventory_start_endpoint(
    attendance_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        GET endpoint for the start inventory of an Impulse visit.
    '''
    message = (f'User: {current_user}. Retrieving start inventory for '
               f'attendance {attendance_id}.')
    logger.info(message)
    return await get_impulse_inventory_start_by_attendance_controller(
        attendance_id = attendance_id,
        db = db,
        request = request,
        current_user = current_user,
    )


@router.get(
    '/visit/{attendance_id}/inventory-end',
    response_model = VisitInventoryResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Retrieve end inventory for an Impulse visit',
    description = (
        'Returns every line of the closing inventory captured at the '
        'end of the given visit.'
    ),
)
async def get_impulse_inventory_end_endpoint(
    attendance_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        GET endpoint for the end inventory of an Impulse visit.
    '''
    message = (f'User: {current_user}. Retrieving end inventory for '
               f'attendance {attendance_id}.')
    logger.info(message)
    return await get_impulse_inventory_end_by_attendance_controller(
        attendance_id = attendance_id,
        db = db,
        request = request,
        current_user = current_user,
    )
