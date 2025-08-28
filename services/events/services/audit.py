'''
    Business logic services for the Audit Module.
'''
from sqlalchemy.orm import Session
from models.audit import AuditRecord
from schemas.audit import AuditRecordCreateSchema
from services.utils import handle_service_errors

@handle_service_errors
def create_audit_record(
    db: Session,
    record_data: AuditRecordCreateSchema
) -> AuditRecord:
    '''
        Service to create a new audit record in the database.
    '''
    db_record = AuditRecord(**record_data.model_dump())
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record
