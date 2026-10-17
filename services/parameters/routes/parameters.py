'''
    Parameters — HTTP layer.

    Any authenticated caller reads a scope (a service forwards its caller's
    token); only an ADMIN of BearSoft changes a value.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path as PathParam, Request, status

from controllers.parameters import (
    all_parameters_controller,
    delete_parameter_controller,
    scope_parameters_controller,
    set_parameter_controller
)
from schemas.parameters import (
    ParameterListResponseSchema,
    ParameterResponseSchema,
    ParameterSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner, require_roles

router = APIRouter(prefix = '/v1/parameters', tags = ['Parameters'])

# A FastAPI endpoint declares its dependencies as parameters —resource, caller,
# body— so the five-argument budget does not describe it.
# pylint: disable=too-many-arguments, too-many-positional-arguments

# What is global is changed only by BearSoft.
EDITORS = ('ADMIN',)

_SCOPE = PathParam(..., min_length = 1, max_length = 40, pattern = r'^[a-z_]+$',
                   description = '`global` or the service that reads it.')
_CODE = PathParam(..., min_length = 1, max_length = 60, pattern = r'^[A-Z0-9_]+$')


@router.get(
    '',
    response_model = ParameterListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Every parameter (ADMIN)'
)
async def all_parameters_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*EDITORS))
) -> ParameterListResponseSchema:
    '''
        Endpoint listing every parameter.
    '''
    message = f'User: {current_user}. Reading every parameter.'
    logger.info(message)
    return await all_parameters_controller(
        dynamodb_resource = dynamodb_resource,
        current_user = current_user,
        request = request
    )


@router.get(
    '/{scope}',
    response_model = ParameterListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The parameters of one scope',
    description = 'What a service reads: its own scope, and `global`.'
)
async def scope_parameters_endpoint(
    request: Request,
    scope: str = _SCOPE,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ParameterListResponseSchema:
    '''
        Endpoint listing a scope.
    '''
    message = f'User: {current_user}. Reading the parameters of {scope}.'
    logger.info(message)
    return await scope_parameters_controller(
        dynamodb_resource = dynamodb_resource,
        scope = scope,
        current_user = current_user,
        request = request
    )


@router.put(
    '/{scope}/{code}',
    response_model = ParameterResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Create or change a parameter (ADMIN)',
    description = 'The new value is read by its service within its cache time; no release.'
)
async def set_parameter_endpoint(
    request: Request,
    parameter: ParameterSchema,
    scope: str = _SCOPE,
    code: str = _CODE,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*EDITORS))
) -> ParameterResponseSchema:
    '''
        Endpoint setting a parameter.
    '''
    message = f'User: {current_user}. Setting {scope}.{code}.'
    logger.info(message)
    return await set_parameter_controller(
        dynamodb_resource = dynamodb_resource,
        key = (scope, code),
        parameter = parameter,
        current_user = current_user,
        request = request
    )


@router.delete(
    '/{scope}/{code}',
    response_model = ParameterResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Remove a parameter (ADMIN)'
)
async def delete_parameter_endpoint(
    request: Request,
    scope: str = _SCOPE,
    code: str = _CODE,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*EDITORS))
) -> ParameterResponseSchema:
    '''
        Endpoint removing a parameter.
    '''
    message = f'User: {current_user}. Removing {scope}.{code}.'
    logger.info(message)
    return await delete_parameter_controller(
        dynamodb_resource = dynamodb_resource,
        key = (scope, code),
        current_user = current_user,
        request = request
    )
