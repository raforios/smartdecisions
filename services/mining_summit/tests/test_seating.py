'''
    services/mining_summit/tests/test_seating.py

    Unit tests for the per-axis seat-distribution engine. DynamoDB (aulas table)
    is mocked with moto.
'''
import pytest
from moto import mock_aws

from schemas.enums import ThematicAxis
from services.exceptions import InvalidInputError
from services.mesas import AULAS_TABLE, list_mesas
from services.seating import select_seat
from tests.dynamo_helpers import build_resource

# Two axes with distinct capacities to exercise axis-scoped balancing.
_AXIS = ThematicAxis.CONTRATOS.value
_OTHER_AXIS = ThematicAxis.MEDIO_AMBIENTE.value
_SEED = [
    {'code': 'C1', 'block': 'A', 'location': 'PB', 'capacity': 2, 'axis': _AXIS},
    {'code': 'C2', 'block': 'A', 'location': 'PB', 'capacity': 2, 'axis': _AXIS},
    {'code': 'M1', 'block': 'A', 'location': 'PB', 'capacity': 5, 'axis': _OTHER_AXIS},
]


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Provides a moto-mocked DynamoDB resource with a small aulas seed.'''
    with mock_aws():
        resource = build_resource([(AULAS_TABLE, 'code')])
        table = resource.Table(AULAS_TABLE)
        for item in _SEED:
            table.put_item(Item = item)
        yield resource


def test_seat_is_within_chosen_axis(dynamodb):
    '''
        The engine must only ever return an aula of the chosen axis.
    '''
    seat = select_seat(dynamodb, axis = _AXIS, occupancy = {})
    assert seat['axis'] == _AXIS
    assert seat['code'] in {'C1', 'C2'}


def test_distribution_is_balanced_within_axis(dynamodb):
    '''
        Filling the axis one by one must spread evenly across its aulas before
        any of them gets a second occupant.
    '''
    occupancy: dict[str, int] = {}
    picks: list[str] = []
    for _ in range(2):
        seat = select_seat(dynamodb, axis = _AXIS, occupancy = occupancy)
        picks.append(seat['code'])
        occupancy[seat['code']] = occupancy.get(seat['code'], 0) + 1
    assert set(picks) == {'C1', 'C2'}


def test_axis_full_raises(dynamodb):
    '''
        When every aula of the chosen axis is at capacity, the engine must raise
        (axis capacity reached).
    '''
    occupancy = {mesa['code']: mesa['capacity']
                 for mesa in list_mesas(dynamodb, axis = _AXIS)}
    with pytest.raises(InvalidInputError):
        select_seat(dynamodb, axis = _AXIS, occupancy = occupancy)


def test_unknown_axis_raises(dynamodb):
    '''
        An axis with no allocated aulas must raise InvalidInputError.
    '''
    with pytest.raises(InvalidInputError):
        select_seat(dynamodb, axis = ThematicAxis.SEGURIDAD_JURIDICA.value, occupancy = {})
