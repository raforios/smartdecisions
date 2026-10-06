'''
    Route parameters of a company: read and save.
'''
from boto3.resources.base import ServiceResource

from models.optimization_settings import RouteSettingsItem
from schemas.optimization_settings import RouteSettingsResponseSchema, RouteSettingsSchema
from services.common import from_dynamo, now_iso, to_dynamo
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

_SETTINGS = load_and_validate_env_vars({'DYNAMODB_TABLE_NAME_OPTIMIZATION_SETTINGS': str})
SETTINGS_TABLE = _SETTINGS['DYNAMODB_TABLE_NAME_OPTIMIZATION_SETTINGS']


def get_route_settings(
    dynamodb_resource: ServiceResource,
    owner_email: str
) -> RouteSettingsResponseSchema:
    '''
        The company's route parameters; empty when it never set any.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.

        Returns:
            RouteSettingsResponseSchema: The parameters.
    '''
    stored = from_dynamo(dynamodb_resource.Table(SETTINGS_TABLE).get_item(
        Key = {'owner_email': owner_email}
    ).get('Item')) or {}
    return RouteSettingsResponseSchema(base_point = stored.get('base_point'),
                                       updated_at = stored.get('updated_at'))


def save_route_settings(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    settings: RouteSettingsSchema
) -> RouteSettingsResponseSchema:
    '''
        Creates or replaces the company's route parameters.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner_email (str): Authenticated account.
            settings (RouteSettingsSchema): What was edited.

        Returns:
            RouteSettingsResponseSchema: What was stored.
    '''
    item: RouteSettingsItem = {
        'owner_email': owner_email,
        'base_point': settings.base_point.model_dump() if settings.base_point else None,
        'updated_at': now_iso()
    }
    dynamodb_resource.Table(SETTINGS_TABLE).put_item(
        Item = to_dynamo({key: value for key, value in item.items() if value is not None})
    )
    message = f'Route settings stored for {owner_email}.'
    logger.info(message)
    return get_route_settings(dynamodb_resource, owner_email)
