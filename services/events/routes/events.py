'''
    Audit and usage logs: routes handler.
'''
from fastapi import APIRouter, Depends, status
from boto3.resources.base import ServiceResource

from core.db_connection import GET_DB_DEPENDENCY
from core.logger_config import custom_logger as logger
from core.security import get_current_user, require_roles
from controllers.events import (
    create_audit_record_controller,
    create_usage_log_controller,
    get_audit_records_controller,
    get_usage_logs_controller
)
from schemas.audit import (
    READ_ROLES,
    AuditRecordCreateSchema,
    AuditRecordQuerySchema,
    AuditRecordResponseSchema,
    AuditRecordsPage
)
from schemas.usage_log import (
    UsageLogCreateSchema,
    UsageLogQuerySchema,
    UsageLogResponseSchema,
    UsageLogsPage
)

router = APIRouter(prefix = '/v1/events', tags = ['Events'])

# How a listing pages, said once for both logs.
PAGING_NOTE = ('The `last_evaluated_key` is a stringified JSON object to send back '
               'for the next page.')


@router.post(
    '/audit',
    response_model = AuditRecordResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new audit record',
    description = 'Creates a new audit record for a given event.'
)
def create_audit_record_endpoint(
    record_data: AuditRecordCreateSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    caller: str = Depends(get_current_user)
) -> AuditRecordResponseSchema:
    '''
        Stores an audit record.
    '''
    message = f'Caller: {caller}. Received request to create a new audit record.'
    logger.info(message)
    return create_audit_record_controller(dynamodb_resource, record_data)


@router.get(
    '/audit',
    response_model = AuditRecordsPage,
    status_code = status.HTTP_200_OK,
    summary = 'Get audit records with filters',
    description = f'A paginated list of audit records with optional filters. {PAGING_NOTE}'
)
def get_audit_records_endpoint(
    current_user: str = Depends(require_roles(*READ_ROLES)),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    query_params: AuditRecordQuerySchema = Depends()
) -> AuditRecordsPage:
    '''
        One page of the audit log.
    '''
    message = f'User: {current_user}. Received request to retrieve audit records.'
    logger.info(message)
    return get_audit_records_controller(dynamodb_resource, query_params)


@router.post(
    '/usage-log',
    response_model = UsageLogResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new usage log',
    description = 'Creates a new log record for a given API call.'
)
def create_usage_log_endpoint(
    log_data: UsageLogCreateSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    caller: str = Depends(get_current_user)
) -> UsageLogResponseSchema:
    '''
        Stores a usage record.
    '''
    message = f'Caller: {caller}. Received request to create a new usage log.'
    logger.info(message)
    return create_usage_log_controller(dynamodb_resource, log_data)


@router.get(
    '/usage-log',
    response_model = UsageLogsPage,
    status_code = status.HTTP_200_OK,
    summary = 'Get usage logs with filters',
    description = f'A paginated list of usage logs with optional filters. {PAGING_NOTE}'
)
def get_usage_logs_endpoint(
    current_user: str = Depends(require_roles(*READ_ROLES)),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    query_params: UsageLogQuerySchema = Depends()
) -> UsageLogsPage:
    '''
        One page of the usage log.
    '''
    message = f'User: {current_user}. Received request to retrieve usage logs.'
    logger.info(message)
    return get_usage_logs_controller(dynamodb_resource, query_params)
