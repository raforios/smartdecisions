'''
    Replenishments Controllers
'''
from sqlalchemy.orm import Session
from fastapi import Request
from services.utils import handle_service_errors
from services.replenishments import (
    create_complementary_bandeo_service,
    create_complementary_competition_service,
    create_complementary_promo_point_service,
    create_replenishment_inventory_service,
    create_replenishment_reception_service,
    create_replenishment_report_service,
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

@handle_service_errors('TRADE')
async def create_replenishment_inventory_controller(
    attendance_id: int,
    inventory_data_rep: ReplenishmentInventoryCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ReplenishmentInventoryListResponseSchema:
    '''
        Controller for creating a Replenishment Inventory (Detailed) report.
    '''
    created_items = await create_replenishment_inventory_service(
        db = db,
        attendance_id = attendance_id,
        inventory_data_rep = inventory_data_rep
    )

    return ReplenishmentInventoryListResponseSchema(
        items = created_items,
        total = len(created_items)
    )

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

# --- B.3. COMPLEMENTARY ACTIVITIES Controllers ---

@handle_service_errors('TRADE')
async def create_complementary_bandeo_controller(
    attendance_id: int,
    bandeo_data: ComplementaryBandeoCreateSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplementaryBandeoResponseSchema:
    '''
        Controller for creating a Complementary Bandeo Report (Returns/Photos).
    '''
    db_bandeo = await create_complementary_bandeo_service(
        db = db,
        attendance_id = attendance_id,
        bandeo_data = bandeo_data
    )
    return ComplementaryBandeoResponseSchema.model_validate(
        db_bandeo, from_attributes = True
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
