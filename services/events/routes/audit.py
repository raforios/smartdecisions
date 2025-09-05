'''
    Audit: routes handler
'''
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from schemas.audit import AuditRecordCreateSchema, AuditRecordResponseSchema
from controllers.audit import create_audit_record_controller
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger

router = APIRouter(prefix = '/v1/events', tags = ['Events'])

@router.post(
    '/audit',
    response_model = AuditRecordResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new audit record',
    description = 'Creates a new audit record for a given event.'
)
def create_audit_record_endpoint(
    record_data: AuditRecordCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
):
    '''
        Endpoint to create a new audit record.
    '''
    message = 'Received request to create a new audit record.'
    logger.info(message)
    return create_audit_record_controller(db = db, record_data = record_data)
