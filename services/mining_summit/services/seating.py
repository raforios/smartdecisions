'''
    Seat-assignment engine for the Mining Summit.

    Fixed-seat (FIJO) participants are auto-distributed across the mesas in a
    balanced way: each new participant takes the least-occupied mesa that still
    has capacity. The assignment is computed once at registration and persisted,
    so a participant keeps the same eje and mesa for the whole event.
'''
from typing import Any, Dict, Optional

from services.mesas import list_mesas


def select_seat(occupancy: Dict[str, int]) -> Optional[Dict[str, Any]]:
    '''
        Picks the least-occupied mesa that still has free capacity.

        Args:
            occupancy (Dict[str, int]): Current seat count keyed by mesa code.

        Returns:
            Optional[Dict[str, Any]]: The chosen mesa (with axis metadata), or
                None when every mesa is full.
    '''
    chosen: Optional[Dict[str, Any]] = None
    lowest_count: Optional[int] = None
    for mesa in list_mesas():
        count = occupancy.get(mesa['code'], 0)
        if count >= mesa['capacity']:
            continue
        if lowest_count is None or count < lowest_count:
            chosen = dict(mesa)
            lowest_count = count
    return chosen
