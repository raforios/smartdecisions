'''
    Reports controllers.
'''
from boto3.resources.base import ServiceResource

from schemas.reports import (
    NotAccreditedReportSchema,
    StatsGroupBy,
    StatsResponseSchema
)
from services.exports import export_attendances_xlsx, export_participants_xlsx
from services.reports import get_not_accredited_report, get_participant_stats
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


@handle_service_errors
def get_not_accredited_report_controller(
    dynamodb_resource: ServiceResource
) -> NotAccreditedReportSchema:
    '''
        Controller to build the not-accredited report (constancia) from the ETL
        load batches. Restricted to ADMIN at the route layer.
    '''
    payload = get_not_accredited_report(dynamodb_resource = dynamodb_resource)
    return NotAccreditedReportSchema(**payload)


@handle_service_errors
def export_participants_controller(
    dynamodb_resource: ServiceResource,
    include_inactive: bool = False
) -> bytes:
    '''
        Controller returning the participants report as .xlsx bytes.
    '''
    return export_participants_xlsx(
        dynamodb_resource = dynamodb_resource,
        include_inactive = include_inactive
    )


@handle_service_errors
def export_attendances_controller(
    dynamodb_resource: ServiceResource
) -> bytes:
    '''
        Controller returning the attendances report as .xlsx bytes.
    '''
    return export_attendances_xlsx(dynamodb_resource = dynamodb_resource)
