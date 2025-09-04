'''
    Usage Log: routes handler
'''
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from schemas.usage_log import UsageLogCreateSchema, UsageLogResponseSchema
from controllers.usage_log import create_usage_log_controller
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger

router = APIRouter(prefix = '/v1/events', tags=['Events'])

@router.post(
    '/usage-log',
    response_model = UsageLogResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new usage log',
    description = 'Creates a new log record for a given API call.'
)
def create_usage_log_endpoint(
    log_data: UsageLogCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY)
):
    '''
        Endpoint to create a new usage log.
    '''
    message = 'Received request to create a new usage log.'
    logger.info(message)
    return create_usage_log_controller(db = db, log_data = log_data)
