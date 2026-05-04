'''
    Participants: routes handler.
'''
from fastapi import APIRouter, Depends, Path, status
from boto3.resources.base import ServiceResource

from controllers.participants import (
    create_participant_controller,
    get_participant_controller,
    list_participants_controller
)
from schemas.participants import (
    ParticipantCreateSchema,
    ParticipantQuerySchema,
    ParticipantResponseSchema,
    ParticipantsListResponseSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/mining-summit/participants', tags = ['Participants'])


@router.post(
    '',
    response_model = ParticipantResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register a new participant',
    description = (
        'Registers a participant and automatically records the first attendance '
        'using the current Bolivia date.'
    )
)
def create_participant_endpoint(
    payload: ParticipantCreateSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to register a new participant.
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
    _: str = Depends(get_current_user)
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
    _: str = Depends(get_current_user)
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
