'''
    services/mining_summit/tests/test_exports.py

    Unit tests for the Excel report exports. DynamoDB is mocked with moto and the
    produced workbooks are re-opened in memory to assert their contents.
'''
import io

import openpyxl
import pytest
from moto import mock_aws

from schemas.enums import ParticipantStatus
from services.attendances import ATTENDANCES_TABLE
from services.exports import export_attendances_xlsx, export_participants_xlsx
from services.institutions import INSTITUTIONS_TABLE
from services.participants import PARTICIPANTS_TABLE
from services.registration import REGISTRATION_TABLE
from tests.dynamo_helpers import build_resource


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Provides moto DynamoDB with persons, registrations, institutions, attendances.'''
    with mock_aws():
        resource = build_resource([
            (PARTICIPANTS_TABLE, 'ci'),
            (REGISTRATION_TABLE, 'ci'),
            (INSTITUTIONS_TABLE, 'id'),
            (ATTENDANCES_TABLE, 'ci')
        ])
        resource.Table(INSTITUTIONS_TABLE).put_item(Item = {
            'id': 'inst-a', 'name': 'Institución A'
        })
        persons = resource.Table(PARTICIPANTS_TABLE)
        persons.put_item(Item = {
            'ci': '111', 'first_name': 'Ana', 'last_name': 'Lopez',
            'institution_id': 'inst-a', 'role': 'PARTICIPANTE',
            'department': 'La Paz', 'created_at': '2026-07-14T09:00:00'
        })
        persons.put_item(Item = {
            'ci': '222', 'first_name': 'Beto', 'last_name': 'Ruiz',
            'created_at': '2026-07-14T09:05:00'
        })
        registration = resource.Table(REGISTRATION_TABLE)
        registration.put_item(Item = {
            'ci': '111', 'axis_label': 'Contratos Mineros', 'mesa_code': 'C1',
            'status': ParticipantStatus.ACTIVE.value, 'registered_at': '2026-07-14T09:00:00'
        })
        registration.put_item(Item = {
            'ci': '222', 'status': ParticipantStatus.CANCELLED.value,
            'registered_at': '2026-07-14T09:05:00'
        })
        resource.Table(ATTENDANCES_TABLE).put_item(Item = {
            'ci': '111', 'attendance_date': '2026-07-14',
            'attendance_at': '2026-07-14T09:10:00', 'marked_by': 'op@x.com'
        })
        yield resource


def _load(content):
    '''Re-opens workbook bytes and returns the active sheet rows (values only).'''
    workbook = openpyxl.load_workbook(io.BytesIO(content))
    return list(workbook.active.iter_rows(values_only = True))


def test_participants_export_excludes_inactive_by_default(dynamodb):
    '''Only ACTIVE participants appear unless include_inactive is requested.'''
    rows = _load(export_participants_xlsx(dynamodb))
    cis = [row[0] for row in rows[1:]]
    assert '111' in cis
    assert '222' not in cis
    assert rows[0][0] == 'CI'


def test_participants_export_can_include_inactive(dynamodb):
    '''include_inactive brings CANCELLED/REPLACED participants into the export.'''
    rows = _load(export_participants_xlsx(dynamodb, include_inactive = True))
    cis = [row[0] for row in rows[1:]]
    assert {'111', '222'} <= set(cis)


def test_attendances_export_contains_checkins(dynamodb):
    '''The attendances export lists every recorded check-in.'''
    rows = _load(export_attendances_xlsx(dynamodb))
    assert rows[0] == ('CI', 'Fecha', 'Hora', 'Registrado por')
    assert rows[1][0] == '111'
    assert rows[1][1] == '2026-07-14'
