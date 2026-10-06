'''
    Route parameters — HTTP layer. Anybody of the company reads them (the
    phone needs the base point); only management changes them.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Request

from controllers.optimization_settings import (
    get_route_settings_controller,
    save_route_settings_controller
)
from schemas.localization import FIELD_ROLES, MANAGEMENT_ROLES
from schemas.optimization_settings import RouteSettingsResponseSchema, RouteSettingsSchema
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import require_roles

router = APIRouter(prefix = '/v1/optimization', tags = ['Route settings'])


@router.get('/settings', response_model = RouteSettingsResponseSchema)
async def get_route_settings_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*FIELD_ROLES))
) -> RouteSettingsResponseSchema:
    '''
        Endpoint for the company's route parameters.
    '''
    return await get_route_settings_controller(
        dynamodb_resource = dynamodb_resource, current_user = current_user, request = request
    )


@router.put('/settings', response_model = RouteSettingsResponseSchema)
async def save_route_settings_endpoint(
    request: Request,
    settings: RouteSettingsSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> RouteSettingsResponseSchema:
    '''
        Endpoint to save the company's route parameters.
    '''
    message = f'User: {current_user}. Saving route settings.'
    logger.info(message)
    return await save_route_settings_controller(
        dynamodb_resource = dynamodb_resource, settings = settings,
        current_user = current_user, request = request
    )
