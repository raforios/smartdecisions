'''
    Usage Log controllers.
'''
from typing import Any
import uuid
from boto3.resources.base import ServiceResource
from schemas.usage_log import (
    UsageLogCreateSchema,
    UsageLogResponseSchema,
    UsageLogQuerySchema
)
from services.payload_limits import cap_log_bodies, cap_many
from services.utils import get_current_time_gmt, handle_service_errors
from services.usage_log import create_usage_log, get_usage_logs

@handle_service_errors
def create_usage_log_controller(
    dynamodb_resource: ServiceResource,
    log_data: UsageLogCreateSchema
) -> UsageLogResponseSchema:
    '''
        Controller to create a new usage log record.
    '''
    # A unique id and the timestamp of the record.
    log_dict = log_data.model_dump()
    log_dict['id'] = str(uuid.uuid4())
    timestamp = get_current_time_gmt()
    log_dict['timestamp'] = timestamp.isoformat()
    # Full bodies are what inflates every record and makes any read of the
    # table expensive; they are capped before being persisted.
    log_dict = cap_log_bodies(log_dict)

    # Hands it to the service that stores it.
    usage_log = create_usage_log(
        dynamodb_resource = dynamodb_resource,
        log_data = log_dict
    )

    return UsageLogResponseSchema(**usage_log)

@handle_service_errors
def get_usage_logs_controller(
    dynamodb_resource: ServiceResource,
    query_params: UsageLogQuerySchema
) -> dict[str, Any]:
    '''
        Controller to retrieve a paginated list of usage logs with optional filters.
    '''
    response = get_usage_logs(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params.model_dump(exclude_none = True)
    )

    # Records written before the cap still carry their full bodies: a page of
    # 100 went past the Lambda's 6 MB response limit.
    records = cap_many(response['items'])
    last_key = response['last_evaluated_key']

    return {
        'records': [UsageLogResponseSchema(**record) for record in records],
        'last_evaluated_key': last_key
    }
