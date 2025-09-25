'''
    Business logic services for Reports to Forms Microservice.
'''

from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from models.forms import FormHeader
from models.responses import FormResponse, Person, Contact
from schemas.reports import (
    AffiliationMonitorRequestSchema,
    ContactsByRouteReportRequestSchema
)
from schemas.responses import FormResponseDetailResponse
from services.exceptions import ServiceUnavailableError
from services.utils import _perform_request, handle_service_errors
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

# Carga las variables de entorno necesarias
ENV_VARS = load_and_validate_env_vars({
    'PLANNING_SERVICE_URL': str,
    'LOCALIZATION_SERVICE_URL': str
})

PLANNING_SERVICE_URL = ENV_VARS['PLANNING_SERVICE_URL']
LOCALIZATION_SERVICE_URL = ENV_VARS['LOCALIZATION_SERVICE_URL']
PLANNING_ENDPOINT = None
LOCALIZATION_ENDPOINT = None

if PLANNING_SERVICE_URL:
    PLANNING_ENDPOINT = f'{PLANNING_SERVICE_URL}/v1/plannings'

if LOCALIZATION_SERVICE_URL:
    LOCALIZATION_ENDPOINT = f'{LOCALIZATION_SERVICE_URL}/v1/localization'


@handle_service_errors('FORMS-REPORTS')
# pylint: disable=too-many-locals
async def calculate_affiliation_monitor(
    db: Session,
    request_data: AffiliationMonitorRequestSchema
) -> Dict[str, Any]:
    '''
        Calculates key metrics for the Affiliation Monitor report based on dynamic filters.
    '''
    # Start with a base query on FormResponse
    query = db.query(FormResponse).join(
        Contact, FormResponse.contact_id == Contact.id
    ).join(
        Person, FormResponse.person_id == Person.id
    ).join(
        FormHeader, FormResponse.form_id == FormHeader.id
    )

    # List to hold the conditions for dynamic filtering
    conditions = []

    # --- Apply required filters ---
    conditions.append(FormHeader.company_id == request_data.company_id)
    # The 'service_id' and 'management' will be handled in a more complex way
    # as they are likely stored in the FormHeader or related tables.
    # We will need to confirm where these are stored.
    # For now, let's assume they are simple fields on FormHeader.
    conditions.append(FormHeader.service_id == request_data.service_id)
    conditions.append(FormHeader.management == request_data.management)

    # --- Apply optional filters based on request_data ---
    if request_data.date_from and request_data.date_to:
        conditions.append(FormResponse.submission_date.between(
            request_data.date_from, request_data.date_to))
    elif request_data.date_from:
        conditions.append(FormResponse.submission_date >= request_data.date_from)

    if request_data.planned_route_ids:
        # This will be tricky, as 'planned_route_id' is in the 'Contact' table.
        # We need to filter based on that.
        conditions.append(Contact.planned_route_id.in_(request_data.planned_route_ids))

    if request_data.affiliation_number_from and request_data.affiliation_number_to:
        conditions.append(FormResponse.affiliation_number.between(
            request_data.affiliation_number_from,
            request_data.affiliation_number_to
        ))
    elif request_data.affiliation_number_from:
        conditions.append(
            FormResponse.affiliation_number >= request_data.affiliation_number_from)

    if request_data.statuses:
        conditions.append(FormResponse.status.in_(request_data.statuses))

    # --- Execute the query with all conditions ---
    filtered_responses = query.filter(and_(*conditions)).all()

    # --- Perform calculations based on the filtered data ---
    # These calculations are done in Python after fetching the data.
    q_affiliations_registered = len(filtered_responses)

    q_affiliations_approved = 0
    q_referred_registered = 0
    q_persons_registered = 0
    q_contacts_marked = 0

    unique_person_ids = set()
    unique_contact_ids = set()
    unique_affiliate_user_ids = set()

    for response in filtered_responses:
        # Count approved affiliations based on the 'target_status'
        if response.status == request_data.target_status:
            q_affiliations_approved += 1

        # Count unique persons, contacts, and affiliates
        unique_person_ids.add(response.person_id)
        unique_contact_ids.add(response.contact_id)
        unique_affiliate_user_ids.add(response.user_id)

        # Check for referred persons
        # Note: 'is_referred' is a field in the Person model
        if response.person.is_referred:
            q_referred_registered += 1

    q_persons_registered = len(unique_person_ids)
    q_contacts_marked = len(unique_contact_ids)
    q_affiliators = len(unique_affiliate_user_ids)

    # Handle division by zero for percentage calculation
    percent_affiliations_approved = (
        q_affiliations_approved / q_affiliations_registered
        ) * 100 if q_affiliations_registered > 0 else 0

    # --- Calculate Objectives and Indicators ---
    period_target = request_data.target_affiliations * q_affiliators
    daily_target = period_target / request_data.working_days if request_data.working_days > 0 else 0

    # Calculate days transpired in the period (assuming today's date)
    # This is a simplification; a more robust solution would be needed
    # for full implementation.
    today = datetime.now().date()
    days_transpired = (today - request_data.date_from).days if request_data.date_from else 1

    ratio = (q_affiliations_approved / days_transpired) if days_transpired > 0 else 0
    individual_ratio = (ratio / q_affiliators) if q_affiliators > 0 else 0
    daily_need = (period_target - q_affiliations_approved) / (
        request_data.working_days - days_transpired) if (
            request_data.working_days - days_transpired) > 0 else 0

    # --- Build the response object ---
    return {
        'records': {
            'q_contacts_marked': q_contacts_marked,
            'q_persons_registered': q_persons_registered,
            'q_affiliations_registered': q_affiliations_registered,
            'q_affiliations_approved': q_affiliations_approved,
            'percent_affiliations_approved': round(percent_affiliations_approved, 2),
            'q_referred_registered': q_referred_registered,
        },
        'objectives': {
            'working_days_in_period': request_data.working_days,
            'period_target': period_target,
            'daily_target': round(daily_target, 2),
        },
        'indicators': {
            'ratio': round(ratio, 2),
            'individual_ratio': round(individual_ratio, 2),
            'daily_need': round(daily_need, 2),
        }
    }

async def _fetch_planned_routes_from_planning(
    request_data: ContactsByRouteReportRequestSchema,
    auth_token: str
) -> Optional[List[int]]:
    '''
        Fetches planned route IDs from the Planning microservice based on team ID or service ID.
    '''
    if not request_data.team_id and not request_data.service_id:
        return None

    try:
        query_params = {
            'company_id': request_data.company_id
        }
        if request_data.team_id:
            query_params['team_id'] = request_data.team_id
        if request_data.service_id:
            query_params['service_id'] = request_data.service_id
        url = f'{PLANNING_ENDPOINT}/filter?{urlencode(query_params)}'
        headers = {
            'Authorization': f'{auth_token}',
            'Content-Type': 'application/json'            
        }
        response = await _perform_request('GET', url, headers = headers)
        response.raise_for_status()
        data = response.json()

        planned_route_ids = set()
        for planning in data:
            for detail in planning.get('details', []):
                planned_route_ids.add(detail['planned_route_id'])

        return list(planned_route_ids)

    except Exception as exc:
        raise ServiceUnavailableError(
            detail = f'Failed to fetch planned routes from Planning service: {exc}'
        ) from exc

async def _fetch_planned_routes_from_localization(
    request_data: ContactsByRouteReportRequestSchema,
    auth_token: str
) -> Optional[List[int]]:
    '''
        Fetches planned route IDs from the Localization microservice based on city ID.
    '''
    if not request_data.city_id:
        return None

    try:
        query_params = {
            'company_id': request_data.company_id,
            'city_id': request_data.city_id
        }
        url = f'{LOCALIZATION_ENDPOINT}/routes/planned/filter?{urlencode(query_params)}'
        headers = {
            'Authorization': f'{auth_token}',
            'Content-Type': 'application/json'            
        }
        response = await _perform_request('GET', url, headers = headers)

        response.raise_for_status()
        data = response.json()
        logger.info('RESPONSE FROM LOCALIZATION')
        logger.info(data)

        return [route['id'] for route in data]
    except Exception as exc:
        raise ServiceUnavailableError(
            detail = f'Failed to fetch planned routes from Localization service: {exc}'
        ) from exc


async def _fetch_executed_points_from_localization(
    planned_route_id: int,
    auth_token: str
) -> List[int]:
    '''
        Fetches executed point IDs from the Localization microservice for a single planned route ID.
        This function uses the /routes/comparison endpoint to extract the executed points based on 
        the provided schema.
    '''
    try:
        url = f'{LOCALIZATION_ENDPOINT}/routes/comparison/{planned_route_id}'
        headers = {
            'Authorization': f'{auth_token}',
            'Content-Type': 'application/json'            
        }
        response = await _perform_request('GET', url, headers = headers)
        response.raise_for_status()
        data = response.json()

        executed_point_ids = []
        for route in data.get('executed_routes', []):
            for point in route.get('points', []):
                executed_point_ids.append(point['id'])

        return executed_point_ids

    except Exception as exc:
        raise ServiceUnavailableError(
            detail = f'Failed to fetch executed points from Localization service: {exc}'
        ) from exc


@handle_service_errors('FORMS-REPORTS')
async def generate_contacts_by_route_report(
    db: Session,
    request_data: ContactsByRouteReportRequestSchema,
    auth_token: str
) -> List[FormResponseDetailResponse]:
    '''
        Generates a detailed report by combining filters to find contacts,
        persons, routes, and forms.
    '''
    final_planned_route_ids = None
    final_executed_point_ids = []

    # 1. Aplicar los filtros de jerarquía
    if request_data.planned_route_id:
        # Jerarquía 1: planned_route_id es el filtro principal. Los demás se ignoran.
        final_planned_route_ids = {request_data.planned_route_id}
    elif request_data.user_id:
        # Jerarquía 2: user_id es el filtro principal si no hay planned_route_id.
        # En este caso, no hay un endpoint directo en la documentación para obtener
        # planned_route_ids desde un user_id, por lo que asumimos que
        # se obtendrán todos los planned_route_ids asociados a ese usuario
        # desde la base de datos de FORMS (t_contacts, t_form_responses).
        # Esto nos permitirá generar el reporte del trabajo del usuario.

        # Obtenemos los executed_point_ids del usuario directamente desde la BD local.
        executed_point_ids_from_user_contacts = db.query(Contact.executed_route_point_id)\
            .join(FormResponse, FormResponse.contact_id == Contact.id)\
            .filter(FormResponse.user_id == request_data.user_id).all()

        final_executed_point_ids = [point[0] for point in executed_point_ids_from_user_contacts]

    else:
        # Jerarquía 3: Usar filtros auxiliares si no hay planned_route_id ni user_id
        # Obtenemos un conjunto de IDs de cada filtro y luego hacemos una intersección.

        # Filtro por team_id o service_id (PLANNING)
        if request_data.team_id or request_data.service_id:
            ids_from_planning = await _fetch_planned_routes_from_planning(
                request_data=request_data,
                auth_token=auth_token
            )
            if ids_from_planning:
                final_planned_route_ids = set(ids_from_planning)

        # Filtro por city_id (LOCALIZATION)
        if request_data.city_id:
            ids_from_localization = await _fetch_planned_routes_from_localization(
                request_data=request_data,
                auth_token=auth_token
            )
            if ids_from_localization:
                if final_planned_route_ids is None:
                    final_planned_route_ids = set(ids_from_localization)
                else:
                    final_planned_route_ids &= set(ids_from_localization)

    # Si tenemos IDs de ruta planificada, obtenemos los puntos ejecutados.
    if final_planned_route_ids:
        for planned_id in final_planned_route_ids:
            executed_ids = await _fetch_executed_points_from_localization(
                planned_route_id=planned_id,
                auth_token=auth_token
            )
            final_executed_point_ids.extend(executed_ids)

    # 2. Construir la consulta a la base de datos
    if not final_executed_point_ids:
        return []

    query = db.query(FormResponse).join(
        FormResponse.contact
    ).join(
        FormResponse.person
    ).outerjoin(
        FormResponse.answers
    ).options(
        joinedload(FormResponse.contact),
        joinedload(FormResponse.person),
        joinedload(FormResponse.answers),
    )

    conditions = [
        FormResponse.company_id == request_data.company_id,
        Contact.executed_route_point_id.in_(final_executed_point_ids)
    ]

    # Aplicar el filtro de rango de fechas como subfiltro
    if request_data.submission_date_from and request_data.submission_date_to:
        conditions.append(
            FormResponse.submission_date.between(
                request_data.submission_date_from,
                request_data.submission_date_to
            )
        )

    # El filtro por user_id ya se manejó en la lógica de jerarquía.
    # No se aplica aquí como subfiltro para evitar redundancia y mantener la coherencia.
    if request_data.user_id and not request_data.planned_route_id:
        conditions.append(FormResponse.user_id == request_data.user_id)

    query = query.filter(and_(*conditions))

    results = query.all()

    return [FormResponseDetailResponse.model_validate(item) for item in results]
