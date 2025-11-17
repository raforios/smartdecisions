'''
    Reports: routes handler
'''
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.orm import Session
from schemas.responses import FormResponseDetailResponse
from schemas.reports import (
    AffiliationMonitorRequestSchema,
    AffiliationMonitorResponseSchema,
    ContactsByRouteReportRequestSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from controllers.reports import get_affiliation_monitor_data, get_contacts_by_route_report_data

router = APIRouter(prefix = '/v1/reports', tags = ['Reports'])

@router.post(
    '/affiliation-monitor',
    response_model = AffiliationMonitorResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Generates the Affiliation Monitor report.',
    description = '''Calculates and returns key metrics and indicators for affiliations
        based on a complex set of filtering criteria and objectives.'''
)
async def get_affiliation_monitor_report(
    request_data: AffiliationMonitorRequestSchema,
    request: Request,
    auth_token: str = Header(..., alias = 'Authorization'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> Dict[str, Any]:
    '''
        Endpoint to get the Affiliation Monitor data.
        Requires a POST request with the filtering criteria and objective metrics in the body.
    '''
    return await get_affiliation_monitor_data(
        db = db,
        request_data = request_data,
        request = request,
        current_user = current_user,
        auth_token = auth_token
    )

@router.post(
    '/contacts-by-route',
    response_model = List[FormResponseDetailResponse],
    status_code = status.HTTP_200_OK,
    summary = 'Generates the Forms by Points and Contact report.',
    description = '''Retrieves detailed data of form responses, including associated
        contacts, persons, and answers, based on a complex set of filters.'''
)
async def get_contacts_by_route_report(
    request_data: ContactsByRouteReportRequestSchema,
    request: Request,
    auth_token: str = Header(..., alias = 'Authorization'),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
) -> List[FormResponseDetailResponse]:
    '''
        Endpoint to get detailed report data of forms by route and contact.
    '''
    return await get_contacts_by_route_report_data(
        db = db,
        request_data = request_data,
        request = request,
        current_user = current_user,
        auth_token = auth_token
    )
