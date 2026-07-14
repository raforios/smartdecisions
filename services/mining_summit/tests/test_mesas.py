'''
    services/mining_summit/tests/test_mesas.py

    Unit tests for the DynamoDB-backed aulas (mesas) allocation to the thematic
    axes and the parametric aula update. DynamoDB is mocked with moto.
'''
import pytest
from moto import mock_aws

from schemas.enums import ThematicAxis
from services.exceptions import RegisterAlreadyExistsError, RegisterNotFoundError
from services.mesas import (
    AULAS_TABLE,
    create_mesa,
    delete_mesa,
    list_axes,
    list_mesas,
    update_mesa
)
from services.summit_rules import AULAS_SEED, AXIS_METADATA, MESA_ALLOCATION, MESA_CAPACITY
from tests.dynamo_helpers import build_resource


def _seed_items():
    '''Builds the default aula items binding each aula to its axis (seed order).'''
    items = []
    cursor = 0
    for axis in ThematicAxis:
        for _ in range(MESA_ALLOCATION[axis]):
            aula = AULAS_SEED[cursor]
            cursor += 1
            items.append({
                'code': aula['code'],
                'block': aula['block'],
                'location': aula['location'],
                'capacity': aula['capacity'],
                'axis': axis.value
            })
    return items


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Provides a moto-mocked DynamoDB resource with a seeded aulas table.'''
    with mock_aws():
        resource = build_resource([(AULAS_TABLE, 'code')])
        table = resource.Table(AULAS_TABLE)
        for item in _seed_items():
            table.put_item(Item = item)
        yield resource


def test_list_mesas_returns_all_rooms_with_full_capacity(dynamodb):
    '''
        All 17 aulas must be listed, each carrying axis metadata, summing to the
        510 default seats (17 x 30).
    '''
    mesas = list_mesas(dynamodb)
    assert len(mesas) == len(AULAS_SEED)
    assert sum(mesa['capacity'] for mesa in mesas) == len(AULAS_SEED) * MESA_CAPACITY
    assert all(mesa['axis'] and mesa['axis_number'] for mesa in mesas)


def test_list_mesas_filtered_by_axis_matches_allocation(dynamodb):
    '''
        Filtering by an axis must return exactly the aulas allocated to it.
    '''
    axis = ThematicAxis.INSTITUCIONALIDAD
    mesas = list_mesas(dynamodb, axis = axis.value)
    assert len(mesas) == MESA_ALLOCATION[axis]
    assert all(mesa['axis'] == axis.value for mesa in mesas)


def test_list_axes_totals_are_consistent(dynamodb):
    '''
        The axes summary must cover the six axes and its totals must match the
        seeded aulas and their aggregated capacity, ordered by official number.
    '''
    axes = list_axes(dynamodb)
    assert len(axes) == len(ThematicAxis)
    assert sum(item['mesas'] for item in axes) == len(AULAS_SEED)
    assert sum(item['capacity'] for item in axes) == len(AULAS_SEED) * MESA_CAPACITY
    assert [item['number'] for item in axes] == list(range(1, len(ThematicAxis) + 1))


def test_update_mesa_changes_capacity_and_axis(dynamodb):
    '''
        Updating an aula must persist the new capacity/axis and be reflected in
        the axis aggregation.
    '''
    code = AULAS_SEED[0]['code']
    target_axis = ThematicAxis.DESARROLLO_PRODUCTIVO
    updated = update_mesa(
        dynamodb, code = code, capacity = 50, axis = target_axis.value
    )
    assert updated['capacity'] == 50
    assert updated['axis'] == target_axis.value
    assert updated['axis_number'] == AXIS_METADATA[target_axis][0]

    refetched = [mesa for mesa in list_mesas(dynamodb) if mesa['code'] == code][0]
    assert refetched['capacity'] == 50
    assert refetched['axis'] == target_axis.value


def test_create_mesa_adds_a_new_aula(dynamodb):
    '''
        A newly created aula must appear in the listing with its axis metadata,
        raising the total aula count by one.
    '''
    before = len(list_mesas(dynamodb))
    created = create_mesa(dynamodb, {
        'code': 'Z99', 'block': 'Z', 'location': 'Anexo',
        'capacity': 40, 'axis': ThematicAxis.MEDIO_AMBIENTE.value
    })
    assert created['code'] == 'Z99'
    assert created['axis_number'] == AXIS_METADATA[ThematicAxis.MEDIO_AMBIENTE][0]
    assert len(list_mesas(dynamodb)) == before + 1


def test_create_mesa_duplicate_code_raises(dynamodb):
    '''Re-using an existing aula code must raise RegisterAlreadyExistsError.'''
    with pytest.raises(RegisterAlreadyExistsError):
        create_mesa(dynamodb, {
            'code': AULAS_SEED[0]['code'], 'block': 'A', 'location': 'x',
            'capacity': 10, 'axis': ThematicAxis.CONTRATOS.value
        })


def test_delete_mesa_removes_the_aula(dynamodb):
    '''Deleting an aula removes it; deleting a missing one raises not-found.'''
    code = AULAS_SEED[0]['code']
    delete_mesa(dynamodb, code)
    assert all(mesa['code'] != code for mesa in list_mesas(dynamodb))
    with pytest.raises(RegisterNotFoundError):
        delete_mesa(dynamodb, 'DOES-NOT-EXIST')
