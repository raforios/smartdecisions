'''
    Business logic for the Reports module of the Mining Summit service.

    Computes aggregate statistics over the participants table by an arbitrary
    grouping dimension (department or company).
'''
from typing import Any, Dict, List
from boto3.resources.base import ServiceResource

from schemas.reports import StatsGroupBy
from services.logger_config import custom_logger as logger
from services.participants import scan_all_participants
from services.utils import handle_service_errors


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
