'''
    services/mining_summit/tests/test_participants.py

    Unit tests for participant lifecycle across the split person/registration
    model: seat assignment by axis, cupo enforcement, soft-delete (deactivate)
    and replacement. DynamoDB is mocked with moto.
'''
import pytest
from moto import mock_aws

from schemas.enums import ParticipantStatus, ThematicAxis
from services.exceptions import InvalidInputError
from services.institutions import INSTITUTIONS_TABLE
from services.mesas import AULAS_TABLE
from services.availability import get_axis_availability
from services.exceptions import RegisterNotFoundError
from services.participants import (
    PARTICIPANTS_TABLE,
    assert_cupo_available,
    count_active_by_institution,
    create_participant,
    deactivate_participant,
    list_participants,
    replace_participant,
    update_participant
)
from services.registration import REGISTRATION_TABLE, compute_mesa_occupancy
from tests.dynamo_helpers import build_resource

_AXIS = ThematicAxis.CONTRATOS


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Provides moto DynamoDB with institutions, aulas, persons and registration.'''
    with mock_aws():
        resource = build_resource([
            (INSTITUTIONS_TABLE, 'id'),
            (AULAS_TABLE, 'code'),
            (PARTICIPANTS_TABLE, 'ci'),
            (REGISTRATION_TABLE, 'ci')
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
    '''A created participant is ACTIVE, registered and seated in the axis.'''
    saved = _new_participant(dynamodb, '111')
    assert saved['status'] == ParticipantStatus.ACTIVE.value
    assert saved['registered'] is True
    assert saved['axis'] == _AXIS.value
    assert saved['mesa_code'] == 'C1'
    # The person master data has no seat/status fields.
    person = dynamodb.Table(PARTICIPANTS_TABLE).get_item(Key = {'ci': '111'})['Item']
    assert 'axis' not in person and 'status' not in person
    assert person['role']  # resolved from the institution category


def test_create_without_axis_leaves_person_unregistered(dynamodb):
    '''A person created without an axis exists but has no registration.'''
    saved = create_participant(dynamodb, {
        'ci': '900', 'first_name': 'No', 'last_name': 'Seat'
    })
    assert saved['registered'] is False
    assert saved['axis'] is None and saved['status'] is None
    assert dynamodb.Table(REGISTRATION_TABLE).get_item(Key = {'ci': '900'}).get('Item') is None


def test_deactivate_frees_seat_and_hides_from_list(dynamodb):
    '''Deactivation flips the registration to CANCELLED and frees the seat.'''
    _new_participant(dynamodb, '111')
    assert compute_mesa_occupancy(dynamodb) == {'C1': 1}

    updated = deactivate_participant(dynamodb, '111', observation = 'no asiste')
    assert updated['status'] == ParticipantStatus.CANCELLED.value
    assert updated['observation'] == 'no asiste'
    assert not compute_mesa_occupancy(dynamodb)

    listed = list_participants(dynamodb, {'limit': 50})
    assert all(item['ci'] != '111' for item in listed['items'])


def test_deactivate_twice_raises(dynamodb):
    '''Deactivating an already-inactive registration must raise.'''
    _new_participant(dynamodb, '111')
    deactivate_participant(dynamodb, '111')
    with pytest.raises(InvalidInputError):
        deactivate_participant(dynamodb, '111')


def test_replace_inherits_seat_and_retires_outgoing(dynamodb):
    '''
        A replacement inherits the outgoing seat, the outgoing registration is
        marked REPLACED with a back-reference, and the headcount is stable.
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

    outgoing = dynamodb.Table(REGISTRATION_TABLE).get_item(Key = {'ci': '111'})['Item']
    assert outgoing['status'] == ParticipantStatus.REPLACED.value
    assert outgoing['replaced_by_ci'] == '222'
    # The outgoing person master record is retained.
    assert dynamodb.Table(PARTICIPANTS_TABLE).get_item(Key = {'ci': '111'}).get('Item')

    # Net headcount unchanged: one active seat before and after.
    assert count_active_by_institution(dynamodb, 'inst-a') == 1


def test_cupo_available_blocks_when_full(dynamodb):
    '''With cupo=1 and one active participant, a further creation is blocked.'''
    _new_participant(dynamodb, '111')
    with pytest.raises(InvalidInputError):
        assert_cupo_available(dynamodb, 'inst-a')


def test_update_accredits_bare_person_with_department_institution_and_seat(dynamodb):
    '''
        Editing a bare person (no institution, no seat) assigns the department,
        the institution (deriving the role) and seats it in the chosen axis.
    '''
    create_participant(dynamodb, {'ci': '500', 'first_name': 'Sin', 'last_name': 'Datos'})

    updated = update_participant(dynamodb, '500', {
        'department': 'Oruro', 'institution_id': 'inst-a', 'axis': _AXIS.value
    })
    assert updated['department'] == 'Oruro'
    assert updated['institution_id'] == 'inst-a'
    assert updated['role']  # derived from the institution category
    assert updated['registered'] is True
    assert updated['axis'] == _AXIS.value
    assert updated['mesa_code'] == 'C1'


def test_update_institution_cupo_is_enforced(dynamodb):
    '''Assigning an institution whose cupo is already full must be blocked.'''
    _new_participant(dynamodb, '111')  # consumes the single inst-a cupo
    create_participant(dynamodb, {'ci': '600', 'first_name': 'Otro', 'last_name': 'Mas'})
    with pytest.raises(InvalidInputError):
        update_participant(dynamodb, '600', {'institution_id': 'inst-a'})


def test_update_missing_participant_raises(dynamodb):
    '''Editing a CI with no person record must raise a not-found error.'''
    with pytest.raises(RegisterNotFoundError):
        update_participant(dynamodb, '999', {'department': 'La Paz'})


def test_availability_reflects_active_registrations(dynamodb):
    '''Availability free seats drop as active registrations take aulas.'''
    before = get_axis_availability(dynamodb)
    contratos = next(a for a in before if a['axis'] == _AXIS.value)
    assert contratos['free'] == 30 and contratos['occupied'] == 0

    _new_participant(dynamodb, '111')
    after = get_axis_availability(dynamodb)
    contratos = next(a for a in after if a['axis'] == _AXIS.value)
    assert contratos['occupied'] == 1
    assert contratos['free'] == 29
    assert contratos['aulas'][0]['mesa_code'] == 'C1'
