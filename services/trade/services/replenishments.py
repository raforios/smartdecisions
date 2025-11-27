'''
    Business logic services for the Trade Microservice
    Replenishments
'''
from typing import List, Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session
from services.products import (
    get_product_id_by_sku,
    create_bulk_items_from_skus
)
from services.common import prepare_file_to_upload
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

# --- Helper interno para archivos ---
async def _process_multiple_files(
    files: List[Optional[UploadFile]],
    dynamic_path: str,
    auth_token: str,
    prefix: str
) -> List[Optional[str]]:
    '''
        Helper to upload a list of files and return paths.
    '''
    paths = []
    for file in files:
        if file:
            res = await prepare_file_to_upload(
                file = file,
                dynamic_path = dynamic_path,
                auth_token = auth_token,
                prefix = prefix
            )
            paths.append(res.get('url') if isinstance(res, dict) else str(res))
        else:
            paths.append(None)
    return paths

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
    message = f'Creating Replenishment Report for attendance ID: {attendance_id}'
    logger.info(message)

    paths = await _process_multiple_files(files, dynamic_path, auth_token, 'replenishment')

    # Ensure list has enough elements to avoid index errors
    paths += [None] * (3 - len(paths))

    db_report = ReplenishmentReport(
        attendance_id = attendance_id,
        file_path_1 = paths[0],
        file_path_2 = paths[1],
        file_path_3 = paths[2],
        **report_data.model_dump()
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
    '''
    message = f'Creating Replenishment Inventory for attendance ID: {attendance_id}'
    logger.info(message)

    # REFACTOR: Usage of shared bulk creation logic
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

    # REFACTOR: Usage of shared bulk creation logic
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
        Creates a new Complementary Bandeo report.
    '''
    message = f'Creating Bandeo for attendance ID: {attendance_id}'
    logger.info(message)

    if db.query(ComplementaryBandeo).filter_by(attendance_id = attendance_id).first():
        raise RegisterAlreadyExistsError(
            detail = f'Bandeo exists for visit {attendance_id}'
        )

    paths = await _process_multiple_files(files, dynamic_path, auth_token, 'bandeo')
    paths += [None] * (2 - len(paths))

    db_header = ComplementaryBandeo(
        attendance_id = attendance_id,
        file_path_1 = paths[0],
        file_path_2 = paths[1],
        **bandeo_data.model_dump(exclude = {'details'})
    )
    db.add(db_header)
    db.flush()

    # Manual loop needed because Model uses bandeo_header_id, not attendance_id
    for item in bandeo_data.details:
        product_id = get_product_id_by_sku(db, bandeo_data.company_id, item.product_sku)
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
        Creates a new Complementary Promotional Point report.
    '''
    message = f'Creating Promo Point for attendance ID: {attendance_id}'
    logger.info(message)

    paths = await _process_multiple_files(files, dynamic_path, auth_token, 'promo_point')
    paths += [None] * (2 - len(paths))

    db_report = ComplementaryPromoPoint(
        attendance_id = attendance_id,
        file_path_1 = paths[0],
        file_path_2 = paths[1],
        **promo_point_data.model_dump()
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
    uploaded_file: Optional[UploadFile],
    dynamic_path: str,
    auth_token: str
) -> ComplementaryCompetition:
    '''
        Creates a new general Competition Report.
    '''
    logger.info('Creating Competition Report')

    file_path = None
    if uploaded_file:
        res = await prepare_file_to_upload(
            file = uploaded_file,
            dynamic_path = dynamic_path,
            auth_token = auth_token,
            prefix = 'competition'
        )
        file_path = res.get('url') if isinstance(res, dict) else str(res)

    db_report = ComplementaryCompetition(
        file_path_1 = file_path,
        **competition_data.model_dump()
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report
