'''
    Client master — HTTP layer.

    The API door of the master: the owner's ERP pushes who its clients are and
    where they stand, once, and every later upload stops having to repeat it.
'''
from typing import Optional

from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path as PathParam, Query, Request, status

from controllers.clients import (
    get_client_controller,
    register_field_client_controller,
    list_clients_controller,
    update_client_controller,
    upsert_clients_controller
)
from routes.common import get_caller
from schemas.clients import (
    CallerClaims,
    ClientBulkUpsertSchema,
    FieldClientSchema,
    ClientListResponseSchema,
    ClientResponseSchema,
    ClientUpdateSchema,
    ClientUpsertResultSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner

router = APIRouter(prefix = '/v1/ingest/clients', tags = ['Client master'])

_CLIENT_ID = PathParam(..., min_length = 1, max_length = 64)
_SELLER = Query(None, max_length = 128, description = 'Narrow to one portfolio.')


@router.post(
    '',
    response_model = ClientUpsertResultSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Push the client master from an ERP',
    description = (
        'Creates the clients it does not know and completes the fields it has '
        'empty; it never overwrites a value already stored, so the call is safe '
        'to repeat every night. Correcting a stored value is PATCH, a separate '
        'and explicit act.'
    )
)
async def upsert_clients_endpoint(
    request: Request,
    payload: ClientBulkUpsertSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ClientUpsertResultSchema:
    '''
        Endpoint to feed the client master from the owner's own system.
    '''
    message = f'User: {current_user}. Feeding {len(payload.clients)} client(s) into the master.'
    logger.info(message)
    return await upsert_clients_controller(
        dynamodb_resource = dynamodb_resource,
        payload = payload,
        current_user = current_user,
        request = request
    )


@router.post(
    '/field',
    response_model = ClientResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register a client from the street',
    description = (
        'The third door of the master. A seller reached an address the sales '
        'file never mentioned; registering it here is what turns an off-plan '
        'stop into something reusable. Coordinates are required —this record '
        'is created standing at the shop— and a client already known is not '
        'overwritten: only its empty fields are filled in, so two sellers at '
        'the same door do not create two clients.'
    )
)
async def register_field_client_endpoint(
    request: Request,
    client: FieldClientSchema,
    caller: CallerClaims = Depends(get_caller),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ClientResponseSchema:
    '''
        Endpoint to register a client from the field.
    '''
    message = f'User: {current_user}. {caller.email} registers client "{client.name}".'
    logger.info(message)
    return await register_field_client_controller(
        dynamodb_resource = dynamodb_resource,
        client = client,
        current_user = current_user,
        seller = caller.email,
        request = request
    )


@router.get(
    '',
    response_model = ClientListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The clients of the account',
    description = 'Reports how many can be placed on a map, which is what '
                  'decides whether Routes has anything to draw.'
)
async def list_clients_endpoint(
    request: Request,
    seller: Optional[str] = _SELLER,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ClientListResponseSchema:
    '''
        Endpoint listing the owner's client master.
    '''
    message = f'User: {current_user}. Reading the client master (seller={seller}).'
    logger.info(message)
    return await list_clients_controller(
        dynamodb_resource = dynamodb_resource,
        seller = seller,
        current_user = current_user,
        request = request
    )


@router.get(
    '/{client_id}',
    response_model = ClientResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'One client of the account'
)
async def get_client_endpoint(
    request: Request,
    client_id: str = _CLIENT_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ClientResponseSchema:
    '''
        Endpoint reading one client of the master.
    '''
    message = f'User: {current_user}. Reading client {client_id}.'
    logger.info(message)
    return await get_client_controller(
        dynamodb_resource = dynamodb_resource,
        client_id = client_id,
        current_user = current_user,
        request = request
    )


@router.patch(
    '/{client_id}',
    response_model = ClientResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Correct a client',
    description = 'Overwrites the attributes it names, and only those. Unlike a '
                  'load, this is somebody deciding what is stored is wrong.'
)
async def update_client_endpoint(
    request: Request,
    changes: ClientUpdateSchema,
    client_id: str = _CLIENT_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ClientResponseSchema:
    '''
        Endpoint correcting one client of the master.
    '''
    message = f'User: {current_user}. Correcting client {client_id}.'
    logger.info(message)
    return await update_client_controller(
        dynamodb_resource = dynamodb_resource,
        client_id = client_id,
        changes = changes,
        current_user = current_user,
        request = request
    )
