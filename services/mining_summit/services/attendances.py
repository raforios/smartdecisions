'''
    Business logic for the Attendances module of the Mining Summit service.
'''
from typing import Any, Dict, List, Optional, Tuple
from boto3.resources.base import ServiceResource

from services.crud import (
    get_all_records_paginated,
    put_unique_composite_item,
    query_by_partition
)
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger
from services.participants import create_participant, find_participant_by_ci
from services.utils import get_current_time_gmt, handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_ATTENDANCES': str
})

ATTENDANCES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_ATTENDANCES']


def _build_attendance_item(ci: str, marked_by: str) -> Dict[str, Any]:
    '''
        Builds the DynamoDB item shape for a new attendance using the
        configured timezone for the date components.
    '''
    now = get_current_time_gmt()
    return {
        'ci': ci.strip(),
        'attendance_date': now.date().isoformat(),
        'attendance_at': now.isoformat(),
        'marked_by': marked_by
    }


def _apply_date_range(
    items: List[Dict[str, Any]],
    date_from: Optional[str],
    date_to: Optional[str]
) -> List[Dict[str, Any]]:
    '''
        Filters attendances by an inclusive [date_from, date_to] range on
        attendance_date. Date filters are applied client-side because the
        generic CRUD primitive only pushes equality filters to DynamoDB.
    '''
    if not date_from and not date_to:
        return items
    filtered: List[Dict[str, Any]] = []
    for item in items:
        value = item.get('attendance_date')
        if not value:
            continue
        if date_from and value < date_from:
            continue
        if date_to and value > date_to:
            continue
        filtered.append(item)
    return filtered


def _ensure_participant_exists(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> bool:
    '''
        Ensures the CI is registered. If missing, registers the participant
        on-the-fly using the optional fields provided in the attendance payload.

        Returns:
            bool: True if the participant was created during this call.

        Raises:
            InvalidInputError: If the participant has to be created on-the-fly
                but mandatory fields (first_name, last_name) are missing.
    '''
    existing = find_participant_by_ci(dynamodb_resource, payload['ci'])
    if existing:
        return False

    if not payload.get('first_name') or not payload.get('last_name'):
        raise InvalidInputError(
            detail = (
                'Participant is not registered. To create on-the-fly, first_name '
                'and last_name must be provided.'
            )
        )

    create_participant(
        dynamodb_resource = dynamodb_resource,
        payload = {
            'ci': payload['ci'],
            'first_name': payload['first_name'],
            'last_name': payload['last_name'],
            'email': payload.get('email'),
            'phone': payload.get('phone'),
            'department': payload.get('department'),
            'company': payload.get('company')
        }
    )
    return True


@handle_service_errors
def register_attendance(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any],
    marked_by: str
) -> Tuple[Dict[str, Any], bool]:
    '''
        Registers an attendance for the given CI in the current Bolivia day.
        Auto-creates the participant if missing. The composite (ci,
        attendance_date) key enforces a single attendance per participant per
        day; a duplicate raises RegisterAlreadyExistsError.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            payload (Dict[str, Any]): Attendance payload (validated).
            marked_by (str): Email of the authenticated operator.

        Returns:
            Tuple[Dict[str, Any], bool]: The persisted attendance and whether
            the participant was created during this call.
    '''
    participant_created = _ensure_participant_exists(dynamodb_resource, payload)

    item = _build_attendance_item(ci = payload['ci'], marked_by = marked_by)
    message = (
        f'Registering attendance ci={item["ci"]} '
        f'date={item["attendance_date"]} (participant_created={participant_created})'
    )
    logger.info(message)

    saved = put_unique_composite_item(
        dynamodb_resource = dynamodb_resource,
        table_name = ATTENDANCES_TABLE,
        item_data = item,
        partition_key = 'ci',
        sort_key = 'attendance_date'
    )
    return saved, participant_created


@handle_service_errors
def list_attendances(
    dynamodb_resource: ServiceResource,
    query_params: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Lists attendances. If 'ci' is provided, performs an efficient
        partition Query (with optional date range bound on the sort key);
        otherwise falls back to a paginated Scan with client-side date
        filtering.
    '''
    ci_filter: Optional[str] = query_params.get('ci')
    date_from: Optional[str] = query_params.get('date_from')
    date_to: Optional[str] = query_params.get('date_to')

    if ci_filter:
        items = query_by_partition(
            dynamodb_resource = dynamodb_resource,
            table_name = ATTENDANCES_TABLE,
            partition_key = 'ci',
            partition_value = ci_filter.strip(),
            sort_key = 'attendance_date',
            sort_between = {'from': date_from, 'to': date_to}
        )
        return {'items': items, 'last_evaluated_key': None}

    scan_params = {
        k: v for k, v in query_params.items()
        if k not in ('date_from', 'date_to')
    }
    response = get_all_records_paginated(
        dynamodb_resource = dynamodb_resource,
        table_name = ATTENDANCES_TABLE,
        query_params = scan_params
    )
    response['items'] = _apply_date_range(
        items = response['items'],
        date_from = date_from,
        date_to = date_to
    )
    return response
