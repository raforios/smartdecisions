'''
    Reports: routes handler.
'''
from fastapi import APIRouter, Depends, Query, status
from boto3.resources.base import ServiceResource

from controllers.reports import get_participant_stats_controller
from schemas.reports import StatsGroupBy, StatsResponseSchema
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/mining-summit/reports', tags = ['Reports'])


@router.get(
    '/stats',
    response_model = StatsResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Participant statistics',
    description = (
        'Returns aggregate counts and percentages of registered participants '
        'grouped by department or company. Used to feed the chart in the '
        'Vanilla JS frontend.'
    )
)
def get_participant_stats_endpoint(
    group_by: StatsGroupBy = Query(
        ...,
        description = 'Grouping dimension: department or company.'
    ),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve aggregated participant statistics.
    '''
    message = f'Retrieving participants stats group_by={group_by.value}'
    logger.info(message)
    return get_participant_stats_controller(
        dynamodb_resource = dynamodb_resource,
        group_by = group_by
    )
