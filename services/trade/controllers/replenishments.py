'''
    Replenishments Controllers
'''
from sqlalchemy.orm import Session
from fastapi import Request
from services.utils import handle_service_errors
from services.replenishments import (
    create_complementary_competition_service,
    create_complementary_promo_point_service,
    create_replenishment_inventory_service,    # Binaria 2026-07-08
    create_replenishment_reception_service,
    create_replenishment_report_service,
    get_complementary_bandeo_by_id_service,    # iter6
    get_latest_replenishment_inventory_service,  # Binaria 2026-07-08
    list_complementary_bandeos_for_visit_service,  # iter6
    list_complementary_competitions_service,   # Binaria 2026-07-07
    list_complementary_promo_points_service,   # Binaria 2026-07-07
    list_replenishment_inventory_service,      # Binaria 2026-07-08
    list_all_complementary_bandeos_service,   # Binaria 2026-07-17
    list_all_replenishment_receptions_service,   # Binaria 2026-07-08
    list_replenishment_reception_service,   # iter5
    list_replenishment_reports_service,     # iter5
    plan_complementary_bandeo_service,      # Binaria 2026-07-17
    receive_complementary_bandeo_service,   # iter6
    return_complementary_bandeo_service,    # iter6
)
from schemas.replenishments import (
    ComplementaryBandeoGlobalQuerySchema,     # Binaria 2026-07-17
    ComplementaryBandeoListResponseSchema,    # iter6
    ComplementaryBandeoPlanSchema,            # Binaria 2026-07-17
    ComplementaryBandeoReceiveSchema,         # iter6
    ComplementaryBandeoResponseSchema,
    ComplementaryBandeoReturnSchema,          # iter6
    ComplementaryCompetitionCreateSchema,
    ComplementaryCompetitionListResponseSchema,   # Binaria 2026-07-07
    ComplementaryCompetitionQuerySchema,          # Binaria 2026-07-07
    ComplementaryCompetitionResponseSchema,
    ComplementaryPromoPointCreateSchema,
    ComplementaryPromoPointListResponseSchema,    # Binaria 2026-07-07
    ComplementaryPromoPointQuerySchema,           # Binaria 2026-07-07
    ComplementaryPromoPointResponseSchema,
    ReplenishmentInventoryCreateSchema,           # Binaria 2026-07-08
    ReplenishmentInventoryListResponseSchema,     # Binaria 2026-07-08
    ReplenishmentInventoryQuerySchema,            # Binaria 2026-07-08
    ReplenishmentReceptionCreateSchema,
    ReplenishmentReceptionListResponseSchema,
    ReplenishmentReceptionGlobalQuerySchema,  # Binaria 2026-07-08
    ReplenishmentReceptionQuerySchema,        # iter5
    ReplenishmentReportCreateSchema,
    ReplenishmentReportListResponseSchema,    # iter5
    ReplenishmentReportQuerySchema,           # iter5
    ReplenishmentReportResponseSchema,
)

# --- B.2. REPLENISHMENT ACTIVITIES Controllers ---

@handle_service_errors('TRADE')
async def create_replenishment_report_controller(
    attendance_id: int,
    report_data: ReplenishmentReportCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ReplenishmentReportResponseSchema:
    '''
        Controller for creating a Replenishment Report (Success Photos).
        Photos are handled separately.
    '''
    db_report = await create_replenishment_report_service(
        db = db,
        attendance_id = attendance_id,
        report_data = report_data
    )
    return ReplenishmentReportResponseSchema.model_validate(
        db_report, from_attributes = True
    )

# iter5 (Binaria, 2026-06-20): create_replenishment_inventory_controller
# was removed. Inventory now lives in the unified Impulses tables; use
# the Impulses inventory-start / inventory-end controllers instead.

@handle_service_errors('TRADE')
async def create_replenishment_reception_controller(
    attendance_id: int,
    reception_data: ReplenishmentReceptionCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ReplenishmentReceptionListResponseSchema:
    '''
        Controller for creating a Replenishment Reception (Supplier) report.
    '''
    created_items = await create_replenishment_reception_service(
        db = db,
        attendance_id = attendance_id,
        reception_data = reception_data
    )

    return ReplenishmentReceptionListResponseSchema(
        items = created_items,
        total = len(created_items)
    )

# --- iter5: LIST controllers ---

@handle_service_errors('TRADE')
async def list_replenishment_reports_controller(
    query: ReplenishmentReportQuerySchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> ReplenishmentReportListResponseSchema:
    '''
        Controller for paginated listing of replenishment reports.
    '''
    items, total = await list_replenishment_reports_service(
        db = db, query = query
    )
    return ReplenishmentReportListResponseSchema(
        items = [
            ReplenishmentReportResponseSchema.model_validate(item, from_attributes = True)
            for item in items
        ],
        total = total
    )

# iter5: list_replenishment_inventory_controller removed (use Impulses).

@handle_service_errors('TRADE')
async def list_replenishment_reception_controller(
    attendance_id: int,
    query: ReplenishmentReceptionQuerySchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> ReplenishmentReceptionListResponseSchema:
    '''
        Controller for listing the reception rows of a single visit.
    '''
    items, total = await list_replenishment_reception_service(
        db = db, attendance_id = attendance_id, query = query
    )
    return ReplenishmentReceptionListResponseSchema(
        items = items,
        total = total
    )


@handle_service_errors('TRADE')
async def list_all_replenishment_receptions_controller(
    query: ReplenishmentReceptionGlobalQuerySchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str  # pylint: disable=unused-argument
) -> ReplenishmentReceptionListResponseSchema:
    '''
        Binaria 2026-07-08: controller for the global supplier-reception listing
        across visits, filterable by company / client / pos / user / date range.
    '''
    items, total = await list_all_replenishment_receptions_service(
        db = db, query = query
    )
    return ReplenishmentReceptionListResponseSchema(
        items = items,
        total = total
    )

# --- B.3. COMPLEMENTARY ACTIVITIES Controllers ---

# iter6 (Binaria, 2026-06-22): the legacy single-shot
# create_complementary_bandeo_controller was replaced by the 2-stage flow
# below (Recibir + Devolver) plus listing/lookup controllers.

@handle_service_errors('TRADE')
async def plan_complementary_bandeo_controller(
    plan_data: ComplementaryBandeoPlanSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplementaryBandeoResponseSchema:
    '''
        Binaria 2026-07-17: controller for the Plan step of a Bandeo (pre-visit).
    '''
    db_bandeo = await plan_complementary_bandeo_service(
        db = db,
        plan_data = plan_data
    )
    return ComplementaryBandeoResponseSchema.model_validate(
        db_bandeo, from_attributes = True
    )


@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def receive_complementary_bandeo_controller(
    attendance_id: int,
    bandeo_id: int,
    bandeo_data: ComplementaryBandeoReceiveSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplementaryBandeoResponseSchema:
    '''
        Controller for the Receive step of a Bandeo.
    '''
    db_bandeo = await receive_complementary_bandeo_service(
        db = db,
        attendance_id = attendance_id,
        bandeo_id = bandeo_id,
        bandeo_data = bandeo_data
    )
    return ComplementaryBandeoResponseSchema.model_validate(
        db_bandeo, from_attributes = True
    )


@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def return_complementary_bandeo_controller(
    attendance_id: int,
    bandeo_id: int,
    return_data: ComplementaryBandeoReturnSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplementaryBandeoResponseSchema:
    '''
        Controller for the Return step of a Bandeo.
    '''
    db_bandeo = await return_complementary_bandeo_service(
        db = db,
        attendance_id = attendance_id,
        bandeo_id = bandeo_id,
        return_data = return_data
    )
    return ComplementaryBandeoResponseSchema.model_validate(
        db_bandeo, from_attributes = True
    )


@handle_service_errors('TRADE')
async def list_complementary_bandeos_for_visit_controller(
    attendance_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplementaryBandeoListResponseSchema:
    '''
        Controller for the per-visit bandeo listing.
    '''
    items, total = await list_complementary_bandeos_for_visit_service(
        db = db, attendance_id = attendance_id
    )
    return ComplementaryBandeoListResponseSchema(
        items = [
            ComplementaryBandeoResponseSchema.model_validate(b, from_attributes = True)
            for b in items
        ],
        total = total
    )


@handle_service_errors('TRADE')
async def get_complementary_bandeo_by_id_controller(
    bandeo_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplementaryBandeoResponseSchema:
    '''
        Controller for the single-bandeo lookup used on re-entry.
    '''
    db_bandeo = await get_complementary_bandeo_by_id_service(
        db = db, bandeo_id = bandeo_id
    )
    return ComplementaryBandeoResponseSchema.model_validate(
        db_bandeo, from_attributes = True
    )


@handle_service_errors('TRADE')
async def list_all_complementary_bandeos_controller(
    query: ComplementaryBandeoGlobalQuerySchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplementaryBandeoListResponseSchema:
    '''
        Binaria 2026-07-17: controller for the global bandeo listing across POS
        and visits, filterable by company / client / pos / user / status / date.
    '''
    items, total = await list_all_complementary_bandeos_service(
        db = db, query = query
    )
    return ComplementaryBandeoListResponseSchema(
        items = [
            ComplementaryBandeoResponseSchema.model_validate(b, from_attributes = True)
            for b in items
        ],
        total = total
    )

@handle_service_errors('TRADE')
async def create_complementary_promo_point_controller(
    attendance_id: int,
    promo_point_data: ComplementaryPromoPointCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplementaryPromoPointResponseSchema:
    '''
        Controller for creating a Complementary Promotional Point Report (Photos).
    '''
    db_report = await create_complementary_promo_point_service(
        db = db,
        attendance_id = attendance_id,
        promo_point_data = promo_point_data
    )
    return ComplementaryPromoPointResponseSchema.model_validate(
        db_report, from_attributes = True
    )

@handle_service_errors('TRADE')
async def create_complementary_competition_controller(
    competition_data: ComplementaryCompetitionCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplementaryCompetitionResponseSchema:
    '''
        Controller for creating a general Competition Report.
    '''
    db_report = await create_complementary_competition_service(
        db = db,
        competition_data = competition_data
    )
    return ComplementaryCompetitionResponseSchema.model_validate(
        db_report, from_attributes = True
    )


@handle_service_errors('TRADE')
async def list_complementary_promo_points_controller(
    query: ComplementaryPromoPointQuerySchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplementaryPromoPointListResponseSchema:
    '''
        Binaria, 2026-07-07: paginated listing of promotional-point reports.
    '''
    items, total = await list_complementary_promo_points_service(
        db = db, query = query
    )
    return ComplementaryPromoPointListResponseSchema(
        items = [
            ComplementaryPromoPointResponseSchema.model_validate(item, from_attributes = True)
            for item in items
        ],
        total = total
    )


@handle_service_errors('TRADE')
async def list_complementary_competitions_controller(
    query: ComplementaryCompetitionQuerySchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplementaryCompetitionListResponseSchema:
    '''
        Binaria, 2026-07-07: paginated listing of competition reports.
    '''
    items, total = await list_complementary_competitions_service(
        db = db, query = query
    )
    return ComplementaryCompetitionListResponseSchema(
        items = [
            ComplementaryCompetitionResponseSchema.model_validate(item, from_attributes = True)
            for item in items
        ],
        total = total
    )


@handle_service_errors('TRADE')
async def create_replenishment_inventory_controller(
    attendance_id: int,
    inventory_data: ReplenishmentInventoryCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ReplenishmentInventoryListResponseSchema:
    '''
        Binaria, 2026-07-08: registers a line-free replenishment inventory.
    '''
    created = await create_replenishment_inventory_service(
        db = db, attendance_id = attendance_id, inventory_data = inventory_data
    )
    return ReplenishmentInventoryListResponseSchema(
        items = created, total = len(created)
    )


@handle_service_errors('TRADE')
async def get_latest_replenishment_inventory_controller(
    pos_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ReplenishmentInventoryListResponseSchema:
    '''
        Binaria, 2026-07-08: latest replenishment inventory registered at a POS.
    '''
    items, total = await get_latest_replenishment_inventory_service(
        db = db, pos_id = pos_id
    )
    return ReplenishmentInventoryListResponseSchema(items = items, total = total)


@handle_service_errors('TRADE')
async def list_replenishment_inventory_controller(
    query: ReplenishmentInventoryQuerySchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ReplenishmentInventoryListResponseSchema:
    '''
        Binaria, 2026-07-08: paginated listing of replenishment inventory lines.
    '''
    items, total = await list_replenishment_inventory_service(
        db = db, query = query
    )
    return ReplenishmentInventoryListResponseSchema(items = items, total = total)
