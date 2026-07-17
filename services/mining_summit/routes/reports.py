'''
    Reports: routes handler.
'''
from fastapi import APIRouter, Depends, Query, Response, status
from boto3.resources.base import ServiceResource

from controllers.reports import (
    export_attendances_controller,
    export_participants_controller,
    get_lifecycle_report_controller,
    get_not_accredited_report_controller,
    get_participant_stats_controller,
    get_seat_distribution_controller
)
from schemas.enums import REPORT_ROLES
from schemas.reports import (
    LifecycleReportSchema,
    NotAccreditedReportSchema,
    SeatDistributionResponseSchema,
    StatsBasis,
    StatsGroupBy,
    StatsResponseSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import require_roles

router = APIRouter(prefix = '/v1/mining-summit/reports', tags = ['Reports'])

_XLSX_MEDIA_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _xlsx_response(content: bytes, filename: str) -> Response:
    '''Wraps workbook bytes in an attachment Response with the .xlsx headers.'''
    return Response(
        content = content,
        media_type = _XLSX_MEDIA_TYPE,
        headers = {'Content-Disposition': f'attachment; filename="{filename}"'}
    )


@router.get(
    '/stats',
    response_model = StatsResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Participant statistics',
    description = (
        'Returns aggregate counts and percentages of registered participants '
        'grouped by department. Restricted to ADMIN/REPORTS.'
    )
)
def get_participant_stats_endpoint(
    group_by: StatsGroupBy = Query(
        ...,
        description = 'Grouping dimension: department.'
    ),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*REPORT_ROLES))
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


@router.get(
    '/seat-distribution',
    response_model = SeatDistributionResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Seat distribution by axis and aula',
    description = (
        'Returns the head-count across thematic axes and their aulas. With '
        'basis=present only people with an attendance on the given date '
        '(default today) are counted; with basis=registered every active '
        'participant is counted. Restricted to ADMIN/REPORTS.'
    )
)
def get_seat_distribution_endpoint(
    basis: StatsBasis = Query(
        StatsBasis.PRESENT,
        description = 'Counting basis: present (by attendance) or registered.'
    ),
    date: str | None = Query(
        None,
        description = 'ISO date (YYYY-MM-DD) for the present basis; default today.'
    ),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*REPORT_ROLES))
):
    '''
        Endpoint to retrieve the seat distribution by axis and aula.
    '''
    message = f'Retrieving seat distribution basis={basis.value} date={date}'
    logger.info(message)
    return get_seat_distribution_controller(
        dynamodb_resource = dynamodb_resource,
        basis = basis,
        date = date
    )


@router.get(
    '/lifecycle',
    response_model = LifecycleReportSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Replaced / cancelled participants report',
    description = (
        'Returns the retired participants split into REPLACED and CANCELLED, '
        'each with the seat held, the reason/justification and the operator who '
        'performed it. Replacements include the substitute name and CI. '
        'Restricted to ADMIN/REPORTS.'
    )
)
def get_lifecycle_report_endpoint(
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*REPORT_ROLES))
):
    '''
        Endpoint to retrieve the replaced/cancelled participants report.
    '''
    message = 'Retrieving lifecycle (replaced/cancelled) report.'
    logger.info(message)
    return get_lifecycle_report_controller(dynamodb_resource = dynamodb_resource)


@router.get(
    '/not-accredited',
    response_model = NotAccreditedReportSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Not-accredited report (constancia)',
    description = (
        'Returns every spreadsheet row that could not be accredited across all '
        'ETL load batches, with its institution context and reason. Restricted '
        'to ADMIN/REPORTS.'
    )
)
def get_not_accredited_report_endpoint(
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*REPORT_ROLES))
):
    '''
        Endpoint to retrieve the not-accredited report.
    '''
    message = 'Retrieving not-accredited report.'
    logger.info(message)
    return get_not_accredited_report_controller(dynamodb_resource = dynamodb_resource)


@router.get(
    '/participants.xlsx',
    status_code = status.HTTP_200_OK,
    summary = 'Download participants report (Excel)',
    description = (
        'Downloads the participants report as an .xlsx file. By default only '
        'ACTIVE participants are included. Restricted to ADMIN/REPORTS.'
    )
)
def export_participants_endpoint(
    include_inactive: bool = Query(
        False, description = 'Include REPLACED/CANCELLED participants.'
    ),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*REPORT_ROLES))
):
    '''
        Endpoint to download the participants report in Excel format.
    '''
    message = 'Exporting participants report to Excel.'
    logger.info(message)
    content = export_participants_controller(
        dynamodb_resource = dynamodb_resource,
        include_inactive = include_inactive
    )
    return _xlsx_response(content, 'participantes.xlsx')


@router.get(
    '/attendances.xlsx',
    status_code = status.HTTP_200_OK,
    summary = 'Download attendances report (Excel)',
    description = (
        'Downloads the attendances report as an .xlsx file covering every '
        'recorded check-in. Restricted to ADMIN/REPORTS.'
    )
)
def export_attendances_endpoint(
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(*REPORT_ROLES))
):
    '''
        Endpoint to download the attendances report in Excel format.
    '''
    message = 'Exporting attendances report to Excel.'
    logger.info(message)
    content = export_attendances_controller(dynamodb_resource = dynamodb_resource)
    return _xlsx_response(content, 'asistencias.xlsx')
