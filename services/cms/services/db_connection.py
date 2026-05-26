'''
    DynamoDB Connection for the CMS service.

    Boto3 reads AWS credentials and region from the environment as usual.
    When `DYNAMODB_ENDPOINT_URL` is set (local development pointing at
    DynamoDB Local on Docker) the resource is bound to that endpoint
    instead of the regional AWS one — same code path for both.
'''
from typing import Callable
import boto3
from boto3.resources.base import ServiceResource

from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger


ENV_VARS = load_and_validate_env_vars(
    env_vars = {
        'DYNAMODB_REGION': str,
    },
    optional_env_vars = {
        'DYNAMODB_ENDPOINT_URL': str,
    }
)

DYNAMODB_REGION = ENV_VARS['DYNAMODB_REGION']
DYNAMODB_ENDPOINT_URL = ENV_VARS.get('DYNAMODB_ENDPOINT_URL') or ''


def _build_resource() -> ServiceResource:
    '''
        Instantiates the DynamoDB resource using the configured region and
        — when present — the local endpoint URL.
    '''
    resource_args = {'region_name': DYNAMODB_REGION}
    if DYNAMODB_ENDPOINT_URL:
        resource_args['endpoint_url'] = DYNAMODB_ENDPOINT_URL
        message = f'DynamoDB bound to local endpoint {DYNAMODB_ENDPOINT_URL}.'
        logger.info(message)
    else:
        message = f'DynamoDB bound to AWS region {DYNAMODB_REGION}.'
        logger.info(message)
    return boto3.resource('dynamodb', **resource_args)


DYNAMODB_RESOURCE: ServiceResource = _build_resource()


def get_db_dependency() -> ServiceResource:
    '''
        FastAPI dependency returning the shared DynamoDB resource.
    '''
    return DYNAMODB_RESOURCE


# Backwards-compatible alias matching the shape of the previous SQL helper.
get_db_resource: Callable[[], ServiceResource] = get_db_dependency
