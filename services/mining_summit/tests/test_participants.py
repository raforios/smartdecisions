'''
    services/mining_summit/tests/test_participants.py

    Unit tests for participant lifecycle: seat assignment by axis, cupo
    enforcement, soft-delete (deactivate) and replacement. DynamoDB is mocked
    with moto.
'''
import pytest
from moto import mock_aws

from schemas.enums import ParticipantStatus, ThematicAxis
from services.exceptions import InvalidInputError
from services.institutions import INSTITUTIONS_TABLE
from services.mesas import AULAS_TABLE
from services.participants import (
    PARTICIPANTS_TABLE,
    assert_cupo_available,
    compute_mesa_occupancy,
    count_active_by_institution,
    create_participant,
    deactivate_participant,
    list_participants,
    replace_participant
)
from tests.dynamo_helpers import build_resource

_AXIS = ThematicAxis.CONTRATOS


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Provides moto DynamoDB with institutions, aulas and participants tables.'''
    with mock_aws():
        resource = build_resource([
            (INSTITUTIONS_TABLE, 'id'),
            (AULAS_TABLE, 'code'),
            (PARTICIPANTS_TABLE, 'ci')
        ])
        resource.Table(INSTITUTIONS_TABLE).put_item(Item = {
            'id': 'inst-a', 'number': 1, 'name': 'Institución A',
            'category': 'ACTORES PRODUCTIVOS MINEROS', 'cupos': 1
        })
        resource.Table(AULAS_TABLE).put_item(Item = {
            'code': 'C1', 'block': 'A', 'location': 'PB',
            'capacity': 30, 'axis': _AXIS.value
        })
        yield resource


def _new_participant(dynamodb, ci):
    '''Creates an ACTIVE seated participant of inst-a in the CONTRATOS axis.'''
    return create_participant(dynamodb, {
        'ci': ci, 'first_name': 'N', 'last_name': 'A',
        'department': 'La Paz', 'phone': '700',
        'institution_id': 'inst-a', 'axis': _AXIS.value
    })


def test_create_assigns_seat_and_active(dynamodb):
    '''A created participant is ACTIVE and seated in the chosen axis.'''
    saved = _new_participant(dynamodb, '111')
    assert saved['status'] == ParticipantStatus.ACTIVE.value
    assert saved['axis'] == _AXIS.value
    assert saved['mesa_code'] == 'C1'


def test_deactivate_frees_seat_and_hides_from_list(dynamodb):
    '''Deactivation flips status to CANCELLED, frees the seat and hides it.'''
    _new_participant(dynamodb, '111')
    assert compute_mesa_occupancy(dynamodb) == {'C1': 1}

    updated = deactivate_participant(dynamodb, '111', observation = 'no asiste')
    assert updated['status'] == ParticipantStatus.CANCELLED.value
    assert updated['observation'] == 'no asiste'
    assert not compute_mesa_occupancy(dynamodb)

    listed = list_participants(dynamodb, {'limit': 50})
    assert all(item['ci'] != '111' for item in listed['items'])


def test_deactivate_twice_raises(dynamodb):
    '''Deactivating an already-inactive participant must raise.'''
    _new_participant(dynamodb, '111')
    deactivate_participant(dynamodb, '111')
    with pytest.raises(InvalidInputError):
        deactivate_participant(dynamodb, '111')


def test_replace_inherits_seat_and_retires_outgoing(dynamodb):
    '''
        A replacement inherits the outgoing seat, the outgoing is marked
        REPLACED with a back-reference, and the institution headcount is stable.
    '''
    _new_participant(dynamodb, '111')
    saved = replace_participant(dynamodb, '111', {
        'ci': '222', 'first_name': 'Sub', 'last_name': 'Stitute',
        'observation': 'autorizado por la institución'
    })
    assert saved['status'] == ParticipantStatus.ACTIVE.value
    assert saved['mesa_code'] == 'C1'
    assert saved['axis'] == _AXIS.value
    assert saved['replaces_ci'] == '111'

    outgoing = dynamodb.Table(PARTICIPANTS_TABLE).get_item(Key = {'ci': '111'})['Item']
    assert outgoing['status'] == ParticipantStatus.REPLACED.value
    assert outgoing['replaced_by_ci'] == '222'

    # Net headcount unchanged: one active seat before and after.
    assert count_active_by_institution(dynamodb, 'inst-a') == 1


def test_cupo_available_blocks_when_full(dynamodb):
    '''With cupo=1 and one active participant, a further creation is blocked.'''
    _new_participant(dynamodb, '111')
    with pytest.raises(InvalidInputError):
        assert_cupo_available(dynamodb, 'inst-a')
