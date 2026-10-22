'''
    Recent activity controllers.
'''
from boto3.resources.base import ServiceResource
from schemas.activity import ActivityQuerySchema, ActivityResponseSchema
from services.activity import recent_activity
from services.utils import handle_service_errors


@handle_service_errors
def get_recent_activity_controller(
    dynamodb_resource: ServiceResource,
    query: ActivityQuerySchema
) -> ActivityResponseSchema:
    '''
        Controller returning the recent activity of the given services.
    '''
    return recent_activity(dynamodb_resource = dynamodb_resource, query = query)
