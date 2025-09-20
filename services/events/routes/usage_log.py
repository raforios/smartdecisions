'''
    Usage Log: routes handler
'''
from typing import Dict, Any
from fastapi import APIRouter, Depends, status
from boto3.resources.base import ServiceResource
from schemas.usage_log import (
    UsageLogCreateSchema,
    UsageLogResponseSchema,
    UsageLogQuerySchema
)
from controllers.usage_log import (
    create_usage_log_controller,
    get_usage_logs_controller
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger

router = APIRouter(prefix='/v1/events', tags=['Events'])

@router.post(
    '/usage-log',
    response_model=UsageLogResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary='Create a new usage log',
    description='Creates a new log record for a given API call.'
)
def create_usage_log_endpoint(
    log_data: UsageLogCreateSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY)
):
    '''
        Endpoint to create a new usage log.
    '''
    message = 'Received request to create a new usage log.'
    logger.info(message)
    return create_usage_log_controller(
        dynamodb_resource=dynamodb_resource,
        log_data=log_data
    )

@router.get(
    '/usage-log',
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary='Get usage logs with filters',
    description='''
        Retrieves a paginated list of usage logs with optional filters.
        
        The `last_evaluated_key` is a stringified JSON object that
        should be used for fetching the next page of results.
    '''
)
def get_usage_logs_endpoint(
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    query_params: UsageLogQuerySchema = Depends()
):
    '''
        Endpoint to retrieve a paginated list of usage logs with filters.
    '''
    message = 'Received request to retrieve usage logs.'
    logger.info(message)
    return get_usage_logs_controller(
        dynamodb_resource=dynamodb_resource,
        query_params=query_params
    )
