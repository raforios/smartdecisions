'''
    Business logic for the Participants module of the Mining Summit service.
'''
from typing import Any, Dict, List, Optional
from boto3.resources.base import ServiceResource

from schemas.enums import AssignmentType, ParticipantStatus
from services.crud import (
    create_item,
    find_item_by_key,
    get_all_records_paginated,
    get_item_by_key,
    scan_all_items
)
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError
from services.filters import filter_items_by_date_range
from services.institutions import get_institution
from services.logger_config import custom_logger as logger
from services.seating import select_seat
from services.utils import get_current_time_gmt, handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_PARTICIPANTS': str
})

PARTICIPANTS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_PARTICIPANTS']


def _build_participant_item(
    payload: Dict[str, Any],
    seat: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    '''
        Builds the DynamoDB item shape for a new participant, stamping the
        registration date/timestamp and defaulting the lifecycle status to
        ACTIVE. Any resolved seat attributes (role, eje, mesa) are merged in.
    '''
    now = get_current_time_gmt()
    item = {
        'ci': payload['ci'].strip(),
        'first_name': payload['first_name'].strip(),
        'last_name': payload['last_name'].strip(),
        'email': payload.get('email'),
        'phone': payload.get('phone'),
        'department': payload.get('department'),
        'company': payload.get('company'),
        'status': ParticipantStatus.ACTIVE.value,
        'observation': payload.get('observation'),
        'replaces_ci': payload.get('replaces_ci'),
        'replaced_by_ci': None,
        'registered_date': now.date().isoformat(),
        'registered_at': now.isoformat()
    }
    if seat:
        item.update(seat)
    # An explicit role (e.g. supplied by the ETL per file) overrides the role
    # derived from the institution category.
    if payload.get('role'):
        item['role'] = payload['role']
    return item


def _resolve_institution_attrs(
    dynamodb_resource: ServiceResource,
    institution_id: Optional[str]
) -> Dict[str, Any]:
    '''
        Resolves the persistable institution attributes for a participant.

        Returns:
            Dict[str, Any]: institution_id/name/role/assignment_type, or empty
                when no institution is supplied.
    '''
    if not institution_id:
        return {}
    institution = get_institution(dynamodb_resource, institution_id)
    return {
        'institution_id': institution['id'],
        'institution_name': institution['name'],
        'role': institution['role'],
        'assignment_type': institution['assignment_type']
    }


def _resolve_participant_seat(
    dynamodb_resource: ServiceResource,
    institution_id: Optional[str],
    axis: Optional[str]
) -> Dict[str, Any]:
    '''
        Resolves the institution attributes and, when an axis is chosen, the
        stable aula seat inside that axis. Participants loaded for the summit are
        fixed-seat: the chosen axis always wins, subject to the axis capacity.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            institution_id (Optional[str]): Reference institution slug.
            axis (Optional[str]): Thematic axis chosen by the participant.

        Returns:
            Dict[str, Any]: Attributes to persist (institution + optional seat).

        Raises:
            InvalidInputError: If the chosen axis is full or has no aulas.
    '''
    attrs = _resolve_institution_attrs(dynamodb_resource, institution_id)
    if not axis:
        return attrs
    mesa = select_seat(
        dynamodb_resource = dynamodb_resource,
        axis = axis,
        occupancy = compute_mesa_occupancy(dynamodb_resource)
    )
    attrs.update({
        'assignment_type': AssignmentType.FIJO.value,
        'axis': mesa['axis'],
        'axis_label': mesa['axis_label'],
        'mesa_code': mesa['code']
    })
    return attrs


@handle_service_errors
def create_participant(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Persists a new participant ensuring the CI is unique. When an axis is
        provided, a stable eje/mesa seat inside that axis is resolved and stored
        so the participant keeps it for the whole event.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            payload (Dict[str, Any]): Participant data (already validated).

        Returns:
            Dict[str, Any]: The persisted participant item.
    '''
    seat = _resolve_participant_seat(
        dynamodb_resource,
        payload.get('institution_id'),
        payload.get('axis')
    )
    item = _build_participant_item(payload, seat)
    message = f'Creating participant ci={item["ci"]}'
    logger.info(message)
    return create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        item_data = item,
        unique_key_attribute = 'ci'
    )


@handle_service_errors
def get_participant_by_ci(
    dynamodb_resource: ServiceResource,
    ci: str
) -> Dict[str, Any]:
    '''
        Retrieves a participant by CI. Raises RegisterNotFoundError if missing.
    '''
    return get_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        key = {'ci': ci.strip()}
    )


@handle_service_errors
def find_participant_by_ci(
    dynamodb_resource: ServiceResource,
    ci: str
) -> Optional[Dict[str, Any]]:
    '''
        Retrieves a participant by CI. Returns None if not found (no exception).
    '''
    return find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        key = {'ci': ci.strip()}
    )


@handle_service_errors
def list_participants(
    dynamodb_resource: ServiceResource,
    query_params: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Lists participants with optional filters and pagination. Equality
        filters (department, company, status) are pushed down to DynamoDB; the
        registered_from/registered_to range is applied client-side.

        By default only ACTIVE participants are returned (the initial reports
        exclude replaced/cancelled ones). Pass include_inactive=True to list all.
    '''
    date_from = query_params.pop('registered_from', None)
    date_to = query_params.pop('registered_to', None)
    include_inactive = query_params.pop('include_inactive', False)
    if not include_inactive and 'status' not in query_params:
        query_params['status'] = ParticipantStatus.ACTIVE.value

    response = get_all_records_paginated(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        query_params = query_params
    )
    response['items'] = filter_items_by_date_range(
        items = response['items'],
        date_field = 'registered_date',
        date_from = date_from,
        date_to = date_to
    )
    return response


@handle_service_errors
def scan_all_participants(
    dynamodb_resource: ServiceResource
) -> List[Dict[str, Any]]:
    '''
        Scans the full participants table. Used by the statistics report and the
        seating engine, which need the entire dataset.
    '''
    return scan_all_items(dynamodb_resource, PARTICIPANTS_TABLE)


def _is_active(participant: Dict[str, Any]) -> bool:
    '''
        Tells whether a participant still holds their seat. Legacy items without
        a status are treated as ACTIVE.
    '''
    return participant.get('status', ParticipantStatus.ACTIVE.value) == \
        ParticipantStatus.ACTIVE.value


@handle_service_errors
def compute_mesa_occupancy(dynamodb_resource: ServiceResource) -> Dict[str, int]:
    '''
        Counts how many ACTIVE participants are currently seated at each mesa, so
        the seating engine can pick the least-occupied one. Replaced/cancelled
        participants free their seat and are not counted.

        Returns:
            Dict[str, int]: Seat count keyed by mesa code (only seated actives).
    '''
    occupancy: Dict[str, int] = {}
    for participant in scan_all_participants(dynamodb_resource):
        mesa_code = participant.get('mesa_code')
        if mesa_code and _is_active(participant):
            occupancy[mesa_code] = occupancy.get(mesa_code, 0) + 1
    return occupancy


@handle_service_errors
def deactivate_participant(
    dynamodb_resource: ServiceResource,
    ci: str,
    observation: Optional[str] = None,
    new_status: str = ParticipantStatus.CANCELLED.value
) -> Dict[str, Any]:
    '''
        Soft-deletes an accredited participant: flips the status to CANCELLED
        (or REPLACED) and stores the observation. Data is retained but the
        participant no longer appears in the initial reports and frees the seat.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            ci (str): CI of the participant to deactivate.
            observation (Optional[str]): Reason / authorization note.
            new_status (str): Target inactive status (CANCELLED or REPLACED).

        Returns:
            Dict[str, Any]: The updated participant item.

        Raises:
            InvalidInputError: If the participant is already inactive.
            RegisterNotFoundError: If the CI does not exist.
    '''
    participant = get_participant_by_ci(dynamodb_resource, ci)
    if not _is_active(participant):
        raise InvalidInputError(
            detail = f'Participant ci={ci} is not active (status={participant.get("status")}).'
        )
    participant['status'] = new_status
    if observation is not None:
        participant['observation'] = observation
    dynamodb_resource.Table(PARTICIPANTS_TABLE).put_item(Item = participant)
    message = f'Participant ci={ci} deactivated with status={new_status}.'
    logger.info(message)
    return participant


@handle_service_errors
def replace_participant(
    dynamodb_resource: ServiceResource,
    outgoing_ci: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Replaces an accredited participant with a substitute authorized by the
        same institution. The substitute inherits the outgoing participant's
        exact seat (axis, mesa, institution) so the axis capacity is preserved;
        the outgoing participant is marked REPLACED (data retained).

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            outgoing_ci (str): CI of the participant stepping down.
            payload (Dict[str, Any]): New participant data (ci, first_name,
                last_name, contact, observation).

        Returns:
            Dict[str, Any]: The newly created substitute participant.

        Raises:
            InvalidInputError: If the outgoing participant is inactive or the new
                CI already exists.
            RegisterNotFoundError: If the outgoing CI does not exist.
    '''
    outgoing = get_participant_by_ci(dynamodb_resource, outgoing_ci)
    if not _is_active(outgoing):
        raise InvalidInputError(
            detail = f'Participant ci={outgoing_ci} is not active and cannot be replaced.'
        )

    now = get_current_time_gmt()
    substitute = {
        'ci': payload['ci'].strip(),
        'first_name': payload['first_name'].strip(),
        'last_name': payload['last_name'].strip(),
        'email': payload.get('email'),
        'phone': payload.get('phone'),
        'department': payload.get('department') or outgoing.get('department'),
        'company': payload.get('company'),
        'status': ParticipantStatus.ACTIVE.value,
        'observation': payload.get('observation'),
        'replaces_ci': outgoing_ci,
        'replaced_by_ci': None,
        # Inherit the outgoing participant's exact seat and institution.
        'institution_id': outgoing.get('institution_id'),
        'institution_name': outgoing.get('institution_name'),
        'role': outgoing.get('role'),
        'assignment_type': outgoing.get('assignment_type'),
        'axis': outgoing.get('axis'),
        'axis_label': outgoing.get('axis_label'),
        'mesa_code': outgoing.get('mesa_code'),
        'registered_date': now.date().isoformat(),
        'registered_at': now.isoformat()
    }
    saved = create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        item_data = substitute,
        unique_key_attribute = 'ci'
    )
    # Only after the substitute is safely persisted do we retire the outgoing one.
    deactivate_participant(
        dynamodb_resource = dynamodb_resource,
        ci = outgoing_ci,
        observation = payload.get('observation'),
        new_status = ParticipantStatus.REPLACED.value
    )
    outgoing_key = {'ci': outgoing_ci.strip()}
    dynamodb_resource.Table(PARTICIPANTS_TABLE).update_item(
        Key = outgoing_key,
        UpdateExpression = 'SET replaced_by_ci = :new_ci',
        ExpressionAttributeValues = {':new_ci': saved['ci']}
    )
    message = f'Participant ci={outgoing_ci} replaced by ci={saved["ci"]}.'
    logger.info(message)
    return saved


@handle_service_errors
def count_active_by_institution(
    dynamodb_resource: ServiceResource,
    institution_id: str
) -> int:
    '''
        Counts ACTIVE accredited participants of a given institution. Used to
        enforce the institution cupo during ETL load and on-the-fly creation.
    '''
    return sum(
        1 for participant in scan_all_participants(dynamodb_resource)
        if participant.get('institution_id') == institution_id and _is_active(participant)
    )


@handle_service_errors
def assert_cupo_available(
    dynamodb_resource: ServiceResource,
    institution_id: str
) -> None:
    '''
        Ensures the institution still has a free (unaccredited) cupo before an
        on-the-fly creation. Enforces the rule that new participants can only be
        added while the institution has spare quota.

        Raises:
            InvalidInputError: If the institution's cupo is already exhausted.
    '''
    institution = get_institution(dynamodb_resource, institution_id)
    used = count_active_by_institution(dynamodb_resource, institution_id)
    if used >= int(institution['cupos']):
        raise InvalidInputError(
            detail = (
                f'Institution "{institution["name"]}" has no free cupo '
                f'({used}/{institution["cupos"]} already accredited).'
            )
        )
