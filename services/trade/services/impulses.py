'''
    Business logic services for the Trade Microservice
    Impulses
'''
from typing import Any, Dict, List, Optional, Tuple
from fastapi import UploadFile
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload
from services.products import (
    get_product_id_by_sku,
    create_bulk_items_from_skus
)
from services.common import prepare_file_to_upload
from services.crud import (
    delete_record,
    get_record,
    update_record
)
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
)
from services.logger_config import custom_logger as logger
from services.utils import (
    handle_service_errors,
    audit_event,
    sqlalchemy_object_as_dict
)
from models.impulses import (
    ImpulseInventoryEnd,
    ImpulseInventoryStart,
    ImpulseSale,
    ImpulseSaleDetail,
    TradePromotion,
    TradePromotionDetail
)
from schemas.impulses import (
    ImpulseInventoryCreateSchema,
    ImpulseSaleCreateSchema,
    TradePromotionCreateSchema,
    TradePromotionFilterSchema,
    TradePromotionUpdateSchema,
)

# --- TRADE PROMOTION (BANDEO) SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePromotion', 'CREATE')
async def create_promotion_service(
    db: Session,
    promotion_data: TradePromotionCreateSchema
) -> TradePromotion:
    '''
        Creates a new Promotion (Bandeo) and its nested SKU details.
    '''
    message = f'Attempting to create promotion: {promotion_data.name}'
    logger.info(message)

    existing_promo = db.query(TradePromotion).filter(
        TradePromotion.company_id == promotion_data.company_id,
        TradePromotion.name == promotion_data.name
    ).first()

    if existing_promo:
        error_msg = f'Promotion with name {promotion_data.name} already exists.'
        logger.error(error_msg)
        raise RegisterAlreadyExistsError(detail = error_msg)

    # 1. Create Header
    db_promotion = TradePromotion(**promotion_data.model_dump(exclude = {'details'}))
    db.add(db_promotion)
    db.flush()

    if not promotion_data.details:
        raise InvalidInputError(detail='Cannot create a promotion with an empty SKU list.')

    # 2. Create Details
    for detail_item in promotion_data.details:
        product_id = get_product_id_by_sku(
            db,
            promotion_data.company_id,
            detail_item.product_sku
        )
        db.add(TradePromotionDetail(
            promotion_id = db_promotion.id,
            product_id = product_id
        ))

    db.commit()
    db.refresh(db_promotion)
    return db_promotion

@handle_service_errors('TRADE')
async def get_promotion_by_id_service(
    db: Session,
    promotion_id: int
) -> TradePromotion:
    '''
        Retrieves a single Promotion by its ID.
    '''
    return get_record(
        db, TradePromotion, promotion_id,
        eager_load_options=[joinedload(TradePromotion.details)]
    )

@handle_service_errors('TRADE')
async def get_promotions_list_service(
    db: Session, filters: TradePromotionFilterSchema, skip: int, limit: int
) -> Tuple[List[TradePromotion], int]:
    '''
        Retrieves a paginated list of Promotions.
    '''
    query = db.query(TradePromotion).options(joinedload(TradePromotion.details))
    conditions = [TradePromotion.company_id == filters.company_id]

    if filters.name:
        conditions.append(TradePromotion.name.ilike(f'%{filters.name}%'))
    if filters.status:
        conditions.append(TradePromotion.status == filters.status)

    query = query.filter(and_(*conditions))
    return query.offset(skip).limit(limit).all(), query.count()

@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePromotion', 'UPDATE')
async def update_promotion_service(
    db: Session, promotion_id: int, update_data: TradePromotionUpdateSchema
) -> Tuple[TradePromotion, Dict[str, Any]]:
    '''
        Updates a Promotion Header.
    '''
    db_promotion = get_record(db, TradePromotion, promotion_id)
    old_values = sqlalchemy_object_as_dict(db_promotion)
    db_promotion = update_record(db, db_promotion, update_data)
    db.commit()
    db.refresh(db_promotion)
    return db_promotion, {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_promotion)
    }

@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePromotion', 'DELETE')
async def delete_promotion_service(
    db: Session, promotion_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a Promotion.
    '''
    db_promotion = get_record(db, TradePromotion, promotion_id)
    old_values = sqlalchemy_object_as_dict(db_promotion)
    delete_record(
        db = db,
        model = TradePromotion,
        record_id = promotion_id
    )
    db.commit()
    return promotion_id, {'old_values': old_values, 'new_values': None}

# --- B.1. IMPULSE ACTIVITIES SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ImpulseInventoryStart', 'CREATE')
async def create_impulse_inventory_start_service(
    db: Session,
    attendance_id: int,
    inventory_data: ImpulseInventoryCreateSchema
) -> List[ImpulseInventoryStart]:
    '''
        Creates multiple ImpulseInventoryStart records using bulk helper.
    '''
    message = f'Creating Impulse Inventory Start for attendance ID: {attendance_id}'
    logger.info(message)

    # REFACTOR: Usage of shared bulk creation logic
    return await create_bulk_items_from_skus(
        db = db,
        attendance_id = attendance_id,
        company_id = inventory_data.company_id,
        items_list = inventory_data.items,
        model_class = ImpulseInventoryStart
    )

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ImpulseSale', 'CREATE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def create_impulse_sale_service(
    db: Session,
    attendance_id: int,
    sale_data: ImpulseSaleCreateSchema,
    uploaded_file: Optional[UploadFile],
    dynamic_path: str,
    auth_token: str
) -> ImpulseSale:
    '''
        Creates a new Impulse Sale transaction (Header + Details + Photo).
    '''
    message = f'Creating Impulse Sale for attendance ID: {attendance_id}'
    logger.info(message)

    # 1. Handle File Upload
    file_path = None
    if uploaded_file:
        upload_result = await prepare_file_to_upload(
            file = uploaded_file,
            dynamic_path = dynamic_path,
            auth_token = auth_token,
            prefix = f'sale_{attendance_id}'
        )
        file_path = upload_result.get('url') if isinstance(upload_result, dict) \
            else str(upload_result)

    # 2. Create Header
    db_sale = ImpulseSale(
        attendance_id = attendance_id,
        company_id = sale_data.company_id,
        file_path = file_path
    )
    db.add(db_sale)
    db.flush()

    # 3. Create Details
    for detail in sale_data.details:
        product_id = get_product_id_by_sku(db, sale_data.company_id, detail.product_sku)

        # Check logic inside loop to prevent duplicate SKUs in same sale
        if db.query(ImpulseSaleDetail).filter(
            ImpulseSaleDetail.impulse_sale_id == db_sale.id,
            ImpulseSaleDetail.product_id == product_id
        ).first():
            raise RegisterAlreadyExistsError(
                detail=f'Duplicate SKU {detail.product_sku} in sale.'
            )

        db.add(ImpulseSaleDetail(
            impulse_sale_id = db_sale.id,
            product_id = product_id,
            quantity = detail.quantity
        ))

    db.commit()
    # Reload with details for response
    return db.query(ImpulseSale).options(joinedload(ImpulseSale.details))\
        .filter(ImpulseSale.id == db_sale.id).one()


@handle_service_errors('TRADE')
@audit_event('TRADE', 'ImpulseInventoryEnd', 'CREATE')
async def create_impulse_inventory_end_service(
    db: Session,
    attendance_id: int,
    inventory_data: ImpulseInventoryCreateSchema
) -> List[ImpulseInventoryEnd]:
    '''
        Creates multiple ImpulseInventoryEnd records using bulk helper.
    '''
    message = f'Creating Impulse Inventory End for attendance ID: {attendance_id}'
    logger.info(message)

    # REFACTOR: Usage of shared bulk creation logic
    return await create_bulk_items_from_skus(
        db = db,
        attendance_id = attendance_id,
        company_id = inventory_data.company_id,
        items_list = inventory_data.items,
        model_class = ImpulseInventoryEnd
    )
