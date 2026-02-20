'''
    Business logic services for the Trade Microservice
    Replenishments
'''
from typing import List
from sqlalchemy.orm import Session
from services.products import (
    get_product_id_by_sku,
    create_bulk_items_from_skus,
    validate_product_assigned_to_pos
)
from services.logger_config import custom_logger as logger
from services.exceptions import RegisterAlreadyExistsError
from services.utils import handle_service_errors, audit_event

from models.replenishments import (
    ComplementaryBandeo,
    ComplementaryBandeoDetail,
    ComplementaryCompetition,
    ComplementaryPromoPoint,
    ReplenishmentInventory,
    ReplenishmentReception,
    ReplenishmentReport,
)
from schemas.replenishments import (
    ReplenishmentInventoryCreateSchema,
    ReplenishmentReceptionCreateSchema,
    ReplenishmentReportCreateSchema,
    ComplementaryBandeoCreateSchema,
    ComplementaryCompetitionCreateSchema,
    ComplementaryPromoPointCreateSchema
)

# --- B.2. REPLENISHMENT ACTIVITIES SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ReplenishmentReport', 'CREATE')
async def create_replenishment_report_service(
    db: Session,
    attendance_id: int,
    report_data: ReplenishmentReportCreateSchema
) -> ReplenishmentReport:
    '''
        Creates a new Replenishment Report metadata.
    '''
    message = f'Creating Replenishment Report meta for attendance ID: {attendance_id}'
    logger.info(message)

    db_report = ReplenishmentReport(
        attendance_id = attendance_id,
        company_id = report_data.company_id,
        comments = report_data.comments
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)

    return db_report

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ReplenishmentInventory', 'CREATE')
async def create_replenishment_inventory_service(
    db: Session,
    attendance_id: int,
    inventory_data_rep: ReplenishmentInventoryCreateSchema
) -> List[ReplenishmentInventory]:
    '''
        Creates multiple ReplenishmentInventory records.
        OPTIMIZATION: Uses 'pos_id' provided by Frontend to validate assortment.
    '''
    message = f'Creating Replenishment Inventory for attendance ID: {attendance_id}'
    logger.info(message)

    # Validar Surtido usando el ID que nos manda el frontend
    pos_id = inventory_data_rep.pos_id

    for item in inventory_data_rep.items:
        product_id = get_product_id_by_sku(
            db, inventory_data_rep.company_id, item.product_sku
        )

        # Validación de Negocio (Punto 9)
        validate_product_assigned_to_pos(
            db = db,
            company_id = inventory_data_rep.company_id,
            pos_id = pos_id,
            product_id = product_id
        )

    # Insertar
    return await create_bulk_items_from_skus(
        db = db,
        attendance_id = attendance_id,
        company_id = inventory_data_rep.company_id,
        items_list = inventory_data_rep.items,
        model_class = ReplenishmentInventory
    )

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ReplenishmentReception', 'CREATE')
async def create_replenishment_reception_service(
    db: Session,
    attendance_id: int,
    reception_data: ReplenishmentReceptionCreateSchema
) -> List[ReplenishmentReception]:
    '''
        Creates multiple ReplenishmentReception records.
    '''
    message = f'Creating Replenishment Reception for attendance ID: {attendance_id}'
    logger.info(message)

    # Validar Surtido
    pos_id = reception_data.pos_id

    for item in reception_data.items:
        product_id = get_product_id_by_sku(
            db, reception_data.company_id, item.product_sku
        )
        validate_product_assigned_to_pos(
            db, reception_data.company_id, pos_id, product_id
        )

    return await create_bulk_items_from_skus(
        db = db,
        attendance_id = attendance_id,
        company_id = reception_data.company_id,
        items_list = reception_data.items,
        model_class = ReplenishmentReception
    )

# --- B.3. COMPLEMENTARY ACTIVITIES SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryBandeo', 'CREATE')
async def create_complementary_bandeo_service(
    db: Session,
    attendance_id: int,
    bandeo_data: ComplementaryBandeoCreateSchema
) -> ComplementaryBandeo:
    '''
        Creates a new Complementary Bandeo report metadata.
    '''
    message = f'Creating Bandeo for attendance ID: {attendance_id}'
    logger.info(message)

    if db.query(ComplementaryBandeo).filter_by(attendance_id = attendance_id).first():
        raise RegisterAlreadyExistsError(
            detail = f'Bandeo exists for visit {attendance_id}'
        )

    # 1. Create Header
    db_header = ComplementaryBandeo(
        attendance_id = attendance_id,
        company_id = bandeo_data.company_id,
        comments = bandeo_data.comments
    )
    db.add(db_header)
    db.flush()

    # 2. Save Details & Validate (Punto 8)
    pos_id = bandeo_data.pos_id

    for item in bandeo_data.details:
        product_id = get_product_id_by_sku(db, bandeo_data.company_id, item.product_sku)

        validate_product_assigned_to_pos(
            db, bandeo_data.company_id, pos_id, product_id
        )

        db.add(ComplementaryBandeoDetail(
            bandeo_header_id = db_header.id,
            product_id = product_id,
            quantity_returned = item.quantity_returned
        ))

    db.commit()
    db.refresh(db_header)
    return db_header

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryPromoPoint', 'CREATE')
async def create_complementary_promo_point_service(
    db: Session,
    attendance_id: int,
    promo_point_data: ComplementaryPromoPointCreateSchema
) -> ComplementaryPromoPoint:
    '''
        Creates a new Complementary Promotional Point report metadata.
    '''
    message = f'Creating Promo Point for attendance ID: {attendance_id}'
    logger.info(message)

    db_report = ComplementaryPromoPoint(
        attendance_id = attendance_id,
        company_id = promo_point_data.company_id,
        comments = promo_point_data.comments
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryCompetition', 'CREATE')
async def create_complementary_competition_service(
    db: Session,
    competition_data: ComplementaryCompetitionCreateSchema
) -> ComplementaryCompetition:
    '''
        Creates a new general Competition Report metadata.
    '''
    logger.info('Creating Competition Report')

    db_report = ComplementaryCompetition(
        **competition_data.model_dump()
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report
