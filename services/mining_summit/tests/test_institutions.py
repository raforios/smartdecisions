'''
    services/mining_summit/tests/test_institutions.py

    Unit tests for the DynamoDB-backed institutions catalog. The participant role
    no longer belongs to the institution. DynamoDB is mocked with moto.
'''
import boto3
import pytest
from moto import mock_aws

from schemas.enums import InstitutionCategory
from services.exceptions import RegisterAlreadyExistsError, RegisterNotFoundError
from services.institutions import (
    INSTITUTIONS_TABLE,
    create_institution,
    delete_institution,
    get_institution,
    list_institutions,
    update_institution
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


def test_list_returns_all_sorted(dynamodb):
    '''
        Listing returns every seeded institution, ordered alphabetically by name,
        and no longer carries a derived role/assignment.
    '''
    items = list_institutions(dynamodb)
    assert len(items) == len(SEED_INSTITUTIONS)
    names = [item['name'].lower() for item in items]
    assert names == sorted(names)
    assert all('role' not in item and 'assignment_type' not in item for item in items)


def test_create_update_delete_institution(dynamodb):
    '''
        A new institution can be created (id derived from name), updated and
        deleted through the CRUD helpers.
    '''
    created = create_institution(dynamodb, {
        'name': 'Nueva Minera Andina', 'category': 'ACTORES PRODUCTIVOS MINEROS',
        'cupos': 10
    })
    assert created['id'] == 'nueva-minera-andina'
    assert created['cupos'] == 10
    assert 'role' not in created  # role is no longer derived from the institution

    updated = update_institution(dynamodb, created['id'], {'cupos': 25, 'abbreviation': 'NMA'})
    assert updated['cupos'] == 25
    assert updated['abbreviation'] == 'NMA'

    delete_institution(dynamodb, created['id'])
    with pytest.raises(RegisterNotFoundError):
        get_institution(dynamodb, created['id'])


def test_create_duplicate_id_raises(dynamodb):
    '''Creating an institution whose derived id already exists must raise.'''
    with pytest.raises(RegisterAlreadyExistsError):
        create_institution(dynamodb, {
            'name': 'FENCOMIN', 'category': 'ACTORES PRODUCTIVOS MINEROS',
            'cupos': 5, 'id': 'fencomin'
        })


def test_numeric_fields_are_int_not_decimal(dynamodb):
    '''
        DynamoDB returns numbers as Decimal; the service must expose plain ints.
    '''
    fencomin = get_institution(dynamodb, 'fencomin')
    assert isinstance(fencomin['number'], int)
    assert isinstance(fencomin['cupos'], int)
    assert fencomin['cupos'] == 150


def test_filter_by_category(dynamodb):
    '''Filtering by category returns only that category's institutions.'''
    category = InstitutionCategory.ACTORES_PRODUCTIVOS.value
    items = list_institutions(dynamodb, category = category)
    assert items
    assert all(item['category'] == category for item in items)


def test_get_unknown_id_raises_not_found(dynamodb):
    '''An unknown institution id must raise RegisterNotFoundError (HTTP 404).'''
    with pytest.raises(RegisterNotFoundError):
        get_institution(dynamodb, 'this-institution-does-not-exist')
