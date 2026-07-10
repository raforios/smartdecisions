'''
    services/mining_summit/tests/test_institutions.py

    Unit tests for the DynamoDB-backed institutions catalog and the
    category-to-role resolution rules. DynamoDB is mocked with moto.
'''
import boto3
import pytest
from moto import mock_aws

from schemas.enums import (
    AssignmentType,
    InstitutionCategory,
    ParticipantRole
)
from services.exceptions import RegisterNotFoundError
from services.institutions import (
    INSTITUTIONS_TABLE,
    get_institution,
    list_institutions
)
from services.summit_rules import (
    CATEGORY_ROLE_MAP,
    ROLE_ASSIGNMENT_MAP,
    resolve_assignment_type,
    resolve_role
)

# Representative seed covering every role/assignment case.
SEED_INSTITUTIONS = [
    {'id': 'fencomin', 'number': 6, 'name': 'FENCOMIN', 'abbreviation': 'FENCOMIN',
     'category': 'ACTORES PRODUCTIVOS MINEROS', 'cupos': 150},
    {'id': 'comibol', 'number': 37, 'name': 'COMIBOL', 'abbreviation': 'COMIBOL',
     'category': 'INSTITUCIONES PÚBLICAS - NIVEL CENTRAL', 'cupos': 15},
    {'id': 'umsa', 'number': 70, 'name': 'Universidad Mayor de San Andrés',
     'category': 'SECTOR ACADÉMICO Y DE INVESTIGACIÓN', 'cupos': 2},
    {'id': 'gob-oruro', 'number': 24, 'name': 'Gobernación de Oruro',
     'category': 'GOBIERNOS AUTÓNOMOS DEPARTAMENTALES', 'cupos': 2},
    {'id': 'min-mineria', 'number': 66, 'name': 'Ministerio de Minería y Metalurgia',
     'category': 'ORGANIZADOR / ENTE RECTOR', 'cupos': 40}
]


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''Provides a moto-mocked DynamoDB resource with a seeded catalog.'''
    with mock_aws():
        resource = boto3.resource('dynamodb', region_name = 'us-east-1')
        resource.create_table(
            TableName = INSTITUTIONS_TABLE,
            KeySchema = [{'AttributeName': 'id', 'KeyType': 'HASH'}],
            AttributeDefinitions = [{'AttributeName': 'id', 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
        table = resource.Table(INSTITUTIONS_TABLE)
        for item in SEED_INSTITUTIONS:
            table.put_item(Item = item)
        yield resource


def test_list_returns_all_enriched_and_sorted(dynamodb):
    '''
        Listing returns every seeded institution enriched with role and
        assignment, ordered by the matrix number.
    '''
    items = list_institutions(dynamodb)
    assert len(items) == len(SEED_INSTITUTIONS)
    assert [item['number'] for item in items] == sorted(item['number'] for item in items)
    assert all(item['role'] and item['assignment_type'] for item in items)


def test_numeric_fields_are_int_not_decimal(dynamodb):
    '''
        DynamoDB returns numbers as Decimal; the service must expose plain ints.
    '''
    fencomin = get_institution(dynamodb, 'fencomin')
    assert isinstance(fencomin['number'], int)
    assert isinstance(fencomin['cupos'], int)
    assert fencomin['cupos'] == 150


def test_role_and_assignment_derivation(dynamodb):
    '''
        A productive-actor institution is PARTICIPANTE/FIJO; academia is
        VEEDOR/ROTATIVO.
    '''
    fencomin = get_institution(dynamodb, 'fencomin')
    assert fencomin['role'] == ParticipantRole.PARTICIPANTE.value
    assert fencomin['assignment_type'] == AssignmentType.FIJO.value

    umsa = get_institution(dynamodb, 'umsa')
    assert umsa['role'] == ParticipantRole.VEEDOR.value
    assert umsa['assignment_type'] == AssignmentType.ROTATIVO.value


def test_filter_by_category(dynamodb):
    '''Filtering by category returns only that category's institutions.'''
    category = InstitutionCategory.ACTORES_PRODUCTIVOS.value
    items = list_institutions(dynamodb, category = category)
    assert items
    assert all(item['category'] == category for item in items)


def test_filter_by_role(dynamodb):
    '''Filtering by role returns only institutions with that derived role.'''
    items = list_institutions(dynamodb, role = ParticipantRole.ORGANIZADOR.value)
    assert items
    assert all(item['role'] == ParticipantRole.ORGANIZADOR.value for item in items)


def test_get_unknown_id_raises_not_found(dynamodb):
    '''An unknown institution id must raise RegisterNotFoundError (HTTP 404).'''
    with pytest.raises(RegisterNotFoundError):
        get_institution(dynamodb, 'this-institution-does-not-exist')


def test_every_category_maps_to_a_role_and_assignment():
    '''
        The rule maps must be exhaustive over categories and roles so no
        institution can end up without a resolved role/assignment.
    '''
    assert set(CATEGORY_ROLE_MAP) == set(InstitutionCategory)
    assert set(ROLE_ASSIGNMENT_MAP) == set(ParticipantRole)


def test_resolvers_are_consistent_with_maps():
    '''The resolver helpers must agree with the underlying reference maps.'''
    role = resolve_role(InstitutionCategory.ORGANO_LEGISLATIVO)
    assert role is ParticipantRole.MODERADOR
    assert resolve_assignment_type(role) is AssignmentType.FIJO
