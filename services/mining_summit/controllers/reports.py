'''
    Reports controllers.
'''
from typing import Optional

from boto3.resources.base import ServiceResource

from schemas.reports import (
    NotAccreditedReportSchema,
    SeatDistributionResponseSchema,
    StatsBasis,
    StatsGroupBy,
    StatsResponseSchema
)
from services.exports import export_attendances_xlsx, export_participants_xlsx
from services.reports import (
    get_not_accredited_report,
    get_participant_stats,
    get_seat_distribution
)
from services.utils import handle_service_errors


@handle_service_errors
def get_participant_stats_controller(
    dynamodb_resource: ServiceResource,
    group_by: StatsGroupBy
) -> StatsResponseSchema:
    '''
        Controller to compute participants statistics grouped by department.
    '''
    payload = get_participant_stats(
        dynamodb_resource = dynamodb_resource,
        group_by = group_by
    )
    return StatsResponseSchema(**payload)


@handle_service_errors
def get_seat_distribution_controller(
    dynamodb_resource: ServiceResource,
    basis: StatsBasis,
    date: Optional[str] = None
) -> SeatDistributionResponseSchema:
    '''
        Controller to compute the distribution of people across thematic axes
        and aulas, either for those present on a date or all registered.
    '''
    payload = get_seat_distribution(
        dynamodb_resource = dynamodb_resource,
        basis = basis,
        date = date
    )
    return SeatDistributionResponseSchema(**payload)


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
