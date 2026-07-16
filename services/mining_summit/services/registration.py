'''
    Business logic for the Registration module of the Mining Summit service.

    A registration is the event seat (thematic axis + aula) held by a person,
    together with its lifecycle status and replacement chain. It is stored apart
    from the person master data (participants) and joined by `ci`, so a person
    can exist without a registration (loaded but not yet seated).
'''
from typing import Any, Dict, List, Optional
from boto3.resources.base import ServiceResource

from schemas.enums import AssignmentType, ParticipantStatus
from services.crud import (
    create_item,
    find_item_by_key,
    get_item_by_key,
    scan_all_items
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger
from services.seating import select_seat
from services.utils import get_current_time_gmt, handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_REGISTRATION': str
})

REGISTRATION_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_REGISTRATION']


def is_active(registration: Optional[Dict[str, Any]]) -> bool:
    '''
        Tells whether a registration exists and still holds its seat. A missing
        registration is not active; legacy items without a status are ACTIVE.
    '''
    if not registration:
        return False
    return registration.get('status', ParticipantStatus.ACTIVE.value) == \
        ParticipantStatus.ACTIVE.value


@handle_service_errors
def scan_all_registrations(
    dynamodb_resource: ServiceResource
) -> List[Dict[str, Any]]:
    '''
        Scans the full registration table. Used by the seating engine and the
        distribution reports, which need the entire dataset.
    '''
    return scan_all_items(dynamodb_resource, REGISTRATION_TABLE)


@handle_service_errors
def get_registration_by_ci(
    dynamodb_resource: ServiceResource,
    ci: str
) -> Dict[str, Any]:
    '''
        Retrieves a registration by CI. Raises RegisterNotFoundError if missing.
    '''
    return get_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = REGISTRATION_TABLE,
        key = {'ci': ci.strip()}
    )


@handle_service_errors
def find_registration_by_ci(
    dynamodb_resource: ServiceResource,
    ci: str
) -> Optional[Dict[str, Any]]:
    '''
        Retrieves a registration by CI. Returns None if not found (no exception).
    '''
    return find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = REGISTRATION_TABLE,
        key = {'ci': ci.strip()}
    )


@handle_service_errors
def compute_mesa_occupancy(dynamodb_resource: ServiceResource) -> Dict[str, int]:
    '''
        Counts how many ACTIVE registrations are seated at each mesa, so the
        seating engine can pick the least-occupied one. Replaced/cancelled
        registrations free their seat and are not counted.

        Returns:
            Dict[str, int]: Seat count keyed by mesa code (only active seats).
    '''
    occupancy: Dict[str, int] = {}
    for registration in scan_all_registrations(dynamodb_resource):
        mesa_code = registration.get('mesa_code')
        if mesa_code and is_active(registration):
            occupancy[mesa_code] = occupancy.get(mesa_code, 0) + 1
    return occupancy


@handle_service_errors
def resolve_seat(
    dynamodb_resource: ServiceResource,
    axis: str
) -> Dict[str, Any]:
    '''
        Resolves the stable aula seat inside the chosen axis for a new
        registration: the least-occupied aula of that axis with free capacity.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            axis (str): Thematic axis value chosen by the participant.

        Returns:
            Dict[str, Any]: assignment_type/axis/axis_label/mesa_code to persist.

        Raises:
            InvalidInputError: If the chosen axis is full or has no aulas.
    '''
    mesa = select_seat(
        dynamodb_resource = dynamodb_resource,
        axis = axis,
        occupancy = compute_mesa_occupancy(dynamodb_resource)
    )
    return {
        'assignment_type': AssignmentType.FIJO.value,
        'axis': mesa['axis'],
        'axis_label': mesa['axis_label'],
        'mesa_code': mesa['code']
    }


def build_registration_item(
    ci: str,
    seat: Dict[str, Any],
    observation: Optional[str] = None,
    replaces_ci: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Builds the DynamoDB item shape for a new registration, stamping the
        timestamp and defaulting the lifecycle status to ACTIVE.
    '''
    return {
        'ci': ci.strip(),
        'assignment_type': seat.get('assignment_type'),
        'axis': seat.get('axis'),
        'axis_label': seat.get('axis_label'),
        'mesa_code': seat.get('mesa_code'),
        'observation': observation,
        'replaces_ci': replaces_ci,
        'replaced_by_ci': None,
        'status': ParticipantStatus.ACTIVE.value,
        'registered_at': get_current_time_gmt().isoformat()
    }


@handle_service_errors
def create_registration(
    dynamodb_resource: ServiceResource,
    ci: str,
    seat: Dict[str, Any],
    observation: Optional[str] = None,
    replaces_ci: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Persists a new registration ensuring the CI is unique in the table.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            ci (str): CI of the person being registered.
            seat (Dict[str, Any]): Resolved seat (axis/mesa/assignment_type).
            observation (Optional[str]): Free-form note.
            replaces_ci (Optional[str]): CI this registration substitutes, if any.

        Returns:
            Dict[str, Any]: The persisted registration item.
    '''
    item = build_registration_item(ci, seat, observation, replaces_ci)
    message = f'Creating registration ci={item["ci"]} axis={item.get("axis")}'
    logger.info(message)
    return create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = REGISTRATION_TABLE,
        item_data = item,
        unique_key_attribute = 'ci'
    )


@handle_service_errors
def assign_seat(
    dynamodb_resource: ServiceResource,
    ci: str,
    seat: Dict[str, Any],
    observation: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Creates or overwrites the ACTIVE registration for a CI with the given
        seat. Unlike create_registration this upserts, so a person that had no
        registration (or a retired one) can be (re)seated during accreditation.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            ci (str): CI of the person being seated.
            seat (Dict[str, Any]): Resolved seat (axis/mesa/assignment_type).
            observation (Optional[str]): Free-form note.

        Returns:
            Dict[str, Any]: The persisted registration item.
    '''
    existing = find_registration_by_ci(dynamodb_resource, ci)
    replaces_ci = existing.get('replaces_ci') if existing else None
    item = build_registration_item(ci, seat, observation, replaces_ci)
    dynamodb_resource.Table(REGISTRATION_TABLE).put_item(Item = item)
    message = f'Seat assigned ci={ci} axis={item.get("axis")} mesa={item.get("mesa_code")}'
    logger.info(message)
    return item


@handle_service_errors
def deactivate_registration(
    dynamodb_resource: ServiceResource,
    ci: str,
    observation: Optional[str] = None,
    new_status: str = ParticipantStatus.CANCELLED.value
) -> Dict[str, Any]:
    '''
        Soft-deletes a registration: flips the status to CANCELLED (or REPLACED)
        and stores the observation, freeing the seat. The record is retained.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            ci (str): CI of the registration to deactivate.
            observation (Optional[str]): Reason / authorization note.
            new_status (str): Target inactive status (CANCELLED or REPLACED).

        Returns:
            Dict[str, Any]: The updated registration item.

        Raises:
            RegisterNotFoundError: If the CI has no registration.
    '''
    registration = get_registration_by_ci(dynamodb_resource, ci)
    registration['status'] = new_status
    if observation is not None:
        registration['observation'] = observation
    dynamodb_resource.Table(REGISTRATION_TABLE).put_item(Item = registration)
    message = f'Registration ci={ci} deactivated with status={new_status}.'
    logger.info(message)
    return registration


@handle_service_errors
def set_replaced_by(
    dynamodb_resource: ServiceResource,
    ci: str,
    substitute_ci: str
) -> None:
    '''
        Links an outgoing registration to the substitute that replaces it.
    '''
    dynamodb_resource.Table(REGISTRATION_TABLE).update_item(
        Key = {'ci': ci.strip()},
        UpdateExpression = 'SET replaced_by_ci = :new_ci',
        ExpressionAttributeValues = {':new_ci': substitute_ci}
    )
