'''
    Route parameters — orchestration between the HTTP layer and the service.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.optimization_settings import RouteSettingsResponseSchema, RouteSettingsSchema
from services.optimization_settings import get_route_settings, save_route_settings
from services.utils import audit_event, handle_service_errors


@handle_service_errors('OPTIMIZATION')
async def get_route_settings_controller(
    dynamodb_resource: ServiceResource,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> RouteSettingsResponseSchema:
    '''
        The company's route parameters.
    '''
    return get_route_settings(dynamodb_resource, current_user)


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'RouteSettings', 'UPDATE')
async def save_route_settings_controller(
    dynamodb_resource: ServiceResource,
    settings: RouteSettingsSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> RouteSettingsResponseSchema:
    '''
        Saves the company's route parameters.
    '''
    return save_route_settings(dynamodb_resource, current_user, settings)
