'''
    Participants controllers.
'''
from typing import Any, Dict
from boto3.resources.base import ServiceResource

from schemas.participants import (
    ParticipantCreateSchema,
    ParticipantDeactivateSchema,
    ParticipantQuerySchema,
    ParticipantReplaceSchema,
    ParticipantResponseSchema,
    ParticipantsListResponseSchema,
    ParticipantUpdateSchema
)
from services.attendances import register_attendance
from services.participants import (
    assert_cupo_available,
    create_participant,
    deactivate_participant,
    get_participant_view,
    list_participants,
    replace_participant,
    update_participant
)
from services.utils import handle_service_errors


@handle_service_errors
def create_participant_controller(
    dynamodb_resource: ServiceResource,
    payload: ParticipantCreateSchema,
    current_user: str
) -> ParticipantResponseSchema:
    '''
        Controller to register a new participant on-the-fly (accreditation desk).
        Only allowed while the institution still has free cupo. Per business
        rule, the first attendance is recorded automatically with the operator
        email, since an on-the-fly creation happens at the event door.
    '''
    if payload.institution_id:
        assert_cupo_available(
            dynamodb_resource = dynamodb_resource,
            institution_id = payload.institution_id
        )
    saved = create_participant(
        dynamodb_resource = dynamodb_resource,
        payload = payload.model_dump(exclude_none = True)
    )
    register_attendance(
        dynamodb_resource = dynamodb_resource,
        payload = {'ci': saved['ci']},
        marked_by = current_user
    )
    return ParticipantResponseSchema(**saved)


@handle_service_errors
def get_participant_controller(
    dynamodb_resource: ServiceResource,
    ci: str
) -> ParticipantResponseSchema:
    '''
        Controller to retrieve a single participant by CI.
    '''
    item = get_participant_view(dynamodb_resource = dynamodb_resource, ci = ci)
    return ParticipantResponseSchema(**item)


@handle_service_errors
def list_participants_controller(
    dynamodb_resource: ServiceResource,
    query_params: ParticipantQuerySchema
) -> ParticipantsListResponseSchema:
    '''
        Controller to retrieve a paginated list of participants with filters.
        Defaults to ACTIVE participants only.
    '''
    response: Dict[str, Any] = list_participants(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params.model_dump(exclude_none = True)
    )
    return ParticipantsListResponseSchema(
        items = [ParticipantResponseSchema(**record) for record in response['items']],
        last_evaluated_key = response.get('last_evaluated_key')
    )


@handle_service_errors
def update_participant_controller(
    dynamodb_resource: ServiceResource,
    ci: str,
    payload: ParticipantUpdateSchema
) -> ParticipantResponseSchema:
    '''
        Controller to edit a participant (accreditation): person fields,
        institution (cupo-checked) and seat assignment by axis.
    '''
    updated = update_participant(
        dynamodb_resource = dynamodb_resource,
        ci = ci,
        payload = payload.model_dump(exclude_none = True)
    )
    return ParticipantResponseSchema(**updated)


@handle_service_errors
def deactivate_participant_controller(
    dynamodb_resource: ServiceResource,
    ci: str,
    payload: ParticipantDeactivateSchema,
    current_user: str
) -> ParticipantResponseSchema:
    '''
        Controller to soft-delete (deactivate) an accredited participant,
        recording the operator who cancelled it.
    '''
    updated = deactivate_participant(
        dynamodb_resource = dynamodb_resource,
        ci = ci,
        observation = payload.observation,
        changed_by = current_user
    )
    return ParticipantResponseSchema(**updated)


@handle_service_errors
def replace_participant_controller(
    dynamodb_resource: ServiceResource,
    outgoing_ci: str,
    payload: ParticipantReplaceSchema,
    current_user: str
) -> ParticipantResponseSchema:
    '''
        Controller to replace an accredited participant with a substitute that
        inherits the outgoing seat, recording the operator who authorized it.
    '''
    saved = replace_participant(
        dynamodb_resource = dynamodb_resource,
        outgoing_ci = outgoing_ci,
        payload = payload.model_dump(exclude_none = True),
        changed_by = current_user
    )
    return ParticipantResponseSchema(**saved)
