'''
    Audit and usage log controllers: each hands its log to `services/events.py`.
'''
from boto3.resources.base import ServiceResource

from schemas.audit import (
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
from services.events import AUDIT_LOG, USAGE_LOG, list_events, record_event
from services.utils import handle_service_errors


@handle_service_errors
def create_audit_record_controller(
    dynamodb_resource: ServiceResource,
    record_data: AuditRecordCreateSchema
) -> AuditRecordResponseSchema:
    '''
        Stores an audit record.
    '''
    return record_event(dynamodb_resource, AUDIT_LOG, record_data)


@handle_service_errors
def get_audit_records_controller(
    dynamodb_resource: ServiceResource,
    query_params: AuditRecordQuerySchema
) -> AuditRecordsPage:
    '''
        One page of the audit log.
    '''
    return list_events(dynamodb_resource, AUDIT_LOG, query_params)


@handle_service_errors
def create_usage_log_controller(
    dynamodb_resource: ServiceResource,
    log_data: UsageLogCreateSchema
) -> UsageLogResponseSchema:
    '''
        Stores a usage record.
    '''
    return record_event(dynamodb_resource, USAGE_LOG, log_data)


@handle_service_errors
def get_usage_logs_controller(
    dynamodb_resource: ServiceResource,
    query_params: UsageLogQuerySchema
) -> UsageLogsPage:
    '''
        One page of the usage log.
    '''
    return list_events(dynamodb_resource, USAGE_LOG, query_params)
