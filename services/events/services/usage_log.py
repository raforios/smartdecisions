'''
    Business logic services for the Usage Log Module.
'''
from typing import Dict, Any
from boto3.resources.base import ServiceResource
from schemas.usage_log import UsageLogQuerySchema
from services.crud import (
    create_item,
    get_all_records_paginated
)
from services.utils import handle_service_errors, process_query_params
from services.logger_config import custom_logger as logger

from services.environment import load_and_validate_env_vars

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_USAGE': str
})


USAGE_LOG_TABLE_NAME = ENV_VARS['DYNAMODB_TABLE_NAME_USAGE']

@handle_service_errors
def create_usage_log(
    dynamodb_resource: ServiceResource,
    log_data: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Service to create a new usage log record in the database.
    '''
    logger.debug('Attempting to create a new usage log.')
    return create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = USAGE_LOG_TABLE_NAME,
        item_data = log_data
    )

@handle_service_errors
def get_usage_logs(
    dynamodb_resource: ServiceResource,
    query_params: UsageLogQuerySchema
) -> Dict[str, Any]:
    '''
        Retrieves a paginated list of usage logs with optional filters.
    '''
    message = 'Attempting to retrieve usage logs.'
    logger.info(message)
    processed_params = process_query_params(query_params)
    return get_all_records_paginated(
        dynamodb_resource = dynamodb_resource,
        table_name = USAGE_LOG_TABLE_NAME,
        query_params = processed_params
    )
