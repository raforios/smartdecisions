'''
    Impulses Controllers
'''
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from fastapi import Request, UploadFile
from services.utils import handle_service_errors
from services.impulses import (
    create_impulse_inventory_end_service,
    create_impulse_inventory_start_service,
    create_impulse_sale_service,
    create_promotion_service,
    delete_promotion_service,
    get_promotion_by_id_service,
    get_promotions_list_service,
    update_promotion_service,
)
from schemas.impulses import (
    ImpulseInventoryCreateSchema,
    ImpulseInventoryListResponseSchema,
    ImpulseSaleCreateSchema,
    ImpulseSaleResponseSchema,
    TradePromotionCreateSchema,
    TradePromotionFilterSchema,
    TradePromotionListResponseSchema,
    TradePromotionResponseSchema,
    TradePromotionUpdateSchema
)

# --- TRADE PROMOTION (BANDEO) Controllers ---

@handle_service_errors('TRADE')
async def create_promotion_controller(
    promotion_data: TradePromotionCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TradePromotionResponseSchema:
    '''
        Controller for creating a new Promotion (Bandeo).
    '''
    db_promotion = await create_promotion_service(
        db = db,
        promotion_data = promotion_data
    )
    return TradePromotionResponseSchema.model_validate(
        db_promotion, from_attributes = True
    )

@handle_service_errors('TRADE')
async def get_promotion_by_id_controller(
    promotion_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TradePromotionResponseSchema:
    '''
        Controller for retrieving a single Promotion by ID.
    '''
    db_promotion = await get_promotion_by_id_service(
        db = db,
        promotion_id = promotion_id
    )
    return TradePromotionResponseSchema.model_validate(
        db_promotion, from_attributes = True
    )

@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_promotions_list_controller(
    filters: TradePromotionFilterSchema,
    db: Session,
    skip: int,
    limit: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TradePromotionListResponseSchema:
    '''
        Controller for retrieving a paginated list of Promotions.
    '''
    items, total = await get_promotions_list_service(
        db = db, filters = filters, skip = skip, limit = limit
    )
    return TradePromotionListResponseSchema(items = items, total = total)

@handle_service_errors('TRADE')
async def update_promotion_controller(
    promotion_id: int,
    update_data: TradePromotionUpdateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TradePromotionResponseSchema:
    '''
        Controller for updating a Promotion Header.
    '''
    db_promotion = await update_promotion_service(
        db = db,
        promotion_id = promotion_id,
        update_data = update_data
    )
    return TradePromotionResponseSchema.model_validate(
        db_promotion, from_attributes = True
    )

@handle_service_errors('TRADE')
async def delete_promotion_controller(
    promotion_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller for deleting a Promotion.
    '''
    deleted_id = await delete_promotion_service(
        db = db,
        promotion_id = promotion_id
    )
    return {
        'message': f'Promotion with ID {deleted_id} deleted successfully.',
        'id': deleted_id
    }

# --- B.1. IMPULSE ACTIVITIES Controllers ---

@handle_service_errors('TRADE')
async def create_impulse_inventory_start_controller(
    attendance_id: int,
    inventory_data: ImpulseInventoryCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ImpulseInventoryListResponseSchema:
    '''
        Controller for creating an Impulse Inventory Start report.
    '''
    created_items = await create_impulse_inventory_start_service(
        db = db,
        attendance_id = attendance_id,
        inventory_data = inventory_data
    )

    return ImpulseInventoryListResponseSchema(
        items = created_items,
        total = len(created_items)
    )

@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def create_impulse_sale_controller(
    attendance_id: int,
    sale_data: ImpulseSaleCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    auth_token: str,
    uploaded_file: Optional[UploadFile] = None
) -> ImpulseSaleResponseSchema:
    '''
        Controller for creating a new Impulse Sale transaction.
    '''
    dynamic_path = f'trade/{sale_data.company_id}/impulses'

    db_sale = await create_impulse_sale_service(
        db = db,
        attendance_id = attendance_id,
        sale_data = sale_data,
        uploaded_file = uploaded_file,
        dynamic_path = dynamic_path,
        auth_token = auth_token
    )
    return ImpulseSaleResponseSchema.model_validate(
        db_sale, from_attributes = True
    )

@handle_service_errors('TRADE')
async def create_impulse_inventory_end_controller(
    attendance_id: int,
    inventory_data: ImpulseInventoryCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ImpulseInventoryListResponseSchema:
    '''
        Controller for creating an Impulse Inventory End report.
    '''
    created_items = await create_impulse_inventory_end_service(
        db = db,
        attendance_id = attendance_id,
        inventory_data = inventory_data
    )

    return ImpulseInventoryListResponseSchema(
        items = created_items,
        total = len(created_items)
    )
