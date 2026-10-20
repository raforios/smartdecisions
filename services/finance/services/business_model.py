'''
    The client's business model: one per client, written by its MANAGER and
    read by the portal, which hands it to the AI next to the figures.

    FINANCE only keeps it. The comparison with the results is the AI's job
    (CLAUDE.md §6): nothing here interprets the answers.
'''
from boto3.resources.base import ServiceResource

from models.finance import BusinessModelItem
from schemas.business_model import BusinessModelResponseSchema, BusinessModelSchema
from services.environment import load_and_validate_env_vars
from services.finance_utils import to_dynamo
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_FINANCE_BUSINESS_MODELS': str,
})
BUSINESS_MODELS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_FINANCE_BUSINESS_MODELS']


def get_business_model(
    dynamodb_resource: ServiceResource,
    client: str
) -> BusinessModelResponseSchema:
    '''
        The business model the client stored; empty while it has none.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            client (str): The owner.

        Returns:
            BusinessModelResponseSchema: The model and when it last changed.
    '''
    item = dynamodb_resource.Table(BUSINESS_MODELS_TABLE).get_item(
        Key = {'client': client}
    ).get('Item')
    if not item:
        return BusinessModelResponseSchema(business_model = None)
    return BusinessModelResponseSchema(
        business_model = BusinessModelSchema.model_validate(item),
        updated_at = item['updated_at']
    )


def set_business_model(
    dynamodb_resource: ServiceResource,
    owner: tuple[str, str],
    business_model: BusinessModelSchema
) -> BusinessModelResponseSchema:
    '''
        Replaces the client's business model with the one just saved.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (tuple[str, str]): The client and the user saving it.
            business_model (BusinessModelSchema): The form as filled.

        Returns:
            BusinessModelResponseSchema: The model after the change.
    '''
    client, user = owner
    now = get_current_time_gmt().isoformat()
    item: BusinessModelItem = {
        **business_model.model_dump(exclude_none = True),
        'client': client, 'user': user, 'updated_at': now
    }
    dynamodb_resource.Table(BUSINESS_MODELS_TABLE).put_item(Item = to_dynamo(dict(item)))
    message = f'{client} saved its business model ({user}).'
    logger.info(message)
    return BusinessModelResponseSchema(business_model = business_model, updated_at = now)
