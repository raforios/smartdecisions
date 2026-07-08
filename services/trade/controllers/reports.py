'''
    Reports Controllers
    Orchestrates the generation of reports.
'''
from sqlalchemy.orm import Session
from fastapi import Request
from services.utils import handle_service_errors
from services.reports import (
    get_compliance_report_service,
    get_inventory_alerts_service,
    get_merchandising_report_service,
    get_photographic_report_service,
    get_sales_report_service,
    get_attendance_report_service,
)
from services.panel_reports import (
    get_impulses_panel_service,
    get_replenishments_panel_service,
    get_route_tracking_service,
)

from schemas.reports import (
    ComplianceFilterSchema,
    ComplianceReportResponseSchema,
    InventoryAlertFilterSchema,
    InventoryAlertResponseSchema,
    MerchandisingFilterSchema,
    MerchandisingReportResponseSchema,
    PhotoFilterSchema,
    PhotographicReportResponseSchema,
    SalesReportFilterSchema,
    SalesReportResponseSchema,
    AttendanceReportFilterSchema,
    AttendanceReportResponseSchema,
    ImpulsesPanelResponseSchema,
    PanelFilterSchema,
    ReplenishmentsPanelResponseSchema,
    RouteTrackingFilterSchema,
    RouteTrackingResponseSchema,
)

# --- COMPLIANCE REPORT CONTROLLER ---

@handle_service_errors('REPORTS')
async def get_compliance_report_controller(
    filters: ComplianceFilterSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ComplianceReportResponseSchema:
    '''
        Controller to retrieve the Compliance Report (Agenda vs Reality).
        Receives filters from the route and delegates calculation to the service.
    '''
    # Call the service logic
    # El servicio ya devuelve el objeto Pydantic 'ComplianceReportResponseSchema'
    report_data = await get_compliance_report_service(
        db = db,
        filters = filters
    )

    return report_data

# --- INVENTORY ALERTS CONTROLLER ---

@handle_service_errors('REPORTS')
async def get_inventory_alerts_controller(
    filters: InventoryAlertFilterSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> InventoryAlertResponseSchema:
    '''
        Controller to retrieve Inventory Alerts (Short Date / Stockout).
    '''
    return await get_inventory_alerts_service(
        db = db,
        filters = filters
    )

# --- SALES REPORT CONTROLLER ---

@handle_service_errors('REPORTS')
async def get_sales_report_controller(
    filters: SalesReportFilterSchema,
    auth_token: str,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> SalesReportResponseSchema:
    '''
        Controller to retrieve Detailed Sales Report.
    '''
    return await get_sales_report_service(
        db = db,
        filters = filters,
        auth_token = auth_token
    )

# --- MERCHANDISING REPORT CONTROLLER (NUEVO) ---
@handle_service_errors('REPORTS')
async def get_merchandising_report_controller(
    filters: MerchandisingFilterSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> MerchandisingReportResponseSchema:
    ''' Retrieve Merchandising activities (Bandeo, Comp, Promo). '''
    return await get_merchandising_report_service(
        db = db,
        filters = filters
    )

# --- PHOTOGRAPHIC REPORT CONTROLLER (NUEVO) ---
@handle_service_errors('REPORTS')
async def get_photographic_report_controller(
    filters: PhotoFilterSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PhotographicReportResponseSchema:
    ''' Retrieve consolidated Photo Gallery. '''
    return await get_photographic_report_service(
        db = db,
        filters = filters
    )

# --- ATTENDANCE REPORT CONTROLLER ---

@handle_service_errors('REPORTS')
async def get_attendance_report_controller(
    filters: AttendanceReportFilterSchema,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> AttendanceReportResponseSchema:
    '''
        Controller to retrieve the Attendance & Geofencing Report.
    '''
    return await get_attendance_report_service(
        db = db,
        filters = filters
    )


# ============================================================================
# iter6 (Binaria, 2026-06-22) — Monitor de Trade panels (req 7.4)
# ============================================================================
@handle_service_errors('REPORTS')
async def get_impulses_panel_controller(
    filters: PanelFilterSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str,  # pylint: disable=unused-argument
) -> ImpulsesPanelResponseSchema:
    '''
        Controller for the Impulses monitor panel.
    '''
    return await get_impulses_panel_service(db = db, filters = filters)


@handle_service_errors('REPORTS')
async def get_replenishments_panel_controller(
    filters: PanelFilterSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str,  # pylint: disable=unused-argument
) -> ReplenishmentsPanelResponseSchema:
    '''
        Controller for the Replenishments monitor panel.
    '''
    return await get_replenishments_panel_service(db = db, filters = filters)


@handle_service_errors('REPORTS')
async def get_route_tracking_controller(
    filters: RouteTrackingFilterSchema,
    db: Session,
    request: Request,  # pylint: disable=unused-argument
    current_user: str,  # pylint: disable=unused-argument
) -> RouteTrackingResponseSchema:
    '''
        Controller for the route tracking map.
    '''
    return await get_route_tracking_service(db = db, filters = filters)
