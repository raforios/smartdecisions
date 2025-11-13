'''
    Reports: routes handler
'''
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.reports import (
    get_compliance_report_controller,
    get_inventory_alerts_controller,
    get_sales_report_controller
)
from schemas.reports import (
    ComplianceFilterSchema,
    ComplianceReportResponseSchema,
    InventoryAlertFilterSchema,
    InventoryAlertResponseSchema,
    SalesReportFilterSchema,
    SalesReportResponseSchema
)

router = APIRouter(prefix = '/v1/reports', tags = ['Reports'])

# --- COMPLIANCE REPORT ENDPOINT ---

@router.get(
    '/compliance',
    response_model = ComplianceReportResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get Compliance Report (Planned vs Executed)',
    description = '''Generates a report comparing planned visits vs actual execution,
            including Ad-Hoc visits and workload analysis.'''
)
async def get_compliance_report_endpoint(
    request: Request,
    filters: ComplianceFilterSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve the Compliance Report.
    '''
    message = f'User: {current_user}. Request Compliance Report for Company: {filters.company_id}.'
    logger.info(message)

    return await get_compliance_report_controller(
        filters = filters,
        db = db,
        request = request,
        current_user = current_user
    )

# --- INVENTORY ALERTS ENDPOINT ---

@router.get(
    '/inventory-alerts',
    response_model = InventoryAlertResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get Inventory Alerts (Stockouts & Short Dates)',
    description = 'Lists products with zero stock or marked as short-dated (semáforo).'
)
async def get_inventory_alerts_endpoint(
    request: Request,
    filters: InventoryAlertFilterSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve inventory alerts.
    '''
    message = f'User: {current_user}. Request Inventory Alerts for Company: {filters.company_id}.'
    logger.info(message)

    return await get_inventory_alerts_controller(
        filters = filters,
        db = db,
        request = request,
        current_user = current_user
    )

# --- SALES REPORT ENDPOINT ---

@router.get(
    '/sales',
    response_model = SalesReportResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get Sales Report (Dashboard Data)',
    description = 'Returns detailed sales data (flattened) suitable for Pivot Tables or Charts.'
)
async def get_sales_report_endpoint(
    request: Request,
    auth_token: str = Header(..., alias = 'Authorization'),
    filters: SalesReportFilterSchema = Depends(),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve sales data.
    '''
    message = f'User: {current_user}. Request Sales Report for Company: {filters.company_id}.'
    logger.info(message)

    return await get_sales_report_controller(
        filters = filters,
        db = db,
        request = request,
        current_user = current_user,
        auth_token = auth_token
    )
