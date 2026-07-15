'''
    services/mining_summit/tests/test_reports_seat_distribution.py

    Unit tests for the seat distribution report (people per thematic axis and
    aula), for both the PRESENT (by attendance date) and REGISTERED bases.
    DynamoDB is mocked with moto.
'''
import pytest
from moto import mock_aws

from schemas.enums import ParticipantStatus, ThematicAxis
from schemas.reports import StatsBasis
from services.mesas import AULAS_TABLE
from services.participants import PARTICIPANTS_TABLE
from services.reports import ATTENDANCES_TABLE, get_seat_distribution
from services.summit_rules import AULAS_SEED, MESA_ALLOCATION
from tests.dynamo_helpers import build_resource

_PRESENT_DATE = '2026-07-15'


def _aula_items():
    '''Binds every aula to its axis following the seed allocation order.'''
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


# Two SEGURIDAD_JURIDICA seats (A3, A7), one CONTRATOS seat (A9), one participant
# with no seat (unassigned) and one CANCELLED participant that must be excluded.
_PARTICIPANTS = [
    {'ci': '1', 'axis': ThematicAxis.SEGURIDAD_JURIDICA.value, 'mesa_code': 'A3',
     'status': ParticipantStatus.ACTIVE.value},
    {'ci': '2', 'axis': ThematicAxis.SEGURIDAD_JURIDICA.value, 'mesa_code': 'A7',
     'status': ParticipantStatus.ACTIVE.value},
    {'ci': '3', 'axis': ThematicAxis.CONTRATOS.value, 'mesa_code': 'A9',
     'status': ParticipantStatus.ACTIVE.value},
    {'ci': '4', 'status': ParticipantStatus.ACTIVE.value},
    {'ci': '5', 'axis': ThematicAxis.SEGURIDAD_JURIDICA.value, 'mesa_code': 'A3',
     'status': ParticipantStatus.CANCELLED.value}
]

# CI 1 and 3 attended on the target date; CI 2 attended a different day.
_ATTENDANCES = [
    {'ci': '1', 'attendance_date': _PRESENT_DATE},
    {'ci': '3', 'attendance_date': _PRESENT_DATE},
    {'ci': '2', 'attendance_date': '2026-07-14'}
]


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Provides a moto DynamoDB with seeded aulas, participants and attendances.'''
    with mock_aws():
        resource = build_resource([
            (AULAS_TABLE, 'code'),
            (PARTICIPANTS_TABLE, 'ci'),
            (ATTENDANCES_TABLE, 'ci')
        ])
        for item in _aula_items():
            resource.Table(AULAS_TABLE).put_item(Item = item)
        for item in _PARTICIPANTS:
            resource.Table(PARTICIPANTS_TABLE).put_item(Item = item)
        for item in _ATTENDANCES:
            resource.Table(ATTENDANCES_TABLE).put_item(Item = item)
        yield resource


def _axis(result, axis: ThematicAxis):
    '''Returns the axis entry for the given thematic axis from a result payload.'''
    return next(entry for entry in result['axes'] if entry['axis'] == axis.value)


def test_registered_counts_active_participants_by_axis_and_aula(dynamodb):
    '''
        REGISTERED counts every active participant (CANCELLED excluded), splits
        them by axis/aula and reports the seatless one as unassigned.
    '''
    result = get_seat_distribution(dynamodb, StatsBasis.REGISTERED)

    assert result['date'] is None
    assert result['total'] == 4
    assert result['unassigned'] == 1
    assert len(result['axes']) == len(ThematicAxis)

    seguridad = _axis(result, ThematicAxis.SEGURIDAD_JURIDICA)
    assert seguridad['count'] == 2
    aula_counts = {aula['mesa_code']: aula['count'] for aula in seguridad['aulas']}
    assert aula_counts['A3'] == 1
    assert aula_counts['A7'] == 1
    assert _axis(result, ThematicAxis.CONTRATOS)['count'] == 1


def test_present_counts_only_attendees_on_date(dynamodb):
    '''
        PRESENT on the target date counts only CIs 1 and 3, ignoring the
        attendance from another day and the never-present participants.
    '''
    result = get_seat_distribution(dynamodb, StatsBasis.PRESENT, _PRESENT_DATE)

    assert result['date'] == _PRESENT_DATE
    assert result['total'] == 2
    assert result['unassigned'] == 0
    assert _axis(result, ThematicAxis.SEGURIDAD_JURIDICA)['count'] == 1
    assert _axis(result, ThematicAxis.CONTRATOS)['count'] == 1


def test_present_on_empty_date_returns_zeroed_axes(dynamodb):
    '''
        A date with no attendances yields a zero total while still listing every
        axis and aula (pre-seeded skeleton) so the UI can render an empty state.
    '''
    result = get_seat_distribution(dynamodb, StatsBasis.PRESENT, '2020-01-01')

    assert result['total'] == 0
    assert len(result['axes']) == len(ThematicAxis)
    assert all(aula['count'] == 0
               for axis in result['axes'] for aula in axis['aulas'])
