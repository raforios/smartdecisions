'''
    Business logic services for Reports to Forms Microservice.
'''

import asyncio
from datetime import date
from typing import Dict, List, NamedTuple, Optional, Set
from urllib.parse import urlencode
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, select
from models.planning import PlanningDetail
from models.responses import Contact, FormResponse, Person
from schemas.reports import (
    AffiliationMonitorRequestSchema,
    AffiliationMonitorResponseSchema,
    ContactsByRouteReportRequestSchema,
    IndicatorsSummary,
    ObjectivesSummary,
    RecordsSummary
)
from schemas.responses import FormResponseDetailResponse
from schemas.planning import PlanningMonitorFilterSchema
from services.utils import _perform_request, handle_service_errors
from services.environment import load_and_validate_env_vars
from services.planning import get_planned_route_ids_for_monitor_service

ENV_VARS = load_and_validate_env_vars({
    'LOCALIZATION_SERVICE_URL': str
})

LOCALIZATION_SERVICE_URL = ENV_VARS['LOCALIZATION_SERVICE_URL']
LOCALIZATION_ENDPOINT = None

if LOCALIZATION_SERVICE_URL:
    LOCALIZATION_ENDPOINT = f'{LOCALIZATION_SERVICE_URL}/v1/localization'

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

@handle_service_errors('LOCALIZATION')
async def _fetch_executed_point_map_from_localization(
    planned_route_ids: Set[int],
    auth_token: str
) -> Dict[int, int]:
    '''
        Fetches executed point IDs from the Localization microservice for multiple planned
        routes concurrently.

        Constructs a mapping dictionary to link each executed point back to its parent
        planned route.

        This function performs parallel requests to minimize latency when querying multiple routes.

        Args:
            planned_route_ids (Set[int]): A set of unique planned route IDs to query.
            auth_token (str): The authorization token for the external service request.

        Returns:
            Dict[int, int]: A dictionary mapping {executed_point_id: planned_route_id}.
                            Returns an empty dict if no points are found or if the set is empty.
    '''
    point_to_route_map = {}

    # Function internal to request points for a SINGLE route
    async def fetch_points_for_single_route(route_id: int):
        query_params = {'planned_route_ids': [route_id]}
        # NOTE: Adjust the URL according to your actual endpoint
        url = f'{LOCALIZATION_ENDPOINT}/routes/executed-points/filter?{
            urlencode(query_params, doseq=True)}'
        headers = {'Authorization': auth_token}

        response = await _perform_request('GET', url, headers = headers)

        if response.status_code == 200:
            points = response.json()
            return route_id, points
        return route_id, []

    # Creating asynchronous tasks to request all routes in parallel
    tasks = [fetch_points_for_single_route(rid) for rid in planned_route_ids]

    # Executing all at once
    results = await asyncio.gather(*tasks)

    # Building the final map
    for route_id, points in results:
        for point_id in points:
            point_to_route_map[point_id] = route_id

    return point_to_route_map

def _resolve_target_route_ids(
    db: Session,
    request_data: ContactsByRouteReportRequestSchema
) -> Set[int]:
    '''
        Helper: Resolves the set of planned route IDs based on direct IDs or Team ID.
    '''
    target_route_ids: Set[int] = set()

    if request_data.planned_route_ids:
        target_route_ids = set(request_data.planned_route_ids)

    # Logic of Team ID
    if request_data.team_id:
        planning_q = select(PlanningDetail.planned_route_id).filter(
            PlanningDetail.service_id == request_data.service_id,
            PlanningDetail.team_id == request_data.team_id,
            PlanningDetail.date.between(
                request_data.submission_date_from,
                request_data.submission_date_to
            )
        )

        team_route_ids = set(db.execute(planning_q).scalars().all())

        if target_route_ids:
            target_route_ids.intersection_update(team_route_ids)
        else:
            target_route_ids = team_route_ids

    return target_route_ids

def _build_contacts_report_conditions(
    request_data: ContactsByRouteReportRequestSchema,
    valid_executed_point_ids: Set[int]
) -> List:
    '''
        Helper: Builds SQLAlchemy filter conditions.
    '''
    conditions = []

    # A. Mandatory Filters
    conditions.append(FormResponse.submission_date.between(
        request_data.submission_date_from,
        request_data.submission_date_to
    ))

    if request_data.service_id:
        conditions.append(FormResponse.service_id == request_data.service_id)

    if request_data.company_id:
        conditions.append(FormResponse.company_id == request_data.company_id)

    # B. Geographic Filter
    if valid_executed_point_ids:
        conditions.append(Contact.executed_route_point_id.in_(valid_executed_point_ids))

    # C. Optional Filters
    if request_data.user_ids:
        conditions.append(FormResponse.user_id.in_(request_data.user_ids))

    if request_data.status:
        conditions.append(FormResponse.status.in_(request_data.status))

    # D. Affiliation Number Logic
    if request_data.affiliation_number_start and request_data.affiliation_number_end:
        conditions.append(FormResponse.affiliation_number.between(
            request_data.affiliation_number_start,
            request_data.affiliation_number_end
        ))
    elif request_data.affiliation_number_start:
        conditions.append(FormResponse.affiliation_number >= request_data.affiliation_number_start)
    elif request_data.affiliation_number_end:
        conditions.append(FormResponse.affiliation_number <= request_data.affiliation_number_end)

    return conditions

# --- Internal data structure for transferring counts ---
class MonitorRawStats(NamedTuple):
    '''
        Immutable data structure to hold intermediate raw counts for the Affiliation Monitor report.

        This NamedTuple acts as a Data Transfer Object (DTO) to pass calculated
        statistics from the processing logic to the final response builder.
        It helps separate the data aggregation responsibility from the final
        metrics calculation (percentages, ratios).

        Attributes:
            total_registered (int): The total count of form responses found after filtering.
            total_approved (int): The count of responses matching the target status (e.g.,
            'APPROVED').
            total_referred (int): The count of persons registered who were marked as referred.
            unique_contacts (int): The count of distinct contact points (locations) visited.
            unique_persons (int): The count of distinct unique persons registered.
            unique_affiliators (int): The count of distinct users (affiliators) involved in
            the process.
    '''
    total_registered: int
    total_approved: int
    total_referred: int
    unique_contacts: int
    unique_persons: int
    unique_affiliators: int

def _build_monitor_query_conditions(
    executed_point_ids: Set[int],
    request_data: AffiliationMonitorRequestSchema
) -> List:
    '''
        Helper: Builds the list of SQLAlchemy filter conditions.
        Reduces complexity in the main function.
    '''
    conditions = []

    # A. Geographic/Route Filter
    conditions.append(Contact.executed_route_point_id.in_(executed_point_ids))

    # B. Service Filter
    conditions.append(FormResponse.service_id == request_data.service_id)

    # C. Date Filters
    if request_data.date_from:
        conditions.append(FormResponse.submission_date >= request_data.date_from)
    if request_data.date_to:
        conditions.append(FormResponse.submission_date <= request_data.date_to)

    # D. Affiliation Filters
    if request_data.affiliation_number_from:
        conditions.append(FormResponse.affiliation_number >= request_data.affiliation_number_from)
    if request_data.affiliation_number_to:
        conditions.append(FormResponse.affiliation_number <= request_data.affiliation_number_to)

    # E. Status Filters
    if request_data.statuses:
        conditions.append(FormResponse.status.in_(request_data.statuses))

    # F. User Filters
    if request_data.user_ids:
        conditions.append(FormResponse.user_id.in_(request_data.user_ids))

    return conditions

def _compute_raw_statistics(
    responses: List[FormResponse],
    target_status: str
) -> MonitorRawStats:
    '''
        Helper: Iterates through DB results to calculate raw counts and unique sets.
        Reduces branches and loops in the main function.
    '''
    q_approved = 0
    q_referred = 0

    unique_person_ids = set()
    unique_contact_ids = set()
    unique_affiliate_user_ids = set()

    for response in responses:
        # Approval
        if response.status == target_status:
            q_approved += 1

        # Uniqueness
        if response.person_id:
            unique_person_ids.add(response.person_id)
        if response.contact_id:
            unique_contact_ids.add(response.contact_id)
        if response.user_id:
            unique_affiliate_user_ids.add(response.user_id)

        # Referred
        if response.person and getattr(response.person, 'is_referred', False):
            q_referred += 1

    return MonitorRawStats(
        total_registered = len(responses),
        total_approved = q_approved,
        total_referred = q_referred,
        unique_contacts = len(unique_contact_ids),
        unique_persons = len(unique_person_ids),
        unique_affiliators = len(unique_affiliate_user_ids)
    )

def _build_final_metrics_response(
    stats: MonitorRawStats,
    request_data: AffiliationMonitorRequestSchema
) -> AffiliationMonitorResponseSchema:
    '''
        Helper: Performs business math and constructs the final Schema.
        Reduces local variables and statements in the main function.
    '''
    # 1. Approval Percentage
    percent_approved = 0.0
    if stats.total_registered > 0:
        percent_approved = (stats.total_approved / stats.total_registered) * 100

    # 2. Objectives
    period_target = request_data.target_affiliations * stats.unique_affiliators

    daily_target = 0.0
    if request_data.working_days > 0:
        daily_target = period_target / request_data.working_days

    # 3. Time Indicators
    today = date.today()
    start_date = request_data.date_from if request_data.date_from else today
    days_transpired = max(1, (today - start_date).days)

    ratio = stats.total_approved / days_transpired

    individual_ratio = 0.0
    if stats.unique_affiliators > 0:
        individual_ratio = ratio / stats.unique_affiliators

    # 4. Daily Need
    daily_need = 0.0
    remaining_days = request_data.working_days - days_transpired
    remaining_target = period_target - stats.total_approved

    if remaining_days > 0 and remaining_target > 0:
        daily_need = remaining_target / remaining_days

    return AffiliationMonitorResponseSchema(
        records = RecordsSummary(
            q_contacts_marked = stats.unique_contacts,
            q_persons_registered = stats.unique_persons,
            q_affiliations_registered = stats.total_registered,
            q_affiliations_approved = stats.total_approved,
            percent_affiliations_approved = round(percent_approved, 2),
            q_referred_registered = stats.total_referred
        ),
        objectives = ObjectivesSummary(
            working_days_in_period = request_data.working_days,
            period_target = period_target,
            daily_target = round(daily_target, 2)
        ),
        indicators = IndicatorsSummary(
            ratio = round(ratio, 2),
            individual_ratio = round(individual_ratio, 2),
            daily_need = round(daily_need, 2)
        )
    )

def _get_empty_monitor_response(
    working_days: int
) -> AffiliationMonitorResponseSchema:
    '''
        Helper for returning zeroed-out metrics.
    '''
    return AffiliationMonitorResponseSchema(
        records = RecordsSummary(
            q_contacts_marked = 0, q_persons_registered = 0,
            q_affiliations_registered = 0, q_affiliations_approved = 0,
            percent_affiliations_approved = 0.0, q_referred_registered = 0
        ),
        objectives = ObjectivesSummary(
            working_days_in_period=working_days,
            period_target = 0, daily_target = 0.0
        ),
        indicators = IndicatorsSummary(
            ratio = 0.0, individual_ratio = 0.0, daily_need = 0.0
        )
    )

# --- MAIN ORCHESTRATOR FUNCTION ---
@handle_service_errors('FORMS-REPORTS')
async def calculate_affiliation_monitor(
    db: Session,
    request_data: AffiliationMonitorRequestSchema,
    auth_token: str
) -> AffiliationMonitorResponseSchema:
    '''
        Orchestrator for the Affiliation Monitor Report.
        Coordinates Planning, Localization, and Forms services.
    '''

    # ---------------------------------------------------------
    # STEP 1: Obtain 'planned_route_ids' (Planning Service)
    # ---------------------------------------------------------
    planning_filters = PlanningMonitorFilterSchema(
        company_id = request_data.company_id,
        service_id = request_data.service_id,
        year = request_data.year,
        period = request_data.period,
        team_ids = request_data.team_ids,
        user_ids = request_data.user_ids
    )

    planned_routes_data = await get_planned_route_ids_for_monitor_service(
        db = db,
        filters = planning_filters
    )

    if not planned_routes_data:
        return _get_empty_monitor_response(request_data.working_days)

    planned_route_ids: Set[int] = {item['planned_route_id'] for item in planned_routes_data}

    # ---------------------------------------------------------
    # STEP 2: Obtain 'executed_point_ids' (Localization Service)
    # ---------------------------------------------------------
    executed_point_ids = await _fetch_executed_point_ids_from_localization(
        planned_route_ids = planned_route_ids,
        auth_token = auth_token
    )

    if not executed_point_ids:
        return _get_empty_monitor_response(request_data.working_days)

    # ---------------------------------------------------------
    # STEP 3: Build and Execute Query (FormResponse)
    # ---------------------------------------------------------
    query = db.query(FormResponse).join(
        Contact, FormResponse.contact_id == Contact.id
    ).join(
        Person, FormResponse.person_id == Person.id
    )

    conditions = _build_monitor_query_conditions(executed_point_ids, request_data)

    filtered_responses = query.filter(and_(*conditions)).all()

    # ---------------------------------------------------------
    # STEP 4: Processing and Return
    # ---------------------------------------------------------

    # Calculate raw statistics (count)
    raw_stats = _compute_raw_statistics(filtered_responses, request_data.target_status)

    # Calculate business metrics and build response
    return _build_final_metrics_response(raw_stats, request_data)

@handle_service_errors('FORMS-REPORTS', with_log=False)
async def generate_contacts_by_route_report(
    db: Session,
    request_data: ContactsByRouteReportRequestSchema,
    auth_token: str
) -> List[FormResponseDetailResponse]:
    '''
        Generates a consolidated report linking Form Responses to their corresponding
        Planned Routes.

        This function orchestrates data from the Planning context (Teams, Routes) and the
        Localization service (Execution Points) to accurately filter and attribute forms
        to specific routes.

        Key Operations:
        1. Resolves target routes based on provided Planned Route IDs or Team assignments.
        2. Fetches execution point mappings from the external Localization service to 
        bridge the gap between planned routes and actual field contacts.
        3. Filters Form Responses using both geographic data (points) and metadata 
        (dates, statuses, affiliation numbers).
        4. Enriches the output by injecting the specific 'planned_route_id' for each form.

        Args:
            db (Session): Database session for local queries.
            request_data (ContactsByRouteReportRequestSchema): Complex filtering criteria
                including dates, service, team, route specific IDs, and form statuses.
            auth_token (str): JWT token for authenticated requests to external microservices.

        Returns:
            List[FormResponseDetailResponse]: A list of enriched form details, including 
                the associated planned route ID.
    '''

    # ---------------------------------------------------------
    # STEP 1: Determine which routes to search (ID Resolution)
    # ---------------------------------------------------------
    target_route_ids = _resolve_target_route_ids(db, request_data)

    # ---------------------------------------------------------
    # STEP 2: Obtain MAP of Points {point_id: route_id}
    # ---------------------------------------------------------
    point_to_route_map: Dict[int, int] = {}

    if target_route_ids:
        point_to_route_map = await _fetch_executed_point_map_from_localization(
            planned_route_ids=target_route_ids,
            auth_token=auth_token
        )

    valid_executed_point_ids = set(point_to_route_map.keys())

    # Security validation
    if (request_data.planned_route_ids or request_data.team_id) and not valid_executed_point_ids:
        return []

    # ---------------------------------------------------------
    # STEP 3: Execute SQL Query (FormResponse)
    # ---------------------------------------------------------
    query = select(FormResponse).join(
        Contact, FormResponse.contact_id == Contact.id
    ).join(
        Person, FormResponse.person_id == Person.id
    ).options(
        joinedload(FormResponse.contact).joinedload(Contact.person),
        joinedload(FormResponse.answers)
    )

    # Get isolated conditions from helper
    conditions = _build_contacts_report_conditions(request_data, valid_executed_point_ids)

    query = query.filter(and_(*conditions))
    results = db.execute(query).scalars().unique().all()

    # ---------------------------------------------------------
    # STEP 4: Mapping and Building Response
    # ---------------------------------------------------------
    final_response = []

    for form in results:
        form_detail = FormResponseDetailResponse.model_validate(form)

        # Map injection logic
        if form.contact and form.contact.executed_route_point_id:
            executed_point = form.contact.executed_route_point_id

            if executed_point in point_to_route_map:
                form_detail.planned_route_id = point_to_route_map[executed_point]

        final_response.append(form_detail)

    return final_response
