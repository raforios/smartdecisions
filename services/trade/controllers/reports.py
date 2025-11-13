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
    get_sales_report_service
)
from schemas.reports import (
    ComplianceFilterSchema,
    ComplianceReportResponseSchema,
    InventoryAlertFilterSchema,
    InventoryAlertResponseSchema,
    SalesReportFilterSchema,
    SalesReportResponseSchema
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
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> SalesReportResponseSchema:
    '''
        Controller to retrieve Detailed Sales Report.
    '''
    return await get_sales_report_service(
        db = db,
        filters = filters
    )
