'''
    Usage Log controllers.
'''
from sqlalchemy.orm import Session
from schemas.usage_log import UsageLogCreateSchema, UsageLogResponseSchema
from services.utils import handle_service_errors
from services.usage_log import create_usage_log

@handle_service_errors
def create_usage_log_controller(
    db: Session,
    log_data: UsageLogCreateSchema
) -> UsageLogResponseSchema:
    '''
        Controller to create a new usage log.
    '''
    usage_log = create_usage_log(db = db, log_data = log_data)
    return UsageLogResponseSchema.model_validate(usage_log)
