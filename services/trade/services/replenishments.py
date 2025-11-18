'''
    Business logic services for the Trade Microservice
    Replenishments
'''
from typing import List, Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session, joinedload
from services.products import (
    create_bulk_items_from_skus,
    get_product_id_by_sku,
)
from services.common import prepare_file_to_upload
from services.logger_config import custom_logger as logger
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

    # 1. Handle file uploads
    file_paths = []
    for file in files:
        if file:
            path = await prepare_file_to_upload(
                file = file,
                dynamic_path = dynamic_path,
                auth_token = auth_token,
                prefix = report_data.company_id
            )

            file_paths.append(path)
        else:
            file_paths.append(None)

    # 2. Create the record
    report_dict = report_data.model_dump(exclude={'company_id'})
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

    created_items = await create_bulk_items_from_skus(
        db = db,
        attendance_id = attendance_id,
        company_id = inventory_data_rep.company_id,
        items_list = inventory_data_rep.items,
        model_class = ReplenishmentInventory
    )

    return created_items

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ReplenishmentReception', 'CREATE')
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

    created_items = await create_bulk_items_from_skus(
        db = db,
        attendance_id = attendance_id,
        company_id = reception_data.company_id,
        items_list = reception_data.items,
        model_class = ReplenishmentReception
    )

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

# 1. Handle file uploads
    file_paths = []
    for file in files:
        if file:
            path = await prepare_file_to_upload(
                file = file,
                dynamic_path = dynamic_path,
                auth_token = auth_token,
                prefix = bandeo_data.company_id
            )

            file_paths.append(path)
        else:
            file_paths.append(None)

    # 2. Create the Bandeo Header
    header_data = bandeo_data.model_dump(exclude = {'details', 'company_id'})
    db_bandeo_header = ComplementaryBandeo(
        attendance_id = attendance_id,
        file_path_1 = file_paths[0] if len(file_paths) > 0 else None,
        file_path_2 = file_paths[1] if len(file_paths) > 1 else None,
        **header_data
    )
    db.add(db_bandeo_header)
    db.flush()

    # 3. Iterate through details (Lógica sin cambios)
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

    # 4. Commit and refresh
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

    # 1. Handle file uploads
    file_paths = []
    for file in files:
        if file:
            path = await prepare_file_to_upload(
                file = file,
                dynamic_path = dynamic_path,
                auth_token = auth_token,
                prefix = promo_point_data.company_id
            )

            file_paths.append(path)
        else:
            file_paths.append(None)

    # 2. Create the record
    report_dict = promo_point_data.model_dump(exclude={'company_id'})
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
async def create_complementary_competition_service(
    db: Session,
    competition_data: ComplementaryCompetitionCreateSchema,
    file: Optional[UploadFile],
    dynamic_path: str,
    auth_token: str
) -> ComplementaryCompetition:
    '''
        Creates a new general Competition Report.
    '''
    message = 'Creating Competition Report'
    logger.info(message)

    # 1. Handle file upload
    file_path_1 = None
    if file:

        file_path_1 = await prepare_file_to_upload(
            file = file,
            dynamic_path = dynamic_path,
            auth_token = auth_token,
            prefix = competition_data.company_id
        )

    # 2. Prepare data
    report_dict = competition_data.model_dump()

    # 3. Create the record
    db_report = ComplementaryCompetition(
        file_path_1 = file_path_1, # Guardamos el path
        **report_dict
    )

    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report
