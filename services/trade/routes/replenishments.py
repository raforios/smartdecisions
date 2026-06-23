'''
    Replenishment: routes handler
'''
from fastapi import (
    APIRouter,
    Depends,
    Request,
    status
)
from sqlalchemy.orm import Session
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.replenishments import (
    create_complementary_competition_controller,
    create_complementary_promo_point_controller,
    create_replenishment_reception_controller,
    create_replenishment_report_controller,
    get_complementary_bandeo_by_id_controller,        # iter6
    list_complementary_bandeos_for_visit_controller,  # iter6
    list_replenishment_reception_controller,   # iter5
    list_replenishment_reports_controller,     # iter5
    receive_complementary_bandeo_controller,   # iter6
    return_complementary_bandeo_controller,    # iter6
)
from schemas.replenishments import (
    ComplementaryBandeoListResponseSchema,     # iter6
    ComplementaryBandeoReceiveSchema,          # iter6
    ComplementaryBandeoResponseSchema,
    ComplementaryBandeoReturnSchema,           # iter6
    ComplementaryCompetitionCreateSchema,
    ComplementaryCompetitionResponseSchema,
    ComplementaryPromoPointCreateSchema,
    ComplementaryPromoPointResponseSchema,
    ReplenishmentReceptionCreateSchema,
    ReplenishmentReceptionListResponseSchema,
    ReplenishmentReceptionQuerySchema,         # iter5
    ReplenishmentReportCreateSchema,
    ReplenishmentReportListResponseSchema,     # iter5
    ReplenishmentReportQuerySchema,            # iter5
    ReplenishmentReportResponseSchema,
)

router = APIRouter(prefix = '/v1/replenishment', tags = ['Replenishment'])

# --- 7. REPLENISHMENT ACTIVITIES ENDPOINTS ---
# These endpoints are linked to the visit ID (attendance_id) from LOCALIZATION

@router.post(
    '/visit/{attendance_id}/report',
    response_model = ReplenishmentReportResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register Replenishment Report'
)
async def create_replenishment_report_endpoint(
    attendance_id: int,
    report_data: ReplenishmentReportCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register a Replenishment Report (Success Photos/Comments).
        Photos are uploaded via /common/photos.
    '''
    message = f'User: {current_user}. Request Replenishment Report for attendance ID: {
            attendance_id}.'
    logger.info(message)

    return await create_replenishment_report_controller(
        attendance_id = attendance_id,
        report_data = report_data,
        db = db,
        request = request,
        current_user = current_user
    )

# iter5 (Binaria, 2026-06-20): POST /v1/replenishment/visit/{attendance_id}/inventory
# was removed. The same inventory model is now shared with Impulses; register
# replenishment-time inventory via the Impulses endpoints:
#   POST /v1/impulses/visit/{attendance_id}/inventory-start
#   POST /v1/impulses/visit/{attendance_id}/inventory-end
# Their bodies now accept batch_number, expiration_date, quantity_in_room
# and quantity_in_warehouse, which were the gaps the Replenishment-specific
# endpoint was filling.

@router.post(
    '/visit/{attendance_id}/reception',
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
        Endpoint to register a product reception from a supplier.
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

# iter6 (Binaria, 2026-06-22): Bandeo en ejecucion (req 7.3.4.1) is now a
# 2-stage flow. The legacy single-shot POST .../bandeo was removed; the
# operator first confirms Recibir (status RECEIVED) and then Devolver
# (status RETURNED). Two GETs back the listing and re-entry use cases.

@router.post(
    '/complementary/visit/{attendance_id}/bandeo/receive',
    response_model = ComplementaryBandeoResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Receive a planned bandeo (Recibir step)'
)
async def receive_complementary_bandeo_endpoint(
    attendance_id: int,
    bandeo_data: ComplementaryBandeoReceiveSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Recibir step: persists qty_planned + qty_received per SKU of the
        planned bandeo and flips the header to status=RECEIVED.
    '''
    message = (
        f'User: {current_user}. Receive bandeo for attendance '
        f'{attendance_id}, promotion {bandeo_data.promotion_id}.'
    )
    logger.info(message)

    return await receive_complementary_bandeo_controller(
        attendance_id = attendance_id,
        bandeo_data = bandeo_data,
        db = db,
        request = request,
        current_user = current_user
    )


@router.patch(
    '/complementary/bandeo/{bandeo_id}/return',
    response_model = ComplementaryBandeoResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Return a received bandeo (Devolver step)'
)
async def return_complementary_bandeo_endpoint(
    bandeo_id: int,
    return_data: ComplementaryBandeoReturnSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Devolver step: registers qty_used / qty_returned / observations
        per detail row and flips the header to status=RETURNED.
    '''
    message = f'User: {current_user}. Return bandeo {bandeo_id}.'
    logger.info(message)

    return await return_complementary_bandeo_controller(
        bandeo_id = bandeo_id,
        return_data = return_data,
        db = db,
        request = request,
        current_user = current_user
    )


@router.get(
    '/complementary/visit/{attendance_id}/bandeos',
    response_model = ComplementaryBandeoListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List bandeos registered for a visit'
)
async def list_complementary_bandeos_for_visit_endpoint(
    attendance_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Returns every bandeo header of one visit so the frontend can show
        the planned bandeos + their current status.
    '''
    message = (
        f'User: {current_user}. Listing bandeos for attendance '
        f'{attendance_id}.'
    )
    logger.info(message)

    return await list_complementary_bandeos_for_visit_controller(
        attendance_id = attendance_id,
        db = db,
        request = request,
        current_user = current_user
    )


@router.get(
    '/complementary/bandeo/{bandeo_id}',
    response_model = ComplementaryBandeoResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get a single bandeo by id'
)
async def get_complementary_bandeo_by_id_endpoint(
    bandeo_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Returns one bandeo header with its details for the re-entry
        screen while the visit is still open.
    '''
    message = f'User: {current_user}. GET bandeo {bandeo_id}.'
    logger.info(message)

    return await get_complementary_bandeo_by_id_controller(
        bandeo_id = bandeo_id,
        db = db,
        request = request,
        current_user = current_user
    )

@router.post(
    '/complementary/visit/{attendance_id}/promo-point',
    response_model = ComplementaryPromoPointResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register Complementary Promotional Point'
)
async def create_complementary_promo_point_endpoint(
    attendance_id: int,
    promo_point_data: ComplementaryPromoPointCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register a Promotional Point Report.
    '''
    message = f'User: {current_user}. Request Complementary Promo Point for attendance ID: {
            attendance_id}.'
    logger.info(message)

    return await create_complementary_promo_point_controller(
        attendance_id = attendance_id,
        promo_point_data = promo_point_data,
        db = db,
        request = request,
        current_user = current_user
    )

@router.post(
    '/complementary/competition',
    response_model = ComplementaryCompetitionResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register General Competition Report'
)
async def create_complementary_competition_endpoint(
    competition_data: ComplementaryCompetitionCreateSchema,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register a general Competition Report.
    '''
    message = f'User: {current_user}. Request to create Competition Report.'
    logger.info(message)

    return await create_complementary_competition_controller(
        competition_data = competition_data,
        db = db,
        request = request,
        current_user = current_user
    )

# --- iter5 (Binaria, 2026-06-20): LIST ENDPOINTS ---

@router.get(
    '/reports',
    response_model = ReplenishmentReportListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List Replenishment Reports (paginated, filterable)'
)
async def list_replenishment_reports_endpoint(
    request: Request,
    query: ReplenishmentReportQuerySchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        iter5: paginated listing of replenishment reports with filters
        (company_id, client_company_id, attendance_id, reviewed, date range).
        Mirrors the shape of GET /v1/impulses/sales.
    '''
    message = (
        f'User: {current_user}. Listing replenishment reports with '
        f'filters {query.model_dump(exclude_none=True)}.'
    )
    logger.info(message)
    return await list_replenishment_reports_controller(
        query = query,
        db = db,
        request = request,
        current_user = current_user
    )

# iter5 (Binaria, 2026-06-20): GET /v1/replenishment/visit/{id}/inventory
# was removed. Inventory listing for either Impulses or Replenishments
# now lives at GET /v1/impulses/visit/{attendance_id}/inventory-start and
# /inventory-end, which return the unified rows including batch_number,
# expiration_date, quantity_in_room and quantity_in_warehouse.

@router.get(
    '/visit/{attendance_id}/reception',
    response_model = ReplenishmentReceptionListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List Replenishment Reception rows for a visit'
)
async def list_replenishment_reception_endpoint(
    attendance_id: int,
    request: Request,
    query: ReplenishmentReceptionQuerySchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        iter5: returns the supplier reception rows registered for one
        visit, including the newly added batch_number and expiration_date
        on each row.
    '''
    message = (
        f'User: {current_user}. Listing replenishment reception for '
        f'attendance {attendance_id}.'
    )
    logger.info(message)
    return await list_replenishment_reception_controller(
        attendance_id = attendance_id,
        query = query,
        db = db,
        request = request,
        current_user = current_user
    )
