'''
    Usage Log controllers.
'''
from typing import Dict, Any
import uuid
import datetime
from boto3.resources.base import ServiceResource
from schemas.usage_log import (
    UsageLogCreateSchema,
    UsageLogResponseSchema,
    UsageLogQuerySchema
)
from services.utils import handle_service_errors
from services.usage_log import create_usage_log, get_usage_logs

@handle_service_errors
def create_usage_log_controller(
    dynamodb_resource: ServiceResource,
    log_data: UsageLogCreateSchema
) -> UsageLogResponseSchema:
    '''
        Controller to create a new usage log record.
    '''
    # Genera un ID único y la marca de tiempo para el registro
    log_dict = log_data.model_dump()
    log_dict['id'] = str(uuid.uuid4())
    log_dict['timestamp'] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Llama al servicio para crear el registro
    usage_log = create_usage_log(
        dynamodb_resource = dynamodb_resource,
        log_data = log_dict
    )

    return UsageLogResponseSchema(**usage_log)

@handle_service_errors
def get_usage_logs_controller(
    dynamodb_resource: ServiceResource,
    query_params: UsageLogQuerySchema
) -> Dict[str, Any]:
    '''
        Controller to retrieve a paginated list of usage logs with optional filters.
    '''
    response = get_usage_logs(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params.model_dump(exclude_none = True)
    )

    records = response['items']
    last_key = response['last_evaluated_key']

    return {
        'records': [UsageLogResponseSchema(**record) for record in records],
        'last_evaluated_key': last_key
    }
