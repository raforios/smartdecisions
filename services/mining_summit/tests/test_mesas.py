'''
    services/mining_summit/tests/test_mesas.py

    Unit tests for the mesas (working tables) allocation to the thematic axes.
    They run without AWS access (fixed reference seed).
'''
from schemas.enums import ThematicAxis
from services.mesas import list_axes, list_mesas
from services.summit_rules import AULAS_SEED, MESA_ALLOCATION, MESA_CAPACITY


def test_allocation_consumes_every_aula_exactly():
    '''
        The per-axis allocation must sum to the number of seeded aulas so every
        room is bound to exactly one axis.
    '''
    assert sum(MESA_ALLOCATION.values()) == len(AULAS_SEED)


def test_list_mesas_returns_all_rooms_with_full_capacity():
    '''
        All 17 mesas must be listed, each carrying axis metadata, summing to the
        510 fixed seats (17 x 30).
    '''
    mesas = list_mesas()
    assert len(mesas) == len(AULAS_SEED)
    assert sum(mesa['capacity'] for mesa in mesas) == len(AULAS_SEED) * MESA_CAPACITY
    assert all(mesa['axis'] and mesa['axis_number'] for mesa in mesas)


def test_list_mesas_filtered_by_axis_matches_allocation():
    '''
        Filtering by an axis must return exactly the mesas allocated to it.
    '''
    axis = ThematicAxis.INSTITUCIONALIDAD
    mesas = list_mesas(axis = axis.value)
    assert len(mesas) == MESA_ALLOCATION[axis]
    assert all(mesa['axis'] == axis.value for mesa in mesas)


def test_list_axes_totals_are_consistent():
    '''
        The axes summary must cover the six axes and its totals must match the
        seeded aulas and their aggregated capacity.
    '''
    axes = list_axes()
    assert len(axes) == len(ThematicAxis)
    assert sum(item['mesas'] for item in axes) == len(AULAS_SEED)
    assert sum(item['capacity'] for item in axes) == len(AULAS_SEED) * MESA_CAPACITY
    # Axes must be ordered by their official number (1..6).
    assert [item['number'] for item in axes] == list(range(1, len(ThematicAxis) + 1))
