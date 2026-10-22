'''
    Recent activity: routes handler (ADMIN only).
'''
from fastapi import APIRouter, Depends, status
from boto3.resources.base import ServiceResource
from schemas.activity import ActivityQuerySchema, ActivityResponseSchema
from schemas.audit import READ_ROLES
from controllers.activity import get_recent_activity_controller
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import require_roles

router = APIRouter(prefix = '/v1/events', tags = ['Events'])


@router.get(
    '/activity',
    response_model = ActivityResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Recent activity of the given services (ADMIN)',
    description = '''
        Calls per service and hour over the last hours, answered and failed,
        with the latest failed calls and the latest audited changes. Read
        through the microservice + date index, without the bodies.
    '''
)
def get_recent_activity_endpoint(
    current_user: str = Depends(require_roles(*READ_ROLES)),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    query: ActivityQuerySchema = Depends()
) -> ActivityResponseSchema:
    '''
        Endpoint returning the recent activity for the ADMIN's dashboard.
    '''
    message = f'User: {current_user}. Requested the activity of the last {query.hours} h.'
    logger.info(message)
    return get_recent_activity_controller(
        dynamodb_resource = dynamodb_resource,
        query = query
    )
