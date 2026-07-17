'''
    Participants: routes handler.
'''
from fastapi import APIRouter, Depends, Path, status
from boto3.resources.base import ServiceResource

from controllers.participants import (
    create_participant_controller,
    deactivate_participant_controller,
    get_participant_controller,
    list_participants_controller,
    replace_participant_controller,
    update_participant_controller
)
from schemas.enums import REGISTRATION_ROLES, VIEW_ROLES
from schemas.participants import (
    ParticipantCreateSchema,
    ParticipantDeactivateSchema,
    ParticipantQuerySchema,
    ParticipantReplaceSchema,
    ParticipantResponseSchema,
    ParticipantsListResponseSchema,
    ParticipantUpdateSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import require_roles

router = APIRouter(prefix = '/v1/mining-summit/participants', tags = ['Participants'])


@router.post(
    '',
    response_model = ParticipantResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register a new participant (on-the-fly)',
    description = (
        'Registers a participant at the accreditation desk and records the '
        'first attendance automatically. When an institution is supplied the '
        'creation is only allowed while it still has free cupo.'
    )
)
def create_participant_endpoint(
    payload: ParticipantCreateSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*REGISTRATION_ROLES))
):
    '''
        Endpoint to register a new participant on-the-fly.
    '''
    message = f'Registering new participant ci={payload.ci}'
    logger.info(message)
    return create_participant_controller(
        dynamodb_resource = dynamodb_resource,
        payload = payload,
        current_user = current_user
    )


@router.get(
    '',
    response_model = ParticipantsListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List participants',
    description = 'Returns a paginated list of participants with optional filters.'
)
def list_participants_endpoint(
    query_params: ParticipantQuerySchema = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*VIEW_ROLES))
):
    '''
        Endpoint to retrieve a paginated participants list.
    '''
    message = 'Retrieving participants list.'
    logger.info(message)
    return list_participants_controller(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params
    )


@router.get(
    '/{ci}',
    response_model = ParticipantResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get participant by CI',
    description = 'Retrieves a participant by Carnet de Identidad.'
)
def get_participant_endpoint(
    ci: str = Path(..., min_length = 4, max_length = 20),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*VIEW_ROLES))
):
    '''
        Endpoint to retrieve a single participant.
    '''
    message = f'Retrieving participant ci={ci}'
    logger.info(message)
    return get_participant_controller(
        dynamodb_resource = dynamodb_resource,
        ci = ci
    )


@router.patch(
    '/{ci}',
    response_model = ParticipantResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Edit a participant (accreditation)',
    description = (
        'Edits a participant so it can be fully accredited: department, contact, '
        'institution (validated against its cupo) and a thematic-axis seat '
        '(validated against the axis aula availability). Restricted to the '
        'registration desk (ADMIN/REGISTRATION).'
    )
)
def update_participant_endpoint(
    payload: ParticipantUpdateSchema,
    ci: str = Path(..., min_length = 4, max_length = 20),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*REGISTRATION_ROLES))
):
    '''
        Endpoint to edit a participant for accreditation.
    '''
    message = f'Editing participant ci={ci}'
    logger.info(message)
    return update_participant_controller(
        dynamodb_resource = dynamodb_resource,
        ci = ci,
        payload = payload
    )


@router.patch(
    '/{ci}/deactivate',
    response_model = ParticipantResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Deactivate (soft-delete) a participant',
    description = (
        'Marks an accredited participant as CANCELLED, freeing both the aula seat '
        'and the institution cupo. Data is retained; the operator who cancelled '
        'it is recorded. Restricted to the registration desk (ADMIN/REGISTRATION).'
    )
)
def deactivate_participant_endpoint(
    payload: ParticipantDeactivateSchema,
    ci: str = Path(..., min_length = 4, max_length = 20),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*REGISTRATION_ROLES))
):
    '''
        Endpoint to deactivate an accredited participant.
    '''
    message = f'Deactivating participant ci={ci} by {current_user}'
    logger.info(message)
    return deactivate_participant_controller(
        dynamodb_resource = dynamodb_resource,
        ci = ci,
        payload = payload,
        current_user = current_user
    )


@router.post(
    '/{ci}/replace',
    response_model = ParticipantResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Replace a participant with a substitute',
    description = (
        'Replaces an accredited participant with an institution-authorized '
        'substitute that inherits the outgoing seat (axis/mesa). The outgoing '
        'participant is marked REPLACED and the operator who authorized it is '
        'recorded. Restricted to the registration desk (ADMIN/REGISTRATION).'
    )
)
def replace_participant_endpoint(
    payload: ParticipantReplaceSchema,
    ci: str = Path(..., min_length = 4, max_length = 20),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*REGISTRATION_ROLES))
):
    '''
        Endpoint to replace an accredited participant.
    '''
    message = f'Replacing participant ci={ci} by {current_user}'
    logger.info(message)
    return replace_participant_controller(
        dynamodb_resource = dynamodb_resource,
        outgoing_ci = ci,
        payload = payload,
        current_user = current_user
    )
