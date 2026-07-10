'''
    Business logic for the Participants module of the Mining Summit service.
'''
from typing import Any, Dict, List, Optional
from boto3.resources.base import ServiceResource

from schemas.enums import AssignmentType
from services.crud import (
    create_item,
    find_item_by_key,
    get_all_records_paginated,
    get_item_by_key
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
        registration date and timestamp using the configured target timezone.
        Any resolved seat attributes (role, eje, mesa) are merged in.
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
        'registered_date': now.date().isoformat(),
        'registered_at': now.isoformat()
    }
    if seat:
        item.update(seat)
    return item


def _resolve_participant_seat(
    dynamodb_resource: ServiceResource,
    institution_id: Optional[str]
) -> Dict[str, Any]:
    '''
        Resolves the role and seat assignment for a participant from their
        reference institution. Fixed-seat (FIJO) roles are auto-distributed to
        the least-occupied mesa; rotating roles are recorded without a seat.

        Returns:
            Dict[str, Any]: Attributes to persist (empty when no institution).

        Raises:
            InvalidInputError: If every fixed seat is already taken.
    '''
    if not institution_id:
        return {}
    institution = get_institution(dynamodb_resource, institution_id)
    seat: Dict[str, Any] = {
        'institution_id': institution['id'],
        'institution_name': institution['name'],
        'role': institution['role'],
        'assignment_type': institution['assignment_type']
    }
    if institution['assignment_type'] != AssignmentType.FIJO.value:
        return seat
    mesa = select_seat(compute_mesa_occupancy(dynamodb_resource))
    if mesa is None:
        raise InvalidInputError(detail = 'No fixed seats available; all mesas are full.')
    seat.update({
        'axis': mesa['axis'],
        'axis_label': mesa['axis_label'],
        'mesa_code': mesa['code']
    })
    return seat


@handle_service_errors
def create_participant(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Persists a new participant ensuring the CI is unique. When an
        institution is provided, the role and a stable eje/mesa seat are
        resolved and stored so the participant keeps them for the whole event.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            payload (Dict[str, Any]): Participant data (already validated).

        Returns:
            Dict[str, Any]: The persisted participant item.
    '''
    seat = _resolve_participant_seat(dynamodb_resource, payload.get('institution_id'))
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
        filters (department, company) are pushed down to DynamoDB; the
        registered_from/registered_to range is applied client-side.
    '''
    date_from = query_params.pop('registered_from', None)
    date_to = query_params.pop('registered_to', None)

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
        Scans the full participants table. Used by the statistics report,
        which needs the entire dataset to compute aggregations.
    '''
    table = dynamodb_resource.Table(PARTICIPANTS_TABLE)
    items: List[Dict[str, Any]] = []
    response = table.scan()
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey = response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    return items


@handle_service_errors
def compute_mesa_occupancy(dynamodb_resource: ServiceResource) -> Dict[str, int]:
    '''
        Counts how many participants are currently seated at each mesa, so the
        seating engine can pick the least-occupied one.

        Returns:
            Dict[str, int]: Seat count keyed by mesa code (only seated ones).
    '''
    occupancy: Dict[str, int] = {}
    for participant in scan_all_participants(dynamodb_resource):
        mesa_code = participant.get('mesa_code')
        if mesa_code:
            occupancy[mesa_code] = occupancy.get(mesa_code, 0) + 1
    return occupancy
