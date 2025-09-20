'''
    Business logic services for the Audit Module.
'''
from typing import Dict, Any
from boto3.resources.base import ServiceResource
from schemas.audit import AuditRecordQuerySchema
from services.crud import (
    create_item,
    get_all_records_paginated
)
from services.utils import handle_service_errors, process_query_params
from services.logger_config import custom_logger as logger

AUDIT_TABLE_NAME = 'audit_records'

@handle_service_errors
def create_audit_record(
    dynamodb_resource: ServiceResource,
    record_data: Dict[str, Any]
) -> Dict[str, Any]:
    '''
        Service to create a new audit record in the database.
    '''
    logger.debug('Attempting to create a new audit record.')
    return create_item(
        dynamodb_resource = dynamodb_resource,
        table_name = AUDIT_TABLE_NAME,
        item_data = record_data
    )

@handle_service_errors
def get_audit_records(
    dynamodb_resource: ServiceResource,
    query_params: AuditRecordQuerySchema
) -> Dict[str, Any]:
    '''
        Retrieves a paginated list of audit records with optional filters.
    '''
    message = 'Attempting to retrieve audit records.'
    logger.info(message)
    processed_params = process_query_params(query_params)
    return get_all_records_paginated(
        dynamodb_resource = dynamodb_resource,
        table_name = AUDIT_TABLE_NAME,
        query_params = processed_params
    )
