'''
    Business logic services for the Trade Microservice
    Impulses
'''
from typing import Any, Dict, List, Optional, Tuple
from fastapi import UploadFile
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload
from services.products import (
    create_bulk_items_from_skus,
    get_product_id_by_sku,
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

    # 1. Prepare data for the Header (TradePromotion)
    header_data = promotion_data.model_dump(exclude = {'details'})

    # Check for existing name (using logic from create_product_service)
    existing_promo = db.query(TradePromotion).filter(
        TradePromotion.company_id == promotion_data.company_id,
        TradePromotion.name == promotion_data.name
    ).first()

    if existing_promo:
        error_msg = f'Promotion with name {promotion_data.name} already exists for this company.'
        logger.error(error_msg)
        raise RegisterAlreadyExistsError(detail = error_msg)

    db_promotion = TradePromotion(**header_data)
    db.add(db_promotion)
    db.flush() # Flush to get the db_promotion.id

    # 2. Iterate through details and create nested records
    if not promotion_data.details:
        error_msg = 'Cannot create a promotion with an empty SKU list (details).'
        logger.error(error_msg)
        raise InvalidInputError(detail = error_msg)

    for detail_item in promotion_data.details:
        # 2a. Translate SKU to product_id (reusing helper)
        product_id = get_product_id_by_sku(
            db, promotion_data.company_id, detail_item.product_sku
        )

        # 2b. Create the detail record
        db_detail = TradePromotionDetail(
            promotion_id = db_promotion.id,
            product_id = product_id
        )
        db.add(db_detail)

    # 3. Commit and refresh
    db.commit()
    db.refresh(db_promotion)
    return db_promotion

@handle_service_errors('TRADE')
async def get_promotion_by_id_service(
    db: Session,
    promotion_id: int
) -> TradePromotion:
    '''
        Retrieves a single Promotion by its ID, including nested SKU details.
    '''
    message = f'Retrieving Promotion ID: {promotion_id}'
    logger.info(message)

    # Use eager_load_options to load the 'details' relationship
    eager_load_options = [joinedload(TradePromotion.details)]

    db_promotion = get_record(
        db,
        TradePromotion,
        promotion_id,
        eager_load_options = eager_load_options
    )
    return db_promotion

@handle_service_errors('TRADE')
async def get_promotions_list_service(
    db: Session, filters: TradePromotionFilterSchema, skip: int, limit: int
) -> Tuple[List[TradePromotion], int]:
    '''
        Retrieves a paginated and filtered list of Promotions.
    '''
    message = f'Attempting to retrieve Promotion list for company {filters.company_id}'
    logger.info(message)

    # Eager load details for the list view
    query = db.query(TradePromotion).options(joinedload(TradePromotion.details))

    # Mandatory filter
    conditions = [TradePromotion.company_id == filters.company_id]

    # Optional filters
    if filters.name:
        conditions.append(TradePromotion.name.ilike(f'%{filters.name}%'))
    if filters.status:
        conditions.append(TradePromotion.status == filters.status)

    query = query.filter(and_(*conditions))

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return items, total

@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePromotion', 'UPDATE')
async def update_promotion_service(
    db: Session,
    promotion_id: int,
    update_data: TradePromotionUpdateSchema
) -> Tuple[TradePromotion, Dict[str, Any]]:
    '''
        Updates a Promotion Header (e.g., dates, status).
        Does NOT update the nested SKU details.
    '''
    message = f'Attempting to update Promotion ID: {promotion_id}'
    logger.info(message)

    db_promotion = get_record(db, TradePromotion, promotion_id)
    old_values = sqlalchemy_object_as_dict(db_promotion)

    # Use the generic crud.update_record function
    db_promotion = update_record(db, db_promotion, update_data)

    db.commit()
    db.refresh(db_promotion)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_promotion)
    }

    return db_promotion, auditable_data

@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePromotion', 'DELETE')
async def delete_promotion_service(
    db: Session,
    promotion_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a Promotion and its cascaded SKU details.
    '''
    message = f'Attempting to delete Promotion ID: {promotion_id}'
    logger.info(message)

    db_promotion = get_record(db, TradePromotion, promotion_id)
    old_values = sqlalchemy_object_as_dict(db_promotion)

    delete_record(
        db = db,
        model = TradePromotion,
        record_id = promotion_id)
    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return promotion_id, auditable_data

# --- B.1. IMPULSE ACTIVITIES SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ImpulseInventoryStart', 'CREATE')
async def create_impulse_inventory_start_service(
    db: Session,
    attendance_id: int,
    inventory_data: ImpulseInventoryCreateSchema
) -> List[ImpulseInventoryStart]:
    '''
        Creates multiple ImpulseInventoryStart records for a specific visit.
    '''
    message = f'Creating Impulse Inventory Start for attendance ID: {attendance_id
            } for the company ID: {inventory_data.company_id}'
    logger.info(message)

    created_items = await create_bulk_items_from_skus(
        db = db,
        attendance_id = attendance_id,
        company_id = inventory_data.company_id,
        items_list = inventory_data.items,
        model_class = ImpulseInventoryStart
    )

    return created_items

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

    # 1. Handle file upload
    file_path = None
    if uploaded_file:
        upload_result = await prepare_file_to_upload(
            file = uploaded_file,
            dynamic_path = dynamic_path,
            auth_token = auth_token,
            prefix = f'sale_{attendance_id}'
        )

        # FIX: Extraemos la URL del diccionario.
        if isinstance(upload_result, dict):
            file_path = upload_result.get('url')
        else:
            file_path = str(upload_result)

    # 2. Create the Header (ImpulseSale)
    db_sale_header = ImpulseSale(
        attendance_id = attendance_id,
        company_id = sale_data.company_id,
        file_path = file_path
    )
    db.add(db_sale_header)
    db.flush()

    # 3. Iterate through details and create child records
    for detail_item in sale_data.details:

        product_id = get_product_id_by_sku(
            db, sale_data.company_id, detail_item.product_sku
        )

        db_detail = ImpulseSaleDetail(
            impulse_sale_id = db_sale_header.id,
            product_id = product_id,
            quantity = detail_item.quantity
        )
        db.add(db_detail)

    # 4. Commit and refresh
    db.commit()

    db_sale_header = db.query(ImpulseSale).options(
        joinedload(ImpulseSale.details)
    ).filter(ImpulseSale.id == db_sale_header.id).one()

    return db_sale_header

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ImpulseInventoryEnd', 'CREATE')
async def create_impulse_inventory_end_service(
    db: Session,
    attendance_id: int,
    inventory_data: ImpulseInventoryCreateSchema
) -> List[ImpulseInventoryEnd]:
    '''
        Creates multiple ImpulseInventoryEnd records for a specific visit.
    '''
    message = f'Attempting to create Impulse Inventory End for attendance ID: {attendance_id
            } and company {inventory_data.company_id}'
    logger.info(message)

    created_items = await create_bulk_items_from_skus(
        db = db,
        attendance_id = attendance_id,
        company_id = inventory_data.company_id,
        items_list = inventory_data.items,
        model_class = ImpulseInventoryEnd
    )

    return created_items
