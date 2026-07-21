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
from services.summit_rules import AULAS_SEED, AXIS_METADATA, MESA_ALLOCATION
from tests.dynamo_helpers import build_resource

_TOTAL_CAPACITY = sum(aula['capacity'] for aula in AULAS_SEED)


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
        Every seeded aula must be listed, each carrying axis metadata, summing to
        the aggregated seat capacity of AULAS_SEED.
    '''
    mesas = list_mesas(dynamodb)
    assert len(mesas) == len(AULAS_SEED)
    assert sum(mesa['capacity'] for mesa in mesas) == _TOTAL_CAPACITY
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
    assert sum(item['capacity'] for item in axes) == _TOTAL_CAPACITY
    assert [item['number'] for item in axes] == list(range(1, len(ThematicAxis) + 1))


def test_update_mesa_changes_capacity_and_axis(dynamodb):
    '''
        Updating an aula must persist the new capacity/axis and be reflected in
        the axis aggregation.
    '''
    code = AULAS_SEED[0]['code']
    target_axis = ThematicAxis.DESARROLLO_PRODUCTIVO
    updated = update_mesa(
        dynamodb, code = code, changes = {'capacity': 50, 'axis': target_axis.value}
    )
    assert updated['capacity'] == 50
    assert updated['axis'] == target_axis.value
    assert updated['axis_number'] == AXIS_METADATA[target_axis][0]

    refetched = [mesa for mesa in list_mesas(dynamodb) if mesa['code'] == code][0]
    assert refetched['capacity'] == 50
    assert refetched['axis'] == target_axis.value


def test_update_mesa_changes_location_fields(dynamodb):
    '''
        Editing an aula must persist new block/location values (descriptive
        fields), leaving the axis untouched when it is not supplied.
    '''
    code = AULAS_SEED[0]['code']
    updated = update_mesa(
        dynamodb, code = code,
        changes = {'block': 'Bloque Nuevo', 'location': 'Segundo Piso'}
    )
    assert updated['block'] == 'Bloque Nuevo'
    assert updated['location'] == 'Segundo Piso'
    assert updated['axis'] is not None


def test_create_pivot_aula_without_axis(dynamodb):
    '''
        A pivot aula (free disposition) is created without an axis and carries no
        axis metadata until it is allocated to a thematic axis.
    '''
    created = create_mesa(dynamodb, {
        'code': 'PIV1', 'block': 'P', 'location': 'Libre', 'capacity': 30
    })
    assert created['axis'] is None
    assert created['axis_number'] is None
    assert created['axis_label'] is None

    listed = [mesa for mesa in list_mesas(dynamodb) if mesa['code'] == 'PIV1'][0]
    assert listed['axis'] is None


def test_allocate_pivot_aula_to_axis(dynamodb):
    '''
        A pivot aula can later be assigned to a thematic axis via update, which
        then attaches its axis metadata and counts toward that axis.
    '''
    create_mesa(dynamodb, {
        'code': 'PIV2', 'block': 'P', 'location': 'Libre', 'capacity': 25
    })
    updated = update_mesa(
        dynamodb, code = 'PIV2',
        changes = {'axis': ThematicAxis.CONTRATOS.value}
    )
    assert updated['axis'] == ThematicAxis.CONTRATOS.value
    assert updated['axis_number'] == AXIS_METADATA[ThematicAxis.CONTRATOS][0]


def test_deallocate_aula_back_to_pivot(dynamodb):
    '''
        Passing an explicit None axis de-allocates an allocated aula, turning it
        back into a pivot (its axis metadata is cleared).
    '''
    code = AULAS_SEED[0]['code']
    updated = update_mesa(dynamodb, code = code, changes = {'axis': None})
    assert updated['axis'] is None
    assert updated['axis_number'] is None

    refetched = [mesa for mesa in list_mesas(dynamodb) if mesa['code'] == code][0]
    assert refetched['axis'] is None


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
