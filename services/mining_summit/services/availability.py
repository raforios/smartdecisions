'''
    Seat availability for the Mining Summit.

    Aggregates the current registration occupancy against the aula capacities to
    expose, per thematic axis and per aula, how many seats are still free. Used
    by the accreditation desk to pick an axis and to guide the operator when the
    chosen axis is full (which aulas/axes still have room).
'''
from typing import Any, Dict, List
from boto3.resources.base import ServiceResource

from services.mesas import list_mesas
from services.registration import compute_mesa_occupancy
from services.utils import handle_service_errors


@handle_service_errors
def get_axis_availability(dynamodb_resource: ServiceResource) -> List[Dict[str, Any]]:
    '''
        Builds the per-axis availability, each broken down by its aulas with the
        free seat count (capacity minus active registrations).

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.

        Returns:
            List[Dict[str, Any]]: Axis availability ordered by official number,
                each with capacity/occupied/free totals and its aulas.
    '''
    occupancy = compute_mesa_occupancy(dynamodb_resource)
    axes: Dict[str, Dict[str, Any]] = {}
    for mesa in list_mesas(dynamodb_resource = dynamodb_resource):
        occupied = occupancy.get(mesa['code'], 0)
        free = max(0, mesa['capacity'] - occupied)
        axis = axes.setdefault(mesa['axis'], {
            'axis': mesa['axis'],
            'number': mesa['axis_number'],
            'label': mesa['axis_label'],
            'capacity': 0,
            'occupied': 0,
            'free': 0,
            'aulas': []
        })
        axis['capacity'] += mesa['capacity']
        axis['occupied'] += occupied
        axis['free'] += free
        axis['aulas'].append({
            'mesa_code': mesa['code'],
            'capacity': mesa['capacity'],
            'occupied': occupied,
            'free': free
        })
    return sorted(axes.values(), key = lambda entry: entry['number'])
