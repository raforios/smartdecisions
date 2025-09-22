'''
    Business logic services for the Usage Log Module.
'''
from sqlalchemy.orm import Session
from models.usage_log import UsageLog
from schemas.usage_log import UsageLogCreateSchema
from services.utils import handle_service_errors

@handle_service_errors
def create_usage_log(
    db: Session,
    log_data: UsageLogCreateSchema
) -> UsageLog:
    '''
        Service to create a new usage log record in the database.
    '''
    db_log = UsageLog(**log_data.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log
