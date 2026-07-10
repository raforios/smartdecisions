'''
    services/mining_summit/tests/test_seating.py

    Unit tests for the fixed-seat auto-distribution engine. Pure logic, no AWS.
'''
from services.seating import select_seat
from services.summit_rules import AULAS_SEED, MESA_CAPACITY


def test_empty_occupancy_returns_first_mesa():
    '''
        With no one seated the engine must return a mesa carrying axis metadata.
    '''
    seat = select_seat({})
    assert seat is not None
    assert seat['code']
    assert seat['axis'] and seat['axis_number']


def test_distribution_is_balanced_across_all_mesas():
    '''
        Seating participants one by one must spread them evenly: the first pass
        of assignments fills every mesa exactly once before any gets a second.
    '''
    occupancy: dict[str, int] = {}
    picks: list[str] = []
    for _ in range(len(AULAS_SEED)):
        seat = select_seat(occupancy)
        assert seat is not None
        picks.append(seat['code'])
        occupancy[seat['code']] = occupancy.get(seat['code'], 0) + 1
    assert len(set(picks)) == len(AULAS_SEED)


def test_least_occupied_mesa_is_preferred():
    '''
        The engine must prefer the mesa with the fewest occupants.
    '''
    occupancy = {mesa['code']: 5 for mesa in AULAS_SEED}
    target = AULAS_SEED[7]['code']
    occupancy[target] = 1
    seat = select_seat(occupancy)
    assert seat['code'] == target


def test_returns_none_when_all_mesas_are_full():
    '''
        When every mesa is at capacity the engine must return None (no seat).
    '''
    occupancy = {mesa['code']: MESA_CAPACITY for mesa in AULAS_SEED}
    assert select_seat(occupancy) is None
