'''
    Participants controllers.
'''
from typing import Any, Dict
from boto3.resources.base import ServiceResource

from schemas.participants import (
    ParticipantCreateSchema,
    ParticipantQuerySchema,
    ParticipantResponseSchema,
    ParticipantsListResponseSchema
)
from services.attendances import register_attendance
from services.participants import (
    create_participant,
    get_participant_by_ci,
    list_participants
)
from services.utils import handle_service_errors


@handle_service_errors
def create_participant_controller(
    dynamodb_resource: ServiceResource,
    payload: ParticipantCreateSchema,
    current_user: str
) -> ParticipantResponseSchema:
    '''
        Controller to register a new participant. Per business rule, the first
        attendance is recorded automatically using the operator email.
    '''
    saved = create_participant(
        dynamodb_resource = dynamodb_resource,
        payload = payload.model_dump()
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
    item = get_participant_by_ci(dynamodb_resource = dynamodb_resource, ci = ci)
    return ParticipantResponseSchema(**item)


@handle_service_errors
def list_participants_controller(
    dynamodb_resource: ServiceResource,
    query_params: ParticipantQuerySchema
) -> ParticipantsListResponseSchema:
    '''
        Controller to retrieve a paginated list of participants with filters.
    '''
    response: Dict[str, Any] = list_participants(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params.model_dump(exclude_none = True)
    )
    return ParticipantsListResponseSchema(
        items = [ParticipantResponseSchema(**record) for record in response['items']],
        last_evaluated_key = response.get('last_evaluated_key')
    )
