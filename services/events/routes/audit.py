'''
    Audit: routes handler
'''
from typing import Dict, Any
from fastapi import APIRouter, Depends, status
from boto3.resources.base import ServiceResource
from schemas.audit import (
    AuditRecordCreateSchema,
    AuditRecordResponseSchema,
    AuditRecordQuerySchema
)
from controllers.audit import (
    create_audit_record_controller,
    get_audit_records_controller
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger

router = APIRouter(prefix='/v1/events', tags=['Events'])

@router.post(
    '/audit',
    response_model = AuditRecordResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new audit record',
    description = 'Creates a new audit record for a given event.'
)
def create_audit_record_endpoint(
    record_data: AuditRecordCreateSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY)
):
    '''
        Endpoint to create a new audit record.
    '''
    message = 'Received request to create a new audit record.'
    logger.info(message)
    return create_audit_record_controller(
        dynamodb_resource = dynamodb_resource,
        record_data = record_data
    )

@router.get(
    '/audit',
    response_model = Dict[str, Any],
    status_code = status.HTTP_200_OK,
    summary = 'Get audit records with filters',
    description = '''
        Retrieves a paginated list of audit records with optional filters.
        
        The `last_evaluated_key` is a stringified JSON object that
        should be used for fetching the next page of results.
    '''
)
def get_audit_records_endpoint(
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    query_params: AuditRecordQuerySchema = Depends()
):
    '''
        Endpoint to retrieve a paginated list of audit records with filters.
    '''
    message = 'Received request to retrieve audit records.'
    logger.info(message)
    return get_audit_records_controller(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params
    )
