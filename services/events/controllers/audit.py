'''
    Audit controllers.
'''
from sqlalchemy.orm import Session
from schemas.audit import AuditRecordCreateSchema, AuditRecordResponseSchema
from services.utils import handle_service_errors
from services.audit import create_audit_record

@handle_service_errors
def create_audit_record_controller(
    db: Session,
    record_data: AuditRecordCreateSchema
) -> AuditRecordResponseSchema:
    '''
        Controller to create a new audit record.
    '''
    audit_record = create_audit_record(db=db, record_data=record_data)
    return AuditRecordResponseSchema.model_validate(audit_record)
