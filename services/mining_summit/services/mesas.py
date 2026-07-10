'''
    Business logic for the mesas (working tables) and their allocation to the
    thematic axes of the Mining Summit.

    Mesas are the fixed campus rooms (aulas ≡ mesas). Each axis receives a fixed
    number of mesas, set by importance in summit_rules.MESA_ALLOCATION. The
    axis-to-mesa binding is derived deterministically from the seed order.
'''
from functools import lru_cache
from typing import Any, Dict, List, Optional

from schemas.enums import ThematicAxis
from services.summit_rules import (
    AULAS_SEED,
    AXIS_METADATA,
    MESA_ALLOCATION
)


def _validate_allocation() -> None:
    '''
        Ensures the per-axis mesa allocation exactly consumes the seeded aulas.

        Raises:
            ValueError: If the allocation total differs from the aula count.
    '''
    allocated = sum(MESA_ALLOCATION.values())
    if allocated != len(AULAS_SEED):
        raise ValueError(
            f'MESA_ALLOCATION assigns {allocated} mesas but there are '
            f'{len(AULAS_SEED)} aulas; the totals must match.'
        )


@lru_cache(maxsize = 1)
def _build_mesa_assignments() -> tuple[Dict[str, Any], ...]:
    '''
        Binds each seeded aula to a thematic axis following the fixed allocation.

        Returns:
            tuple[Dict[str, Any], ...]: Mesas enriched with their axis metadata.
    '''
    _validate_allocation()
    assignments: List[Dict[str, Any]] = []
    cursor = 0
    for axis in ThematicAxis:
        number, label = AXIS_METADATA[axis]
        for _ in range(MESA_ALLOCATION[axis]):
            aula = AULAS_SEED[cursor]
            cursor += 1
            assignments.append({
                **aula,
                'axis': axis.value,
                'axis_number': number,
                'axis_label': label
            })
    return tuple(assignments)


def list_mesas(axis: Optional[str] = None) -> List[Dict[str, Any]]:
    '''
        Returns the allocated mesas, optionally filtered by thematic axis.

        Args:
            axis (Optional[str]): Axis value to filter by.

        Returns:
            List[Dict[str, Any]]: Matching mesas with axis metadata.
    '''
    mesas = list(_build_mesa_assignments())
    if axis:
        mesas = [mesa for mesa in mesas if mesa['axis'] == axis]
    return mesas


def list_axes() -> List[Dict[str, Any]]:
    '''
        Returns the six thematic axes with their allocated mesa count and the
        aggregated seat capacity.

        Returns:
            List[Dict[str, Any]]: Axis summaries ordered by official number.
    '''
    mesas = _build_mesa_assignments()
    summaries: List[Dict[str, Any]] = []
    for axis in ThematicAxis:
        number, label = AXIS_METADATA[axis]
        axis_mesas = [mesa for mesa in mesas if mesa['axis'] == axis.value]
        summaries.append({
            'axis': axis.value,
            'number': number,
            'label': label,
            'mesas': len(axis_mesas),
            'capacity': sum(mesa['capacity'] for mesa in axis_mesas)
        })
    return summaries
