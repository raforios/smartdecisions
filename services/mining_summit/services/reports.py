'''
    Business logic for the Reports module of the Mining Summit service.

    Computes aggregate statistics over the persons table (by department) and the
    distribution of people across thematic axes and aulas (from registrations).
'''
from typing import Any, Dict, List, Optional
from boto3.resources.base import ServiceResource

from schemas.reports import StatsBasis, StatsGroupBy
from services.crud import scan_all_items
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger
from services.mesas import list_mesas
from services.participants import scan_all_participants
from services.registration import is_active, scan_all_registrations
from services.utils import get_current_time_gmt, handle_service_errors

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_LOAD_BATCHES': str,
    'DYNAMODB_TABLE_NAME_ATTENDANCES': str
})

LOAD_BATCHES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_LOAD_BATCHES']
ATTENDANCES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_ATTENDANCES']

_UNDEFINED_LABEL = 'Sin especificar'


def _aggregate_by_dimension(
    items: List[Dict[str, Any]],
    dimension: str
) -> List[Dict[str, Any]]:
    '''
        Aggregates a list of participants by the given dimension. Missing or
        empty values are bucketed under the 'Sin especificar' label so the
        report stays meaningful even with optional fields.
    '''
    counts: Dict[str, int] = {}
    for item in items:
        raw = item.get(dimension)
        label = raw.strip() if isinstance(raw, str) and raw.strip() else _UNDEFINED_LABEL
        counts[label] = counts.get(label, 0) + 1

    total = sum(counts.values())
    if total == 0:
        return []

    aggregated = [
        {
            'label': label,
            'count': count,
            'percentage': round((count / total) * 100, 2)
        }
        for label, count in counts.items()
    ]
    aggregated.sort(key = lambda entry: entry['count'], reverse = True)
    return aggregated


@handle_service_errors
def get_participant_stats(
    dynamodb_resource: ServiceResource,
    group_by: StatsGroupBy
) -> Dict[str, Any]:
    '''
        Builds the statistical report for participants grouped by the chosen
        dimension. Returns the total along with per-bucket counts and shares.
    '''
    message = f'Building participants statistics report group_by={group_by.value}'
    logger.info(message)

    items = scan_all_participants(dynamodb_resource = dynamodb_resource)
    aggregated = _aggregate_by_dimension(items, group_by.value)
    return {
        'group_by': group_by,
        'total': len(items),
        'items': aggregated
    }


def _present_cis_on_date(
    dynamodb_resource: ServiceResource,
    date: str
) -> set[str]:
    '''
        Returns the set of participant CIs with a recorded attendance on the
        given date. Attendances only store ci/attendance_date, so the axis/aula
        breakdown is resolved against the participants table by the caller.
    '''
    attendances = scan_all_items(dynamodb_resource, ATTENDANCES_TABLE)
    return {
        att['ci'] for att in attendances
        if att.get('attendance_date') == date and att.get('ci')
    }


def _build_axis_skeleton(aulas: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    '''
        Builds the per-axis distribution skeleton from the aulas reference set,
        pre-seeding every axis and aula with a zero count and its capacity, so
        empty axes/aulas still appear in the report.
    '''
    skeleton: Dict[str, Dict[str, Any]] = {}
    for aula in aulas:
        axis = skeleton.setdefault(aula['axis'], {
            'axis': aula['axis'],
            'number': aula['axis_number'],
            'label': aula['axis_label'],
            'capacity': 0,
            'count': 0,
            'aulas': {}
        })
        axis['capacity'] += aula['capacity']
        axis['aulas'][aula['code']] = {
            'mesa_code': aula['code'],
            'capacity': aula['capacity'],
            'count': 0
        }
    return skeleton


@handle_service_errors
def get_seat_distribution(
    dynamodb_resource: ServiceResource,
    basis: StatsBasis,
    date: Optional[str] = None
) -> Dict[str, Any]:
    '''
        Builds the distribution of people across thematic axes and their aulas.

        With basis PRESENT, only participants with an attendance on `date`
        (defaulting to today) are counted; with basis REGISTERED, every active
        participant is counted regardless of date. People without an assigned
        axis/aula are reported under the 'unassigned' total.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            basis (StatsBasis): PRESENT (by attendance) or REGISTERED.
            date (Optional[str]): ISO date for the PRESENT basis; ignored for
                REGISTERED. Defaults to today when omitted.

        Returns:
            Dict[str, Any]: basis, date, total, unassigned and the per-axis
                (and per-aula) counts.
    '''
    resolved_date = date or get_current_time_gmt().date().isoformat()
    message = f'Building seat distribution basis={basis.value} date={resolved_date}'
    logger.info(message)

    # Active registrations carry the axis/mesa seat; join by ci.
    registrations = {
        registration['ci']: registration
        for registration in scan_all_registrations(dynamodb_resource)
        if is_active(registration)
    }
    if basis == StatsBasis.PRESENT:
        # People present on the date (attendances); walk-ins without an active
        # registration are counted in the total but reported as unassigned.
        population = _present_cis_on_date(dynamodb_resource, resolved_date)
    else:
        population = set(registrations)

    skeleton = _build_axis_skeleton(list_mesas(dynamodb_resource))
    unassigned = 0
    for ci in population:
        registration = registrations.get(ci)
        mesa_code = registration.get('mesa_code') if registration else None
        axis = skeleton.get(registration.get('axis')) if registration else None
        if not axis or not mesa_code or mesa_code not in axis['aulas']:
            unassigned += 1
            continue
        axis['count'] += 1
        axis['aulas'][mesa_code]['count'] += 1

    axes = sorted(skeleton.values(), key = lambda entry: entry['number'])
    for axis in axes:
        axis['aulas'] = sorted(
            axis['aulas'].values(), key = lambda aula: aula['mesa_code']
        )
    return {
        'basis': basis,
        'date': resolved_date if basis == StatsBasis.PRESENT else None,
        'total': len(population),
        'unassigned': unassigned,
        'axes': axes
    }


@handle_service_errors
def get_not_accredited_report(
    dynamodb_resource: ServiceResource
) -> Dict[str, Any]:
    '''
        Builds the not-accredited report (constancia): every spreadsheet row
        that could not be accredited across all ETL load batches, flattened with
        its institution context.

        Returns:
            Dict[str, Any]: total count and the per-row not-accredited entries.
    '''
    message = 'Building not-accredited report from load batches.'
    logger.info(message)

    batches = scan_all_items(dynamodb_resource, LOAD_BATCHES_TABLE)
    entries: List[Dict[str, Any]] = []
    for batch in batches:
        for rejected in batch.get('rejected', []):
            entries.append({
                'institution_id': batch.get('institution_id'),
                'institution_name': batch.get('institution_name'),
                'batch_id': batch.get('batch_id'),
                'row': int(rejected.get('row')) if rejected.get('row') is not None else None,
                'ci': rejected.get('ci'),
                'reason': rejected.get('reason')
            })
    return {'total': len(entries), 'items': entries}
