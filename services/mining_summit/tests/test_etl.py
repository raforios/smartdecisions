'''
    services/mining_summit/tests/test_etl.py

    Unit tests for the participant batch-load ETL: mandatory-field validation,
    cupo enforcement and per-axis seat assignment. DynamoDB is mocked with moto
    and the input workbook is built in memory with openpyxl.
'''
import io

import openpyxl
import pytest
from moto import mock_aws

from schemas.enums import ParticipantRole, ParticipantStatus, ThematicAxis
from services.etl import LOAD_BATCHES_TABLE, load_participants_from_excel
from services.institutions import INSTITUTIONS_TABLE
from services.mesas import AULAS_TABLE
from services.participants import PARTICIPANTS_TABLE
from tests.dynamo_helpers import build_resource

_AXIS = ThematicAxis.SEGURIDAD_JURIDICA  # axis number 1

# Header row mirrors the distributed template (accent/case-insensitive aliases).
_HEADERS = ['Carnet de Identidad', 'Nombre', 'Apellido', 'Correo electrónico',
            'Celular', 'Departamento', 'Eje Temático']


def _build_workbook(rows):
    '''Builds an in-memory .xlsx (sheet "Registro") and returns its bytes.'''
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = 'Registro'
    worksheet.append(_HEADERS)
    for row in rows:
        worksheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Provides moto DynamoDB with institutions, aulas, participants, batches.'''
    with mock_aws():
        resource = build_resource([
            (INSTITUTIONS_TABLE, 'id'),
            (AULAS_TABLE, 'code'),
            (PARTICIPANTS_TABLE, 'ci'),
            (LOAD_BATCHES_TABLE, 'batch_id')
        ])
        resource.Table(INSTITUTIONS_TABLE).put_item(Item = {
            'id': 'inst-a', 'number': 1, 'name': 'Institución A',
            'category': 'ACTORES PRODUCTIVOS MINEROS', 'cupos': 2
        })
        resource.Table(AULAS_TABLE).put_item(Item = {
            'code': 'A1', 'block': 'A', 'location': 'PB',
            'capacity': 30, 'axis': _AXIS.value
        })
        yield resource


_RESPONSIBLE = {'name': 'Juana Perez', 'phone': '70000000'}


def test_cupo_limits_accepted_rows(dynamodb):
    '''
        With cupo=2 and three valid rows, only the first two are accredited and
        the third is reported as not accredited (cupo reached).
    '''
    file_bytes = _build_workbook([
        ['111', 'Ana', 'Lopez', 'ana@x.com', '701', 'La Paz', 1],
        ['222', 'Beto', 'Ruiz', '', '702', 'Oruro', 1],
        ['333', 'Cira', 'Diaz', '', '703', 'Potosí', 1],
    ])
    summary = load_participants_from_excel(
        dynamodb, file_bytes, 'inst-a', _RESPONSIBLE, ParticipantRole.PARTICIPANTE.value
    )

    assert summary['accepted_count'] == 2
    assert summary['rejected_count'] == 1
    assert summary['rejected'][0]['ci'] == '333'
    assert 'cupo' in summary['rejected'][0]['reason'].lower()
    assert all(entry['axis'] == _AXIS.value for entry in summary['accepted'])
    assert all(entry['mesa_code'] == 'A1' for entry in summary['accepted'])


def test_missing_required_field_is_rejected(dynamodb):
    '''
        A row missing a mandatory field (department) is rejected as invalid,
        while the valid one is accredited. Email remains optional.
    '''
    file_bytes = _build_workbook([
        ['111', 'Ana', 'Lopez', '', '701', '', 1],           # missing department
        ['222', 'Beto', 'Ruiz', '', '702', 'Oruro', 1],      # valid, no email
    ])
    summary = load_participants_from_excel(
        dynamodb, file_bytes, 'inst-a', _RESPONSIBLE, ParticipantRole.PARTICIPANTE.value
    )

    assert summary['accepted_count'] == 1
    assert summary['rejected_count'] == 1
    assert summary['rejected'][0]['ci'] == '111'
    assert 'department' in summary['rejected'][0]['reason'].lower()


def test_invalid_axis_number_is_rejected(dynamodb):
    '''
        An out-of-range axis number (0 or 7) must be rejected with an axis error.
    '''
    file_bytes = _build_workbook([
        ['111', 'Ana', 'Lopez', '', '701', 'La Paz', 9],
    ])
    summary = load_participants_from_excel(
        dynamodb, file_bytes, 'inst-a', _RESPONSIBLE, ParticipantRole.PARTICIPANTE.value
    )
    assert summary['accepted_count'] == 0
    assert 'axis' in summary['rejected'][0]['reason'].lower()


def test_batch_and_participants_persisted_active(dynamodb):
    '''
        Accepted participants are persisted as ACTIVE with the institution, and a
        load batch is stored for evidence.
    '''
    file_bytes = _build_workbook([
        ['111', 'Ana', 'Lopez', '', '701', 'La Paz', 1],
    ])
    summary = load_participants_from_excel(
        dynamodb, file_bytes, 'inst-a', _RESPONSIBLE, ParticipantRole.PARTICIPANTE.value
    )

    participant = dynamodb.Table(PARTICIPANTS_TABLE).get_item(Key = {'ci': '111'})['Item']
    assert participant['status'] == ParticipantStatus.ACTIVE.value
    assert participant['institution_id'] == 'inst-a'
    assert participant['mesa_code'] == 'A1'
    assert participant['role'] == ParticipantRole.PARTICIPANTE.value
    assert summary['role'] == ParticipantRole.PARTICIPANTE.value

    batch = dynamodb.Table(LOAD_BATCHES_TABLE).get_item(
        Key = {'batch_id': summary['batch_id']})['Item']
    assert batch['responsible_name'] == 'Juana Perez'
    assert batch['accepted_count'] == 1
