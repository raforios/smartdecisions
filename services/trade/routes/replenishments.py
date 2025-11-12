'''
    Replenishment: routes handler
'''
from typing import Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    Request,
    UploadFile,
    status
)
from pydantic import ValidationError
from sqlalchemy.orm import Session
from services.exceptions import InvalidInputError
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.replenishments import (
    create_complementary_bandeo_controller,
    create_complementary_competition_controller,
    create_complementary_promo_point_controller,
    create_replenishment_inventory_controller,
    create_replenishment_reception_controller,
    create_replenishment_report_controller,
)
from schemas.replenishments import (
    ComplementaryBandeoCreateSchema,
    ComplementaryBandeoResponseSchema,
    ComplementaryCompetitionCreateSchema,
    ComplementaryCompetitionResponseSchema,
    ComplementaryPromoPointCreateSchema,
    ComplementaryPromoPointResponseSchema,
    ReplenishmentInventoryCreateSchema,
    ReplenishmentInventoryListResponseSchema,
    ReplenishmentReceptionCreateSchema,
    ReplenishmentReceptionListResponseSchema,
    ReplenishmentReportCreateSchema,
    ReplenishmentReportResponseSchema,
)

router = APIRouter(prefix = '/v1/replenishment', tags = ['Replenishment'])

# --- 7. REPLENISHMENT ACTIVITIES ENDPOINTS ---
# These endpoints are linked to the visit ID (attendance_id) from LOCALIZATION

@router.post(
    '/replenishment/visit/{attendance_id}/report',
    response_model = ReplenishmentReportResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register Replenishment Report'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def create_replenishment_report_endpoint(
    attendance_id: int,
    report_data: ReplenishmentReportCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user),
    auth_token: str = Header(..., alias = 'Authorization'),
    data: str = Form(
        ...,
        description = 'JSON string of the report data (ReplenishmentReportCreateSchema).'
    ),
    file_1: Optional[UploadFile] = File(None, description = 'First success photo.'),
    file_2: Optional[UploadFile] = File(None, description = 'Second success photo.'),
    file_3: Optional[UploadFile] = File(None, description = 'Third success photo.')
):
    '''
        Endpoint to register a Replenishment Report (Success Photos/Comments).
    '''
    message = f'User: {current_user}. Request Replenishment Report for attendance ID: {
            attendance_id}.'
    logger.info(message)

    try:
        report_data = ReplenishmentReportCreateSchema.model_validate_json(data)
    except ValidationError as e:
        raise InvalidInputError(
            detail = f'Invalid JSON data format in data field: {e}'
        ) from e

    return await create_replenishment_report_controller(
        attendance_id = attendance_id,
        report_data = report_data,
        files = [file_1, file_2, file_3],
        db = db,
        request = request,
        current_user = current_user,
        auth_token = auth_token
    )

@router.post(
    '/replenishment/visit/{attendance_id}/inventory',
    response_model = ReplenishmentInventoryListResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register Replenishment Inventory'
)
async def create_replenishment_inventory_endpoint(
    attendance_id: int,
    inventory_data_rep: ReplenishmentInventoryCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register the detailed inventory (SKU, Batch, Expiration).
    '''
    message = f'User: {current_user}. Request Replenishment Inventory for attendance ID: {
            attendance_id}.'
    logger.info(message)
    return await create_replenishment_inventory_controller(
        attendance_id = attendance_id,
        inventory_data_rep = inventory_data_rep,
        db = db,
        request = request,
        current_user = current_user
    )

@router.post(
    '/replenishment/visit/{attendance_id}/reception',
    response_model = ReplenishmentReceptionListResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register Supplier Reception'
)
async def create_replenishment_reception_endpoint(
    attendance_id: int,
    reception_data: ReplenishmentReceptionCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register a product reception from a supplier at the POS.
    '''
    message = f'User: {current_user}. Request Replenishment Reception for attendance ID: {
            attendance_id}.'
    logger.info(message)
    return await create_replenishment_reception_controller(
        attendance_id = attendance_id,
        reception_data = reception_data,
        db = db,
        request = request,
        current_user = current_user
    )

# --- 8. COMPLEMENTARY ACTIVITIES ENDPOINTS ---

@router.post(
    '/complementary/visit/{attendance_id}/bandeo',
    response_model = ComplementaryBandeoResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register Complementary Bandeo Report'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def create_complementary_bandeo_endpoint(
    attendance_id: int,
    bandeo_data: ComplementaryBandeoCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user),
    auth_token: str = Header(..., alias = 'Authorization'),
    data: str = Form(
        ...,
        description = 'JSON string of the bandeo data (ComplementaryBandeoCreateSchema).'
    ),
    file_1: Optional[UploadFile] = File(None, description = 'First bandeo photo.'),
    file_2: Optional[UploadFile] = File(None, description = 'Second bandeo photo.')
):
    '''
        Endpoint to register a Bandeo Report (Returns and Photos) for a visit.
    '''
    message = f'User: {current_user}. Request Complementary Bandeo for attendance ID: {
            attendance_id}.'
    logger.info(message)

    try:
        bandeo_data = ComplementaryBandeoCreateSchema.model_validate_json(data)
    except ValidationError as e:
        raise InvalidInputError(
            detail = f'Invalid JSON data format in data field: {e}'
        ) from e

    return await create_complementary_bandeo_controller(
        attendance_id = attendance_id,
        bandeo_data = bandeo_data,
        files = [file_1, file_2],
        db = db,
        request = request,
        current_user = current_user,
        auth_token = auth_token
    )

@router.post(
    '/complementary/visit/{attendance_id}/promo-point',
    response_model = ComplementaryPromoPointResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register Complementary Promotional Point'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def create_complementary_promo_point_endpoint(
    attendance_id: int,
    promo_point_data: ComplementaryPromoPointCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user),
    auth_token: str = Header(..., alias = 'Authorization'),
    data: str = Form(
        ...,
        description = 'JSON string of the promo point data (ComplementaryPromoPointCreateSchema).'
    ),
    file_1: Optional[UploadFile] = File(None, description = 'First promo point photo.'),
    file_2: Optional[UploadFile] = File(None, description = 'Second promo point photo.')
):
    '''
        Endpoint to register a Promotional Point Report (Photos) for a visit.
    '''
    message = f'User: {current_user}. Request Complementary Promo Point for attendance ID: {
            attendance_id}.'
    logger.info(message)

    try:
        promo_point_data = ComplementaryPromoPointCreateSchema.model_validate_json(data)
    except ValidationError as e:
        raise InvalidInputError(
            detail = f'Invalid JSON data format in data field: {e}'
        ) from e

    return await create_complementary_promo_point_controller(
        attendance_id = attendance_id,
        promo_point_data = promo_point_data,
        files = [file_1, file_2],
        db = db,
        request = request,
        current_user = current_user,
        auth_token = auth_token
    )

@router.post(
    '/complementary/competition',
    response_model = ComplementaryCompetitionResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register General Competition Report'
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def create_complementary_competition_endpoint(
    competition_data: ComplementaryCompetitionCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user),
    auth_token: str = Header(..., alias = 'Authorization'),
    data: str = Form(
        ...,
        description = 'JSON string of the competition data (ComplementaryCompetitionCreateSchema).'
    ),
    file: Optional[UploadFile] = File(None, description = 'Optional competitor photo.')
):
    '''
        Endpoint to register a general Competition Report (not tied to a visit).
    '''
    message = f'User: {current_user}. Request to create Competition Report.'
    logger.info(message)

    try:
        competition_data = ComplementaryCompetitionCreateSchema.model_validate_json(data)
    except ValidationError as e:
        raise InvalidInputError(
            detail = f'Invalid JSON data format in data field: {e}'
        ) from e

    return await create_complementary_competition_controller(
        competition_data = competition_data,
        file = file,
        db = db,
        request = request,
        current_user = current_user,
        auth_token = auth_token
    )
