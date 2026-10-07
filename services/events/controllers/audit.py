'''
    Audit controllers.
'''
from typing import Any
import uuid
from boto3.resources.base import ServiceResource
from schemas.audit import (
    AuditRecordCreateSchema,
    AuditRecordResponseSchema,
    AuditRecordQuerySchema
)
from services.payload_limits import cap_log_bodies, cap_many
from services.utils import get_current_time_gmt, handle_service_errors
from services.audit import create_audit_record, get_audit_records

@handle_service_errors
def create_audit_record_controller(
    dynamodb_resource: ServiceResource,
    record_data: AuditRecordCreateSchema
) -> AuditRecordResponseSchema:
    '''
        Controller to create a new audit record.
    '''
    # A unique id and the timestamp of the record.
    record_dict = record_data.model_dump()
    record_dict['id'] = str(uuid.uuid4())
    timestamp = get_current_time_gmt()
    record_dict['timestamp'] = timestamp.isoformat()
    # Full bodies are what inflates every record and makes any read of the
    # table expensive; they are capped before being persisted.
    record_dict = cap_log_bodies(record_dict)

    # Hands it to the service that stores it.
    audit_record = create_audit_record(
        dynamodb_resource = dynamodb_resource,
        record_data = record_dict
    )

    return AuditRecordResponseSchema(**audit_record)

@handle_service_errors
def get_audit_records_controller(
    dynamodb_resource: ServiceResource,
    query_params: AuditRecordQuerySchema
) -> dict[str, Any]:
    '''
        Controller to retrieve a paginated list of audit records with optional filters.
    '''
    response = get_audit_records(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params.model_dump(exclude_none=True)
    )

    # Records written before the cap still carry their full bodies: a page of
    # 100 went past the Lambda's 6 MB response limit.
    records = cap_many(response['items'])
    last_key = response['last_evaluated_key']

    return {
        'records': [AuditRecordResponseSchema(**record) for record in records],
        'last_evaluated_key': last_key
    }
