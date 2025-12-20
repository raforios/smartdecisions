'''
    Reports Controller
'''

from typing import List
from fastapi import Request
from sqlalchemy.orm import Session
from schemas.responses import FormResponseDetailResponse
from schemas.reports import (
    AffiliationMonitorRequestSchema,
    AffiliationMonitorResponseSchema,
    ContactsByRouteReportRequestSchema
)
from services.reports import (
    calculate_affiliation_monitor,
    generate_contacts_by_route_report
)
from services.utils import handle_service_errors

@handle_service_errors('FORMS-REPORTS')
async def get_affiliation_monitor_data(
    db: Session,
    auth_token: str,
    request_data: AffiliationMonitorRequestSchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> AffiliationMonitorResponseSchema:
    '''
        Controller to process the request and fetch data for the Affiliation Monitor report.
    '''
    # The actual business logic is delegated to the service layer.
    report_data = await calculate_affiliation_monitor(db, request_data, auth_token)
    return report_data

@handle_service_errors('FORMS-REPORTS', with_log = False)
async def get_contacts_by_route_report_data(
    db: Session,
    auth_token: str,
    request_data: ContactsByRouteReportRequestSchema,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> List[FormResponseDetailResponse]:
    '''
        Controller to process the request and fetch data for the Forms by Points and Contact report.
    '''
    # The actual business logic is delegated to the service layer.
    report_data = await generate_contacts_by_route_report(db, request_data, auth_token)
    return report_data
