'''
    Business logic services for the Trade Microservice
    Replenishments
'''
from typing import List, Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session, joinedload
from services.products import (
    get_product_id_by_sku,
)
from services.common import prepare_file_to_upload
from services.logger_config import custom_logger as logger
from services.exceptions import (
    RegisterAlreadyExistsError
)
from services.utils import (
    handle_service_errors,
    audit_event,
)
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
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def create_replenishment_report_service(
    db: Session,
    attendance_id: int,
    report_data: ReplenishmentReportCreateSchema,
    files: List[Optional[UploadFile]],
    dynamic_path: str,
    auth_token: str
) -> ReplenishmentReport:
    '''
        Creates a new Replenishment Report (Success Photos).
    '''
    message = f'Attempting to create Replenishment Report for attendance ID: {attendance_id}'
    logger.info(message)

    file_paths = []
    for file in files:
        if file:
            path = await prepare_file_to_upload(
                file = file,
                dynamic_path = dynamic_path,
                auth_token = auth_token,
                prefix = 'replenishment'
            )
            if isinstance(path, dict):
                file_paths.append(path.get('url'))
            else:
                file_paths.append(str(path))
        else:
            file_paths.append(None)

    report_dict = report_data.model_dump()
    db_report = ReplenishmentReport(
        attendance_id = attendance_id,
        file_path_1 = file_paths[0] if len(file_paths) > 0 else None,
        file_path_2 = file_paths[1] if len(file_paths) > 1 else None,
        file_path_3 = file_paths[2] if len(file_paths) > 2 else None,
        **report_dict
    )

    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ReplenishmentInventory', 'CREATE')
# pylint: disable=duplicate-code
async def create_replenishment_inventory_service(
    db: Session,
    attendance_id: int,
    inventory_data_rep: ReplenishmentInventoryCreateSchema
) -> List[ReplenishmentInventory]:
    '''
        Creates multiple ReplenishmentInventory (detailed) records for a visit.
    '''
    message = f'Creating Replenishment Inventory (Detailed) for attendance ID: {attendance_id
            } for company ID: {inventory_data_rep.company_id}'
    logger.info(message)

    created_items = []

    for item in inventory_data_rep.items:

        product_id = get_product_id_by_sku(
            db, inventory_data_rep.company_id, item.product_sku
        )

        existing_item = db.query(ReplenishmentInventory).filter(
            ReplenishmentInventory.attendance_id == attendance_id,
            ReplenishmentInventory.product_id == product_id
        ).first()

        if existing_item:
            error_msg = (f'Inventory record for SKU {item.product_sku} already '
                         f'exists for visit {attendance_id}.')
            logger.error(error_msg)
            raise RegisterAlreadyExistsError(detail=error_msg)

        db_item = ReplenishmentInventory(
            attendance_id = attendance_id,
            product_id = product_id,
            quantity_registered = item.quantity_registered,
        )

        db.add(db_item)
        created_items.append(db_item)

    db.commit()

    for item in created_items:
        db.refresh(item)

    return created_items

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ReplenishmentReception', 'CREATE')
# pylint: disable=duplicate-code
async def create_replenishment_reception_service(
    db: Session,
    attendance_id: int,
    reception_data: ReplenishmentReceptionCreateSchema
) -> List[ReplenishmentReception]:
    '''
        Creates multiple ReplenishmentReception (Supplier) records for a visit.
    '''
    message = f'Creating Replenishment Reception for attendance ID: {attendance_id}'
    logger.info(message)

    created_items = []

    for item in reception_data.items:
        product_id = get_product_id_by_sku(
            db, reception_data.company_id, item.product_sku
        )

        existing = db.query(ReplenishmentReception).filter(
            ReplenishmentReception.attendance_id == attendance_id,
            ReplenishmentReception.product_id == product_id
        ).first()

        if existing:
            error_msg = f'Reception for SKU {item.product_sku} already exists.'
            logger.error(error_msg)
            raise RegisterAlreadyExistsError(detail=error_msg)

        db_item = ReplenishmentReception(
            attendance_id = attendance_id,
            product_id = product_id,
            quantity = item.quantity
        )
        db.add(db_item)
        created_items.append(db_item)

    db.commit()
    for item in created_items:
        db.refresh(item)

    return created_items

# --- B.3. COMPLEMENTARY ACTIVITIES SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryBandeo', 'CREATE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def create_complementary_bandeo_service(
    db: Session,
    attendance_id: int,
    bandeo_data: ComplementaryBandeoCreateSchema,
    files: List[Optional[UploadFile]],
    dynamic_path: str,
    auth_token: str
) -> ComplementaryBandeo:
    '''
        Creates a new Complementary Bandeo report (Header and Details).
    '''
    message = f'Attempting to create Complementary Bandeo for attendance ID: {attendance_id}'
    logger.info(message)

    existing_bandeo = db.query(ComplementaryBandeo).filter(
        ComplementaryBandeo.attendance_id == attendance_id
    ).first()

    if existing_bandeo:
        error_msg = f'Bandeo report already exists for attendance ID: {attendance_id}'
        logger.error(error_msg)
        raise RegisterAlreadyExistsError(detail = error_msg)

    file_paths = []
    for file in files:
        if file:
            path = await prepare_file_to_upload(
                file = file,
                dynamic_path = dynamic_path,
                auth_token = auth_token,
                prefix = 'bandeo'
            )
            if isinstance(path, dict):
                file_paths.append(path.get('url'))
            else:
                file_paths.append(str(path))
        else:
            file_paths.append(None)

    header_data = bandeo_data.model_dump(exclude = {'details'})
    db_bandeo_header = ComplementaryBandeo(
        attendance_id = attendance_id,
        file_path_1 = file_paths[0] if len(file_paths) > 0 else None,
        file_path_2 = file_paths[1] if len(file_paths) > 1 else None,
        **header_data
    )
    db.add(db_bandeo_header)
    db.flush()

    for detail_item in bandeo_data.details:
        product_id = get_product_id_by_sku(
            db, bandeo_data.company_id, detail_item.product_sku
        )
        db_detail = ComplementaryBandeoDetail(
            bandeo_header_id = db_bandeo_header.id,
            product_id = product_id,
            quantity_returned = detail_item.quantity_returned
        )
        db.add(db_detail)

    db.commit()
    db_bandeo_header = db.query(ComplementaryBandeo).options(
        joinedload(ComplementaryBandeo.details)
    ).filter(ComplementaryBandeo.id == db_bandeo_header.id).one()

    return db_bandeo_header

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryPromoPoint', 'CREATE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def create_complementary_promo_point_service(
    db: Session,
    attendance_id: int,
    promo_point_data: ComplementaryPromoPointCreateSchema,
    files: List[Optional[UploadFile]],
    dynamic_path: str,
    auth_token: str
) -> ComplementaryPromoPoint:
    '''
        Creates a new Complementary Promotional Point report (Photos).
    '''
    message = f'Creating Complementary Promo Point for attendance ID: {attendance_id}'
    logger.info(message)

    file_paths = []
    for file in files:
        if file:
            path = await prepare_file_to_upload(
                file = file,
                dynamic_path = dynamic_path,
                auth_token = auth_token,
                prefix = 'promo_point'
            )
            if isinstance(path, dict):
                file_paths.append(path.get('url'))
            else:
                file_paths.append(str(path))
        else:
            file_paths.append(None)

    report_dict = promo_point_data.model_dump()
    db_report = ComplementaryPromoPoint(
        attendance_id = attendance_id,
        file_path_1 = file_paths[0] if len(file_paths) > 0 else None,
        file_path_2 = file_paths[1] if len(file_paths) > 1 else None,
        **report_dict
    )

    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryCompetition', 'CREATE')
# pylint: disable=duplicate-code
async def create_complementary_competition_service(
    db: Session,
    competition_data: ComplementaryCompetitionCreateSchema,
    uploaded_file: Optional[UploadFile],
    dynamic_path: str,
    auth_token: str
) -> ComplementaryCompetition:
    '''
        Creates a new general Competition Report.
    '''
    message = 'Creating Competition Report'
    logger.info(message)

    file_path = None
    if uploaded_file:
        upload_result = await prepare_file_to_upload(
            file = uploaded_file,
            dynamic_path = dynamic_path,
            auth_token = auth_token,
            prefix = 'competition'
        )
        if isinstance(upload_result, dict):
            file_path = upload_result.get('url')
        else:
            file_path = str(upload_result)

    report_dict = competition_data.model_dump()

    db_report = ComplementaryCompetition(
        file_path_1 = file_path,
        **report_dict
    )

    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report
