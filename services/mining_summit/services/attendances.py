'''
    Business logic for the Attendances module of the Mining Summit service.
'''
from typing import Any, Dict, Optional, Tuple
from boto3.resources.base import ServiceResource

from schemas.enums import ParticipantStatus
from services.crud import (
    find_item_by_key,
    get_all_records_paginated,
    put_unique_composite_item,
    query_by_partition
)
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError, RegisterAlreadyExistsError
from services.filters import filter_items_by_date_range
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


def _ensure_participant_exists(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> bool:
    '''
        Ensures the CI is registered and accredited. If missing, registers the
        participant on-the-fly using the optional fields in the attendance
        payload. Inactive (replaced/cancelled) participants are rejected, since
        attendance verifies that the person was actually accredited.

        Returns:
            bool: True if the participant was created during this call.

        Raises:
            InvalidInputError: If the participant is inactive, or has to be
                created on-the-fly but mandatory fields are missing.
    '''
    existing = find_participant_by_ci(dynamodb_resource, payload['ci'])
    if existing:
        status_value = existing.get('status', ParticipantStatus.ACTIVE.value)
        if status_value != ParticipantStatus.ACTIVE.value:
            raise InvalidInputError(
                detail = (
                    f'Participant ci={payload["ci"]} is not accredited '
                    f'(status={status_value}); attendance cannot be registered.'
                )
            )
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

    # Business rule: attendance can only be registered once per day. Pre-check so
    # the operator gets an explicit message instead of a generic conflict.
    existing_today = find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = ATTENDANCES_TABLE,
        key = {'ci': item['ci'], 'attendance_date': item['attendance_date']}
    )
    if existing_today:
        raise RegisterAlreadyExistsError(
            detail = (
                f'Attendance for ci={item["ci"]} was already registered today '
                f'({item["attendance_date"]}).'
            )
        )

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
    response['items'] = filter_items_by_date_range(
        items = response['items'],
        date_field = 'attendance_date',
        date_from = date_from,
        date_to = date_to
    )
    return response
