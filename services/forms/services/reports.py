'''
    Business logic services for Reports to Forms Microservice.
'''

from datetime import datetime
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urlencode
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, select
from models.responses import FormResponse, Person, Contact
from schemas.reports import (
    AffiliationMonitorRequestSchema,
    ContactsByRouteReportRequestSchema
)
from schemas.responses import FormResponseDetailResponse
from services.utils import _perform_request, handle_service_errors
from services.environment import load_and_validate_env_vars

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

async def _check_service_and_company_existence(
    db: Session,
    company_id: int,
    service_id: int
) -> bool:
    '''
        Checks if at least one FormResponse exists for the given company_id and service_id.
    '''

    exists_query = select(FormResponse.id).filter(
        and_(
            FormResponse.company_id == company_id,
            FormResponse.service_id == service_id
        )
    ).limit(1)

    # db.scalar() ejecuta la consulta y retorna el primer elemento (el ID), o None si no hay.
    result = db.execute(exists_query)
    count = result.scalar()

    return count is not None

@handle_service_errors('PLANNING')
async def _fetch_planned_ids_from_planning(
    db: Session,
    request_data: AffiliationMonitorRequestSchema,
    auth_token: str
) -> Optional[Set[int]]:
    '''
        Fetches planned route IDs from the Planning microservice based on various filters.
    '''
    if not await _check_service_and_company_existence(
        db,
        request_data.company_id,
        request_data.service_id
    ):
        return None

    query_params = {
        'company_id': request_data.company_id,
        'service_id': request_data.service_id
    }

    # Agrega filtros opcionales si están presentes
    if request_data.year is not None:
        query_params['year'] = request_data.year
    if request_data.period is not None:
        query_params['period'] = request_data.period
    if request_data.team_ids:
        query_params['team_ids'] = request_data.team_ids
    if request_data.user_ids:
        query_params['user_ids'] = request_data.user_ids

    # Asume un endpoint `monitor-filter` en el servicio Planning para esta lógica
    url = f'{PLANNING_ENDPOINT}/monitor-filter?{urlencode(
        query_params, doseq = True)}'
    headers = {'Authorization': f'{auth_token}'}

    response = await _perform_request('GET', url, headers = headers)
    response.raise_for_status()
    data = response.json()

    # Extrae los planned_route_ids de la respuesta
    return {item['planned_route_id'] for item in data}

@handle_service_errors('LOCALIZATION')
async def _fetch_planned_ids_from_localization(
    request_data: AffiliationMonitorRequestSchema,
    auth_token: str
) -> Optional[Set[int]]:
    '''
        Fetches planned route IDs from the Localization microservice based on city ID.
    '''
    query_params = None
    if request_data.city_ids is not None:
        query_params = {'city_id': request_data.city_ids}

    url = f'{LOCALIZATION_ENDPOINT}/routes/planned/filter?{urlencode(
        query_params, doseq = True)}'
    headers = {'Authorization': f'{auth_token}'}
    response = await _perform_request('GET', url, headers = headers)
    response.raise_for_status()
    data = response.json()

    return {route['id'] for route in data}

# --- Orquestador de filtros ---

async def _get_planned_route_ids_for_monitor(
    db: Session,
    request_data: AffiliationMonitorRequestSchema,
    auth_token: str
) -> Optional[Set[int]]:
    '''
        Determines the final set of planned route IDs based on the filtering hierarchy.
    '''
    if request_data.planned_route_ids:
        # Prioridad 1: planned_route_ids es el filtro principal.
        return set(request_data.planned_route_ids)

    # Si no hay planned_route_ids, se aplican los filtros de Planning
    planned_ids_from_planning = await _fetch_planned_ids_from_planning(
        db = db,
        request_data = request_data,
        auth_token = auth_token
    )
    if not planned_ids_from_planning:
        return None  # No hay datos para los filtros de Planning

    planned_route_ids = planned_ids_from_planning

    # Si hay city_ids, se hace la intersección
    if request_data.city_ids:
        planned_ids_from_localization = await _fetch_planned_ids_from_localization(
            request_data,
            auth_token
        )
        if planned_ids_from_localization:
            planned_route_ids.intersection_update(planned_ids_from_localization)

    return planned_route_ids


@handle_service_errors('LOCALIZATION')
async def _fetch_executed_point_ids_from_localization(
    planned_route_ids: Set[int],
    auth_token: str
) -> Optional[Set[int]]:
    '''
        Fetches executed point IDs from the Localization microservice
        based on a set of planned route IDs.
    '''
    query_params = {'planned_route_ids': list(planned_route_ids)}
    url = f'{LOCALIZATION_ENDPOINT}/routes/executed-points/filter?{urlencode(
        query_params, doseq = True)}'
    headers = {'Authorization': f'{auth_token}'}

    response = await _perform_request('GET', url, headers = headers)
    response.raise_for_status()
    data = response.json()

    return set(data)

# --- Lógica principal del reporte ---

@handle_service_errors('FORMS-REPORTS')
# pylint: disable=too-many-locals,too-many-branches,too-many-statements
async def calculate_affiliation_monitor(
    db: Session,
    request_data: AffiliationMonitorRequestSchema,
    auth_token: str
) -> Dict[str, Any]:
    '''
        Calculates key metrics for the Affiliation Monitor report based on dynamic filters.
    '''
    # 1. Obtener los planned_route_ids según la jerarquía
    planned_route_ids = await _get_planned_route_ids_for_monitor(
        db = db,
        request_data = request_data,
        auth_token = auth_token
    )

    if not planned_route_ids:
        return {
            'records': {},
            'objectives': {},
            'indicators': {}
        }

    # 2. Obtener los executed_point_ids a partir de los planned_route_ids
    executed_point_ids = await _fetch_executed_point_ids_from_localization(
        planned_route_ids,
        auth_token
    )

    if not executed_point_ids:
        return {
            'records': {},
            'objectives': {},
            'indicators': {}
        }

    # 3. Construir la consulta a la base de datos local
    query = db.query(FormResponse).join(
        Contact, FormResponse.contact_id == Contact.id
    ).join(
        Person, FormResponse.person_id == Person.id
    )

    # Lista para las condiciones del filtro
    conditions = []

    # Filtro de executed_route_point_id (obligatorio)
    conditions.append(Contact.executed_route_point_id.in_(executed_point_ids))

    # Filtro de service_id (Mandatorio por schema)
    conditions.append(FormResponse.service_id == request_data.service_id)

    # Aplicar el resto de los filtros opcionales
    if request_data.date_from and request_data.date_to:
        conditions.append(FormResponse.submission_date.between(
            request_data.date_from, request_data.date_to))
    elif request_data.date_from:
        conditions.append(FormResponse.submission_date >= request_data.date_from)
    elif request_data.date_to:
        conditions.append(FormResponse.submission_date <= request_data.date_to)

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

    filtered_responses = query.filter(and_(*conditions)).all()

    # --- Realizar los cálculos con los datos filtrados ---
    q_affiliations_registered = len(filtered_responses)

    q_affiliations_approved = 0
    q_referred_registered = 0

    unique_person_ids = set()
    unique_contact_ids = set()
    unique_affiliate_user_ids = set()

    for response in filtered_responses:
        if response.status == request_data.target_status:
            q_affiliations_approved += 1

        unique_person_ids.add(response.person_id)
        unique_contact_ids.add(response.contact_id)
        unique_affiliate_user_ids.add(response.user_id)

        if response.person and response.person.is_referred:
            q_referred_registered += 1

    q_persons_registered = len(unique_person_ids)
    q_contacts_marked = len(unique_contact_ids)
    q_affiliators = len(unique_affiliate_user_ids)

    # Cálculo de métricas
    percent_affiliations_approved = (
        q_affiliations_approved / q_affiliations_registered
        ) * 100 if q_affiliations_registered > 0 else 0

    period_target = request_data.target_affiliations * q_affiliators
    daily_target = period_target / request_data.working_days if request_data.working_days > 0 else 0

    today = datetime.now().date()
    days_transpired = (today - request_data.date_from).days if request_data.date_from else 1
    # Asegurarse de que days_transpired sea al menos 1 para evitar divisiones por cero o lógicas
    # negativas si no hay fecha de inicio.
    if days_transpired <= 0:
        days_transpired = 1

    ratio = q_affiliations_approved / days_transpired
    individual_ratio = (ratio / q_affiliators) if q_affiliators > 0 else 0
    daily_need_denominator = request_data.working_days - days_transpired
    daily_need = (period_target - q_affiliations_approved) / daily_need_denominator if \
        daily_need_denominator > 0 else 0

    # --- Construir el objeto de respuesta ---
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

@handle_service_errors('PLANNING')
async def _fetch_planned_routes_from_planning(
    db: Session,
    request_data: ContactsByRouteReportRequestSchema,
    auth_token: str
) -> Optional[List[int]]:
    '''
        Fetches planned route IDs from the Planning microservice based on team ID or service ID.
    '''
    if not request_data.team_id and not request_data.service_id and not request_data.company_id:
        return None

    if not await _check_service_and_company_existence(
        db,
        request_data.company_id,
        request_data.service_id
    ):
        return None

    query_params = {
        'company_id': request_data.company_id,
        'service_id': request_data.service_id
    }
    if request_data.team_id:
        query_params['team_id'] = request_data.team_id
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

@handle_service_errors('LOCALIZATION')
async def _fetch_planned_routes_from_localization(
    request_data: ContactsByRouteReportRequestSchema,
    auth_token: str
) -> Optional[List[int]]:
    '''
        Fetches planned route IDs from the Localization microservice based on city ID.
    '''
    if not request_data.city_id:
        return None

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

    return [route['id'] for route in data]

@handle_service_errors('LOCALIZATION')
async def _fetch_executed_points_from_localization(
    planned_route_id: int,
    auth_token: str
) -> List[int]:
    '''
        Fetches executed point IDs from the Localization microservice for a single planned route ID.
        This function uses the /routes/comparison endpoint to extract the executed points based on 
        the provided schema.
    '''
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

@handle_service_errors('LOCALIZATION')
async def _get_company_id_from_localization(
    planned_route_id: int,
    auth_token: str
) -> Optional[int]:
    '''
        Fetches the company ID associated with a planned route from the Localization service.
    '''
    url = f'{LOCALIZATION_ENDPOINT}/routes/planned/{planned_route_id}'
    headers = {
        'Authorization': f'{auth_token}',
        'Content-Type': 'application/json'
    }
    response = await _perform_request('GET', url, headers = headers)
    response.raise_for_status()
    data = response.json()
    return data.get('company_id')

async def _get_planned_route_ids_from_request(
    db: Session,
    request_data: ContactsByRouteReportRequestSchema,
    auth_token: str
) -> Optional[Set[int]]:
    '''
        Applies the filtering hierarchy to get a set of planned route IDs.
    '''
    final_planned_route_ids = None

    if request_data.planned_route_id:
        final_planned_route_ids = {request_data.planned_route_id}
    elif request_data.team_id or request_data.service_id:
        ids_from_planning = await _fetch_planned_routes_from_planning(
            db = db,
            request_data = request_data,
            auth_token = auth_token
        )
        if ids_from_planning:
            final_planned_route_ids = set(ids_from_planning)

    if request_data.city_id:
        ids_from_localization = await _fetch_planned_routes_from_localization(
            request_data = request_data,
            auth_token = auth_token
        )
        if ids_from_localization:
            if final_planned_route_ids is None:
                final_planned_route_ids = set(ids_from_localization)
            else:
                final_planned_route_ids &= set(ids_from_localization)

    return final_planned_route_ids

async def _get_executed_point_ids(
    db: Session,
    request_data: ContactsByRouteReportRequestSchema,
    auth_token: str
) -> List[int]:
    '''
        Determines the final list of executed point IDs based on request filters.
    '''
    final_executed_point_ids = []

    if request_data.user_id and not request_data.planned_route_id:
        # Jerarquía 2: user_id es el filtro principal si no hay planned_route_id.
        executed_point_ids_from_user = db.query(Contact.executed_route_point_id)\
            .join(FormResponse, FormResponse.contact_id == Contact.id)\
            .filter(FormResponse.user_id == request_data.user_id).all()

        final_executed_point_ids = [point[0] for point in executed_point_ids_from_user]
    else:
        # Aplica el resto de la jerarquía de filtros de ruta
        final_planned_route_ids = await _get_planned_route_ids_from_request(
            db = db,
            request_data = request_data,
            auth_token = auth_token
        )

        if final_planned_route_ids:
            for planned_id in final_planned_route_ids:
                executed_ids = await _fetch_executed_points_from_localization(
                    planned_route_id = planned_id,
                    auth_token = auth_token
                )
                final_executed_point_ids.extend(executed_ids)

    return final_executed_point_ids


@handle_service_errors('FORMS-REPORTS')
async def generate_contacts_by_route_report(
    db: Session,
    request_data: ContactsByRouteReportRequestSchema,
    auth_token: str
) -> List[FormResponseDetailResponse]:
    '''
        Generates a detailed report by combining filters to find contacts,
        persons, routes, and forms. (Simplified: service_id taken from request/DB).
    '''
    company_id = request_data.company_id

    # 1. Obtener la company_id si planned_route_id está presente y company_id no
    if request_data.planned_route_id and not company_id:
        company_id = await _get_company_id_from_localization(
            planned_route_id = request_data.planned_route_id,
            auth_token = auth_token
        )
        if not company_id:
            return []

    # 2. Obtener los executed_point_ids
    final_executed_point_ids = await _get_executed_point_ids(
        db = db,
        request_data = request_data,
        auth_token = auth_token
    )

    if not final_executed_point_ids:
        return []

    # 3. Construir la consulta a la base de datos con los filtros
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
        Contact.executed_route_point_id.in_(final_executed_point_ids),
        FormResponse.submission_date.between(
            request_data.submission_date_from,
            request_data.submission_date_to
        )
    ]

    if company_id:
        conditions.append(FormResponse.company_id == company_id)

    if request_data.service_id:
        conditions.append(FormResponse.service_id == request_data.service_id)

    if request_data.user_id and not request_data.planned_route_id:
        conditions.append(FormResponse.user_id == request_data.user_id)

    query = query.filter(and_(*conditions))

    results = query.all()

    # 4. Retornar las respuestas. El service_id ya está en el modelo FormResponse
    # y será mapeado automáticamente por FormResponseDetailResponse.
    return [FormResponseDetailResponse.model_validate(form_response) for form_response in results]
