'''
    Seat-assignment engine for the Mining Summit.

    The participant chooses a thematic axis (eje) when registering; the engine
    distributes them across the aulas allocated to THAT axis in a balanced way:
    each new participant takes the least-occupied aula of the chosen axis that
    still has free capacity. The assignment is computed once and persisted, so a
    participant keeps the same eje and mesa for the whole event.
'''
from typing import Any, Dict, Optional
from boto3.resources.base import ServiceResource

from services.exceptions import InvalidInputError
from services.mesas import list_mesas


def select_seat(
    dynamodb_resource: ServiceResource,
    axis: str,
    occupancy: Dict[str, int]
) -> Dict[str, Any]:
    '''
        Picks the least-occupied aula of the given axis that still has capacity.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            axis (str): Thematic axis value chosen by the participant.
            occupancy (Dict[str, int]): Current seat count keyed by mesa code.

        Returns:
            Dict[str, Any]: The chosen aula (with axis metadata).

        Raises:
            InvalidInputError: If the axis has no aulas allocated, or every aula
                of the axis is already full (axis capacity reached).
    '''
    axis_mesas = list_mesas(dynamodb_resource = dynamodb_resource, axis = axis)
    if not axis_mesas:
        raise InvalidInputError(
            detail = f'No aulas are allocated to axis "{axis}".'
        )

    chosen: Optional[Dict[str, Any]] = None
    lowest_count: Optional[int] = None
    for mesa in axis_mesas:
        count = occupancy.get(mesa['code'], 0)
        if count >= mesa['capacity']:
            continue
        if lowest_count is None or count < lowest_count:
            chosen = dict(mesa)
            lowest_count = count

    if chosen is None:
        raise InvalidInputError(
            detail = f'Axis "{axis}" is full; every allocated aula reached capacity.'
        )
    return chosen
