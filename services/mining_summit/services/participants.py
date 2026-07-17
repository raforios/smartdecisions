'''
    Business logic for the Participants module of the Mining Summit service.

    This module owns the person master data (mining_summit_participants). The
    event seat/registration lives in the registration module and is joined here
    by `ci` to expose a single participant view to the API and reports.
'''
from typing import Any, Dict, List, Optional
from boto3.resources.base import ServiceResource

from schemas.enums import ParticipantStatus
from services.crud import (
    create_item,
    find_item_by_key,
    get_item_by_key,
    scan_all_items
)
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError
from services.filters import filter_items_by_date_range
from services.institutions import INSTITUTIONS_TABLE, get_institution
from services.logger_config import custom_logger as logger
from services.registration import (
    RegistrationMeta,
    assign_seat,
    create_registration,
    deactivate_registration,
    find_registration_by_ci,
    is_active,
    resolve_seat,
    scan_all_registrations,
    set_replaced_by
)
from services.utils import get_current_time_gmt, handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_PARTICIPANTS': str
})

PARTICIPANTS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_PARTICIPANTS']

# Registration fields surfaced in the joined participant view.
_REGISTRATION_FIELDS = (
    'assignment_type', 'axis', 'axis_label', 'mesa_code', 'status',
    'observation', 'replaces_ci', 'replaced_by_ci', 'registered_at',
    'registered_by', 'status_changed_by', 'status_changed_at'
)


def _build_person_item(payload: Dict[str, Any], role: Optional[str]) -> Dict[str, Any]:
    '''
        Builds the DynamoDB item shape for a new person (participant master),
        stamping the creation timestamp. Seat/registration data is NOT stored
        here; it lives in the registration table.
    '''
    return {
        'ci': payload['ci'].strip(),
        'first_name': payload['first_name'].strip(),
        'last_name': payload['last_name'].strip(),
        'email': payload.get('email'),
        'phone': payload.get('phone'),
        'department': payload.get('department'),
        'institution_id': payload.get('institution_id'),
        'role': role,
        'created_at': get_current_time_gmt().isoformat()
    }


def _resolve_role(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> Optional[str]:
    '''
        Resolves the person's functional role: an explicit role in the payload
        (e.g. supplied by the ETL) wins; otherwise it is derived from the
        institution category. Returns None when neither is available.
    '''
    if payload.get('role'):
        return payload['role']
    institution_id = payload.get('institution_id')
    if not institution_id:
        return None
    return get_institution(dynamodb_resource, institution_id)['role']


def _institution_name_map(dynamodb_resource: ServiceResource) -> Dict[str, str]:
    '''
        Builds an institution_id -> name map from the institutions catalog so a
        batch of participants can be joined without one lookup per row.
    '''
    return {
        institution['id']: institution.get('name')
        for institution in scan_all_items(dynamodb_resource, INSTITUTIONS_TABLE)
    }


def _merge(
    person: Dict[str, Any],
    registration: Optional[Dict[str, Any]],
    institution_name: Optional[str]
) -> Dict[str, Any]:
    '''
        Merges the person master data with its (optional) registration and the
        resolved institution name into the single participant view returned by
        the API and consumed by the reports.
    '''
    view = dict(person)
    view['institution_name'] = institution_name
    for field in _REGISTRATION_FIELDS:
        view[field] = registration.get(field) if registration else None
    view['registered'] = is_active(registration)
    return view


@handle_service_errors
def create_participant(
    dynamodb_resource: ServiceResource,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Creates a person ensuring the CI is unique. When an axis is provided the
        person is also registered: a stable eje/mesa seat inside that axis is
        resolved and stored in the registration table so the participant keeps
        it for the whole event. Returns the joined participant view.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            payload (Dict[str, Any]): Participant data (already validated).

        Returns:
            Dict[str, Any]: The joined participant view (person + registration).
    '''
    role = _resolve_role(dynamodb_resource, payload)
    person = _build_person_item(payload, role)
    message = f'Creating person ci={person["ci"]}'
    logger.info(message)
    saved_person = create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        item_data = person,
        unique_key_attribute = 'ci'
    )

    registration = None
    if payload.get('axis'):
        seat = resolve_seat(dynamodb_resource, payload['axis'])
        registration = create_registration(
            dynamodb_resource = dynamodb_resource,
            ci = saved_person['ci'],
            seat = seat,
            meta = RegistrationMeta(observation = payload.get('observation'))
        )

    institution_name = None
    if saved_person.get('institution_id'):
        institution_name = _institution_name_map(dynamodb_resource).get(
            saved_person['institution_id']
        )
    return _merge(saved_person, registration, institution_name)


@handle_service_errors
def get_participant_by_ci(
    dynamodb_resource: ServiceResource,
    ci: str
) -> Dict[str, Any]:
    '''
        Retrieves a person by CI. Raises RegisterNotFoundError if missing.
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
        Retrieves a person by CI. Returns None if not found (no exception).
    '''
    return find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        key = {'ci': ci.strip()}
    )


@handle_service_errors
def get_participant_view(
    dynamodb_resource: ServiceResource,
    ci: str
) -> Dict[str, Any]:
    '''
        Retrieves the joined participant view (person + registration + institution
        name) by CI. Raises RegisterNotFoundError if the person is missing.
    '''
    person = get_participant_by_ci(dynamodb_resource, ci)
    registration = find_registration_by_ci(dynamodb_resource, ci)
    institution_name = None
    if person.get('institution_id'):
        institution_name = _institution_name_map(dynamodb_resource).get(
            person['institution_id']
        )
    return _merge(person, registration, institution_name)


def _passes_filters(view: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    '''
        Applies the in-memory participant filters to a joined view: person
        attributes (department, institution_id) and registration attributes
        (axis, status), plus the default that hides replaced/cancelled ones.
    '''
    if filters.get('department') and view.get('department') != filters['department']:
        return False
    if filters.get('institution_id') and view.get('institution_id') != filters['institution_id']:
        return False
    if filters.get('axis') and view.get('axis') != filters['axis']:
        return False

    status = view.get('status')
    if filters.get('status'):
        return status == filters['status']
    if filters.get('include_inactive'):
        return True
    # Default: hide people whose registration was replaced/cancelled; people
    # without a registration (loaded but not seated) still show.
    return status in (None, ParticipantStatus.ACTIVE.value)


@handle_service_errors
def list_participants(
    dynamodb_resource: ServiceResource,
    query_params: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Lists the joined participant view with optional filters. People are the
        master set; each is joined with its registration and institution name.
        By default replaced/cancelled registrations are hidden; pass
        include_inactive=True (or an explicit status) to list them.
    '''
    date_from = query_params.pop('registered_from', None)
    date_to = query_params.pop('registered_to', None)
    limit = query_params.pop('limit', 50)
    query_params.pop('last_evaluated_key', None)

    registrations = {
        registration['ci']: registration
        for registration in scan_all_registrations(dynamodb_resource)
    }
    institution_names = _institution_name_map(dynamodb_resource)

    views: List[Dict[str, Any]] = []
    for person in scan_all_items(dynamodb_resource, PARTICIPANTS_TABLE):
        registration = registrations.get(person['ci'])
        view = _merge(
            person, registration, institution_names.get(person.get('institution_id'))
        )
        if _passes_filters(view, query_params):
            views.append(view)

    views = filter_items_by_date_range(
        items = views,
        date_field = 'registered_at',
        date_from = date_from,
        date_to = date_to
    )
    views.sort(key = lambda view: (view.get('last_name') or '', view.get('first_name') or ''))
    return {'items': views[:limit], 'last_evaluated_key': None}


@handle_service_errors
def scan_all_participants(
    dynamodb_resource: ServiceResource
) -> List[Dict[str, Any]]:
    '''
        Scans the full persons table. Used by the statistics report and the cupo
        enforcement, which need the entire person dataset.
    '''
    return scan_all_items(dynamodb_resource, PARTICIPANTS_TABLE)


def _apply_person_edits(
    dynamodb_resource: ServiceResource,
    person: Dict[str, Any],
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Applies the editable person fields onto the loaded person. Changing the
        institution re-derives the role and is validated against the new
        institution cupo (a person that moves in must have a free slot).

        Returns:
            Dict[str, Any]: The mutated person (not yet persisted).
    '''
    for field in ('first_name', 'last_name', 'email', 'phone', 'department'):
        if payload.get(field) is not None:
            person[field] = payload[field]

    new_institution = payload.get('institution_id')
    if new_institution is not None and new_institution != person.get('institution_id'):
        assert_cupo_available(dynamodb_resource, new_institution)
        person['institution_id'] = new_institution
        person['role'] = get_institution(dynamodb_resource, new_institution)['role']
    return person


@handle_service_errors
def update_participant(
    dynamodb_resource: ServiceResource,
    ci: str,
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Edits an existing participant so it can be fully accredited: updates the
        person fields, (re)assigns the institution (with cupo validation) and,
        when an axis is provided, seats the person in a stable eje/mesa of that
        axis (validated against the axis aula availability).

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            ci (str): CI of the participant to edit.
            payload (Dict[str, Any]): Partial participant data (validated).

        Returns:
            Dict[str, Any]: The joined participant view after the edit.

        Raises:
            RegisterNotFoundError: If the participant (person) does not exist.
            InvalidInputError: If the institution cupo is full or the chosen axis
                has no free aula.
    '''
    person = get_participant_by_ci(dynamodb_resource, ci)
    person = _apply_person_edits(dynamodb_resource, person, payload)
    dynamodb_resource.Table(PARTICIPANTS_TABLE).put_item(Item = person)
    message = f'Participant ci={ci} edited.'
    logger.info(message)

    registration = find_registration_by_ci(dynamodb_resource, ci)
    axis = payload.get('axis')
    if axis is not None:
        current_axis = registration.get('axis') if is_active(registration) else None
        if current_axis != axis:
            seat = resolve_seat(dynamodb_resource, axis)
            registration = assign_seat(
                dynamodb_resource = dynamodb_resource,
                ci = ci,
                seat = seat,
                observation = payload.get('observation')
            )

    institution_name = None
    if person.get('institution_id'):
        institution_name = _institution_name_map(dynamodb_resource).get(
            person['institution_id']
        )
    return _merge(person, registration, institution_name)


@handle_service_errors
def deactivate_participant(
    dynamodb_resource: ServiceResource,
    ci: str,
    observation: Optional[str] = None,
    new_status: str = ParticipantStatus.CANCELLED.value,
    changed_by: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Soft-deletes a participant's registration: flips its status to CANCELLED
        (or REPLACED), freeing the seat. The person master data is retained. The
        person must have an active registration.

        Raises:
            InvalidInputError: If the person has no active registration.
            RegisterNotFoundError: If the CI (person or registration) is missing.
    '''
    person = get_participant_by_ci(dynamodb_resource, ci)
    registration = find_registration_by_ci(dynamodb_resource, ci)
    if not is_active(registration):
        raise InvalidInputError(
            detail = f'Participant ci={ci} has no active registration to deactivate.'
        )
    registration = deactivate_registration(
        dynamodb_resource = dynamodb_resource,
        ci = ci,
        observation = observation,
        new_status = new_status,
        changed_by = changed_by
    )
    institution_name = None
    if person.get('institution_id'):
        institution_name = _institution_name_map(dynamodb_resource).get(
            person['institution_id']
        )
    return _merge(person, registration, institution_name)


@handle_service_errors
def replace_participant(
    dynamodb_resource: ServiceResource,
    outgoing_ci: str,
    payload: Dict[str, Any],
    changed_by: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Replaces an accredited participant with a substitute authorized by the
        same institution. A new person is created and registered inheriting the
        outgoing participant's exact seat (axis/mesa/institution); the outgoing
        registration is marked REPLACED (all data retained).

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            outgoing_ci (str): CI of the participant stepping down.
            payload (Dict[str, Any]): Substitute data (ci, first_name, last_name,
                contact, observation).

        Returns:
            Dict[str, Any]: The joined view of the new substitute participant.

        Raises:
            InvalidInputError: If the outgoing participant has no active
                registration, or the substitute CI already exists.
            RegisterNotFoundError: If the outgoing CI does not exist.
    '''
    outgoing_person = get_participant_by_ci(dynamodb_resource, outgoing_ci)
    outgoing_registration = find_registration_by_ci(dynamodb_resource, outgoing_ci)
    if not is_active(outgoing_registration):
        raise InvalidInputError(
            detail = f'Participant ci={outgoing_ci} has no active registration to replace.'
        )

    substitute_person = _build_person_item(
        {
            'ci': payload['ci'],
            'first_name': payload['first_name'],
            'last_name': payload['last_name'],
            'email': payload.get('email'),
            'phone': payload.get('phone'),
            'department': payload.get('department') or outgoing_person.get('department'),
            'institution_id': outgoing_person.get('institution_id')
        },
        role = outgoing_person.get('role')
    )
    saved_person = create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = PARTICIPANTS_TABLE,
        item_data = substitute_person,
        unique_key_attribute = 'ci'
    )

    # The substitute inherits the outgoing participant's exact seat.
    inherited_seat = {
        'assignment_type': outgoing_registration.get('assignment_type'),
        'axis': outgoing_registration.get('axis'),
        'axis_label': outgoing_registration.get('axis_label'),
        'mesa_code': outgoing_registration.get('mesa_code')
    }
    substitute_registration = create_registration(
        dynamodb_resource = dynamodb_resource,
        ci = saved_person['ci'],
        seat = inherited_seat,
        meta = RegistrationMeta(
            observation = payload.get('observation'),
            replaces_ci = outgoing_ci,
            registered_by = changed_by
        )
    )

    # Only after the substitute is safely persisted do we retire the outgoing one,
    # recording the operator who authorized the replacement.
    deactivate_registration(
        dynamodb_resource = dynamodb_resource,
        ci = outgoing_ci,
        observation = payload.get('observation'),
        new_status = ParticipantStatus.REPLACED.value,
        changed_by = changed_by
    )
    set_replaced_by(dynamodb_resource, outgoing_ci, saved_person['ci'])

    message = f'Participant ci={outgoing_ci} replaced by ci={saved_person["ci"]}.'
    logger.info(message)
    institution_name = None
    if saved_person.get('institution_id'):
        institution_name = _institution_name_map(dynamodb_resource).get(
            saved_person['institution_id']
        )
    return _merge(saved_person, substitute_registration, institution_name)


@handle_service_errors
def count_active_by_institution(
    dynamodb_resource: ServiceResource,
    institution_id: str
) -> int:
    '''
        Counts accredited people of a given institution: persons whose
        registration is not REPLACED/CANCELLED (people without a registration
        still occupy their institution cupo). Used to enforce the cupo.
    '''
    inactive_cis = {
        registration['ci']
        for registration in scan_all_registrations(dynamodb_resource)
        if not is_active(registration)
    }
    return sum(
        1 for person in scan_all_participants(dynamodb_resource)
        if person.get('institution_id') == institution_id
        and person['ci'] not in inactive_cis
    )


@handle_service_errors
def assert_cupo_available(
    dynamodb_resource: ServiceResource,
    institution_id: str
) -> None:
    '''
        Ensures the institution still has a free (unaccredited) cupo before an
        on-the-fly creation.

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
