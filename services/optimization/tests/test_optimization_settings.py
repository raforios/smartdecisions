'''
    Tests for the route parameters of a company: today, the optional base
    point routes may start or end at.
'''
import boto3
import pytest
from moto import mock_aws

from schemas.localization import RouteEndpointSchema
from schemas.optimization_settings import RouteSettingsSchema
from services import optimization_settings as settings

OWNER = 'acme'
OTHER = 'otra'


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''The settings table, mocked.'''
    with mock_aws():
        resource = boto3.resource('dynamodb', region_name = 'us-east-1')
        resource.create_table(
            TableName = settings.SETTINGS_TABLE,
            KeySchema = [{'AttributeName': 'owner_email', 'KeyType': 'HASH'}],
            AttributeDefinitions = [{'AttributeName': 'owner_email', 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
        yield resource


def test_a_company_with_no_settings_reads_them_empty(dynamodb):
    '''Never set is not an error: there is simply no base point.'''
    assert settings.get_route_settings(dynamodb, OWNER).base_point is None


def test_the_base_point_is_stored_and_is_the_company_s_own(dynamodb):
    '''Case 6 of the spec: stored, and invisible to another company.'''
    saved = settings.save_route_settings(dynamodb, OWNER, RouteSettingsSchema(
        base_point = RouteEndpointSchema(name = 'Depósito', latitude = -16.54,
                                         longitude = -68.07)
    ))
    assert saved.base_point.name == 'Depósito'
    assert saved.updated_at
    assert settings.get_route_settings(dynamodb, OTHER).base_point is None


def test_the_endpoints_save_for_management_and_read_for_the_seller(dynamodb):
    '''
        PUT is management's; GET is everybody's in the company, because the
        phone needs the base point. Exercises `save_route_settings_endpoint`
        and `get_route_settings_endpoint`.
    '''
    # pylint: disable=import-outside-toplevel
    from fastapi.testclient import TestClient

    from main import app
    from services.db_connection import GET_DB_DEPENDENCY
    from services.security import get_current_payload

    app.dependency_overrides[GET_DB_DEPENDENCY] = lambda: dynamodb
    try:
        client = TestClient(app)
        app.dependency_overrides[get_current_payload] = lambda: {
            'email': 'gerente@acme.com', 'role': 'MANAGER', 'client': OWNER}
        saved = client.put('/v1/optimization/settings', json = {'base_point': {
            'name': 'Depósito', 'latitude': -16.54, 'longitude': -68.07}})
        assert saved.status_code == 200, saved.text

        app.dependency_overrides[get_current_payload] = lambda: {
            'email': 'ana@acme.com', 'role': 'SELLER', 'client': OWNER}
        read = client.get('/v1/optimization/settings')
        assert read.json()['base_point']['name'] == 'Depósito'
        refused = client.put('/v1/optimization/settings', json = {'base_point': None})
        assert refused.status_code == 403
    finally:
        app.dependency_overrides.clear()
