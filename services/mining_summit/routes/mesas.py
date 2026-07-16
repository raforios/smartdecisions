'''
    Mesas and thematic axes: routes handler.
'''
from fastapi import APIRouter, Depends, Path, status
from boto3.resources.base import ServiceResource

from controllers.mesas import (
    create_mesa_controller,
    delete_mesa_controller,
    get_axis_availability_controller,
    list_axes_controller,
    list_mesas_controller,
    update_mesa_controller
)
from schemas.enums import VIEW_ROLES, RoleEnum
from schemas.mesas import (
    AvailabilityResponseSchema,
    AxesListResponseSchema,
    MesaCreateSchema,
    MesaQuerySchema,
    MesaResponseSchema,
    MesasListResponseSchema,
    MesaUpdateSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user, require_roles

router = APIRouter(prefix = '/v1/mining-summit', tags = ['Mesas'])


@router.get(
    '/mesas',
    response_model = MesasListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List working tables (mesas)',
    description = (
        'Returns the fixed campus rooms (aulas ≡ mesas) allocated to the '
        'thematic axes, with each mesa capacity and the total seat capacity. '
        'Supports an optional axis filter.'
    )
)
def list_mesas_endpoint(
    query_params: MesaQuerySchema = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve the mesas allocated to the thematic axes.
    '''
    message = 'Retrieving mesas allocation.'
    logger.info(message)
    return list_mesas_controller(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params
    )


@router.post(
    '/mesas',
    response_model = MesaResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Register a new aula',
    description = (
        'Registers a new aula (e.g. an extra classroom assigned to the summit) '
        'with its capacity and thematic axis. Restricted to ADMIN.'
    )
)
def create_mesa_endpoint(
    payload: MesaCreateSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value))
):
    '''
        Endpoint to register a new aula.
    '''
    message = f'Creating aula code={payload.code}'
    logger.info(message)
    return create_mesa_controller(
        dynamodb_resource = dynamodb_resource,
        payload = payload
    )


@router.patch(
    '/mesas/{code}',
    response_model = MesaResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update an aula (capacity / axis)',
    description = (
        'Updates the parametric attributes of an aula: its seat capacity and/or '
        'the thematic axis it is allocated to. Restricted to ADMIN.'
    )
)
def update_mesa_endpoint(
    payload: MesaUpdateSchema,
    code: str = Path(..., min_length = 1, max_length = 20),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value))
):
    '''
        Endpoint to update the capacity/axis of an aula.
    '''
    message = f'Updating aula code={code}'
    logger.info(message)
    return update_mesa_controller(
        dynamodb_resource = dynamodb_resource,
        code = code,
        payload = payload
    )


@router.delete(
    '/mesas/{code}',
    status_code = status.HTTP_204_NO_CONTENT,
    summary = 'Delete an aula',
    description = 'Removes an aula from the summit allocation. Restricted to ADMIN.'
)
def delete_mesa_endpoint(
    code: str = Path(..., min_length = 1, max_length = 20),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value))
):
    '''
        Endpoint to delete an aula.
    '''
    message = f'Deleting aula code={code}'
    logger.info(message)
    delete_mesa_controller(dynamodb_resource = dynamodb_resource, code = code)


@router.get(
    '/axes',
    response_model = AxesListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List thematic axes',
    description = (
        'Returns the six thematic axes (ejes) with their allocated mesa count '
        'and aggregated seat capacity, plus summit-wide totals.'
    )
)
def list_axes_endpoint(
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve the thematic axes with their mesa allocation.
    '''
    message = 'Retrieving thematic axes.'
    logger.info(message)
    return list_axes_controller(dynamodb_resource = dynamodb_resource)


@router.get(
    '/axes/availability',
    response_model = AvailabilityResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Seat availability per axis and aula',
    description = (
        'Returns, for each thematic axis and its aulas, the free seats '
        '(capacity minus active registrations). Guides the accreditation desk '
        'to pick an axis with room. Available to any authenticated operator.'
    )
)
def get_axis_availability_endpoint(
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*VIEW_ROLES))
):
    '''
        Endpoint to retrieve the seat availability per thematic axis and aula.
    '''
    message = 'Retrieving seat availability.'
    logger.info(message)
    return get_axis_availability_controller(dynamodb_resource = dynamodb_resource)
