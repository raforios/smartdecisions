'''
    Reports controllers.
'''
from boto3.resources.base import ServiceResource

from schemas.reports import StatsGroupBy, StatsResponseSchema
from services.reports import get_participant_stats
from services.utils import handle_service_errors


@handle_service_errors
def get_participant_stats_controller(
    dynamodb_resource: ServiceResource,
    group_by: StatsGroupBy
) -> StatsResponseSchema:
    '''
        Controller to compute participants statistics grouped by department
        or company.
    '''
    payload = get_participant_stats(
        dynamodb_resource = dynamodb_resource,
        group_by = group_by
    )
    return StatsResponseSchema(**payload)
