'''
    Audit controllers.
'''
from typing import Dict, Any
import uuid
from boto3.resources.base import ServiceResource
from schemas.audit import (
    AuditRecordCreateSchema,
    AuditRecordResponseSchema,
    AuditRecordQuerySchema
)
from services.payload_limits import cap_log_bodies
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
    # Genera un ID único y la marca de tiempo para el registro
    record_dict = record_data.model_dump()
    record_dict['id'] = str(uuid.uuid4())
    timestamp = get_current_time_gmt()
    record_dict['timestamp'] = timestamp.isoformat()
    # Los bodies completos son lo que infla cada registro y encarece
    # toda lectura de la tabla; se acotan antes de persistir.
    record_dict = cap_log_bodies(record_dict)

    # Llama al servicio para crear el registro
    audit_record = create_audit_record(
        dynamodb_resource = dynamodb_resource,
        record_data = record_dict
    )

    return AuditRecordResponseSchema(**audit_record)

@handle_service_errors
def get_audit_records_controller(
    dynamodb_resource: ServiceResource,
    query_params: AuditRecordQuerySchema
) -> Dict[str, Any]:
    '''
        Controller to retrieve a paginated list of audit records with optional filters.
    '''
    response = get_audit_records(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params.model_dump(exclude_none=True)
    )

    records = response['items']
    last_key = response['last_evaluated_key']

    return {
        'records': [AuditRecordResponseSchema(**record) for record in records],
        'last_evaluated_key': last_key
    }
