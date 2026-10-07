'''
    Audit: routes handler
'''
from typing import Any
from fastapi import APIRouter, Depends, status
from boto3.resources.base import ServiceResource
from schemas.audit import (
    AuditRecordCreateSchema,
    AuditRecordResponseSchema,
    AuditRecordQuerySchema,
    READ_ROLES
)
from controllers.audit import (
    create_audit_record_controller,
    get_audit_records_controller
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user, require_roles

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
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    caller: str = Depends(get_current_user)
) -> AuditRecordResponseSchema:
    '''
        Endpoint to create a new audit record.
    '''
    message = f'Caller: {caller}. Received request to create a new audit record.'
    logger.info(message)
    return create_audit_record_controller(
        dynamodb_resource = dynamodb_resource,
        record_data = record_data
    )

@router.get(
    '/audit',
    response_model = dict[str, Any],
    status_code = status.HTTP_200_OK,
    summary = 'Get audit records with filters',
    description = '''
        Retrieves a paginated list of audit records with optional filters.
        
        The `last_evaluated_key` is a stringified JSON object that
        should be used for fetching the next page of results.
    '''
)
def get_audit_records_endpoint(
    current_user: str = Depends(require_roles(*READ_ROLES)),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    query_params: AuditRecordQuerySchema = Depends()
) -> dict[str, Any]:
    '''
        Endpoint to retrieve a paginated list of audit records with filters.
    '''
    message = f'User: {current_user}. Received request to retrieve audit records.'
    logger.info(message)
    return get_audit_records_controller(
        dynamodb_resource = dynamodb_resource,
        query_params = query_params
    )
