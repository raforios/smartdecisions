'''
    services/mining_summit/tests/test_reports_lifecycle.py

    Unit tests for the retired-participants report (replaced / cancelled), which
    joins registrations with persons and institutions and surfaces the substitute
    for replacements. DynamoDB is mocked with moto.
'''
import pytest
from moto import mock_aws

from schemas.enums import ParticipantStatus
from services.institutions import INSTITUTIONS_TABLE
from services.participants import PARTICIPANTS_TABLE
from services.registration import REGISTRATION_TABLE
from services.reports import get_lifecycle_report
from tests.dynamo_helpers import build_resource


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Seeds persons, registrations (active/replaced/cancelled) and institutions.'''
    with mock_aws():
        resource = build_resource([
            (PARTICIPANTS_TABLE, 'ci'),
            (REGISTRATION_TABLE, 'ci'),
            (INSTITUTIONS_TABLE, 'id')
        ])
        resource.Table(INSTITUTIONS_TABLE).put_item(Item = {'id': 'inst-a', 'name': 'Institución A'})
        persons = resource.Table(PARTICIPANTS_TABLE)
        persons.put_item(Item = {'ci': '1', 'first_name': 'Ana', 'last_name': 'Lopez',
                                 'institution_id': 'inst-a', 'role': 'PARTICIPANTE'})
        persons.put_item(Item = {'ci': '2', 'first_name': 'Sub', 'last_name': 'Stituto'})
        persons.put_item(Item = {'ci': '3', 'first_name': 'Carlos', 'last_name': 'Ruiz'})
        persons.put_item(Item = {'ci': '4', 'first_name': 'Activo', 'last_name': 'Vigente'})
        registration = resource.Table(REGISTRATION_TABLE)
        # Ana was replaced by CI 2.
        registration.put_item(Item = {
            'ci': '1', 'status': ParticipantStatus.REPLACED.value, 'mesa_code': 'C1',
            'axis_label': 'Contratos Mineros', 'replaced_by_ci': '2',
            'observation': 'cambio institucional', 'status_changed_by': 'op@min.gob.bo',
            'status_changed_at': '2026-07-17T09:00:00'
        })
        registration.put_item(Item = {'ci': '2', 'status': ParticipantStatus.ACTIVE.value,
                                      'mesa_code': 'C1', 'replaces_ci': '1'})
        # Carlos declined entirely.
        registration.put_item(Item = {
            'ci': '3', 'status': ParticipantStatus.CANCELLED.value, 'mesa_code': 'C2',
            'observation': 'no podrá asistir', 'status_changed_by': 'acred@min.gob.bo',
            'status_changed_at': '2026-07-17T10:00:00'
        })
        # An active registration must NOT appear in the report.
        registration.put_item(Item = {'ci': '4', 'status': ParticipantStatus.ACTIVE.value,
                                      'mesa_code': 'C3'})
        yield resource


def test_lifecycle_lists_replaced_with_substitute(dynamodb):
    '''Replaced entries carry the reason, operator and substitute name/CI.'''
    report = get_lifecycle_report(dynamodb)
    assert report['total_replaced'] == 1
    entry = report['replaced'][0]
    assert entry['ci'] == '1'
    assert entry['first_name'] == 'Ana'
    assert entry['institution_name'] == 'Institución A'
    assert entry['observation'] == 'cambio institucional'
    assert entry['status_changed_by'] == 'op@min.gob.bo'
    assert entry['substitute_ci'] == '2'
    assert entry['substitute_name'] == 'Sub Stituto'


def test_lifecycle_lists_cancelled_with_reason(dynamodb):
    '''Cancelled entries carry the reason and operator, without a substitute.'''
    report = get_lifecycle_report(dynamodb)
    assert report['total_cancelled'] == 1
    entry = report['cancelled'][0]
    assert entry['ci'] == '3'
    assert entry['observation'] == 'no podrá asistir'
    assert entry['status_changed_by'] == 'acred@min.gob.bo'
    assert entry['substitute_ci'] is None


def test_lifecycle_excludes_active_registrations(dynamodb):
    '''Active (and substitute) registrations never show as retired.'''
    report = get_lifecycle_report(dynamodb)
    retired_cis = {e['ci'] for e in report['replaced'] + report['cancelled']}
    assert '4' not in retired_cis
    assert '2' not in retired_cis