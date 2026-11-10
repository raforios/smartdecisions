'''
    Companies: stored in their own table, counted against the users table,
    never removed while they have users; the ADMIN reaches them through
    /v1/auth/companies. Needs the configuration (moto, the
    table names), so the CI leaves it out like the other configured tests.
'''
import importlib

import pytest

from core.exceptions import InvalidInputError, RegisterAlreadyExistsError
from schemas.companies import CompanyError, CompanyRequest, CompanyUpdateRequest, Sector


@pytest.fixture(name = 'companies')
def companies_fixture(monkeypatch):
    '''
        Both tables, mocked, and the modules reloaded inside the mock.

        Yields:
            module: services.companies.
    '''
    # Imported here: the CI installs neither moto nor the service's configuration.
    from moto import mock_aws  # pylint: disable=import-outside-toplevel,import-error
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'testing')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'testing')
    with mock_aws():
        import boto3  # pylint: disable=import-outside-toplevel
        from services import companies, dynamodb  # pylint: disable=import-outside-toplevel
        resource = boto3.resource('dynamodb')
        for table, key in ((dynamodb.TABLE_NAME, 'email'), (companies.COMPANIES_TABLE, 'name')):
            resource.create_table(TableName = table, BillingMode = 'PAY_PER_REQUEST',
                                  KeySchema = [{'AttributeName': key, 'KeyType': 'HASH'}],
                                  AttributeDefinitions = [{'AttributeName': key,
                                                           'AttributeType': 'S'}])
        importlib.reload(dynamodb)
        yield importlib.reload(companies)


def _add_user(client: str) -> None:
    '''A user of `client` in the mocked users table.'''
    import boto3  # pylint: disable=import-outside-toplevel
    from services import dynamodb  # pylint: disable=import-outside-toplevel
    boto3.resource('dynamodb').Table(dynamodb.TABLE_NAME).put_item(
        Item = {'email': 'ana@andina.bo', 'client': client})


def test_a_company_is_listed_with_its_users(companies) -> None:
    '''The count comes from the users whose client is the company.'''
    companies.create_company(CompanyRequest(name = 'Andina S.R.L.'))
    _add_user('Andina S.R.L.')
    listed = companies.list_companies()
    assert [(company.name, company.users, company.active) for company in listed] == [
        ('Andina S.R.L.', 1, True)]


def test_a_name_is_never_repeated(companies) -> None:
    '''The second company with the same name is refused with its code.'''
    companies.create_company(CompanyRequest(name = 'Andina S.R.L.'))
    with pytest.raises(RegisterAlreadyExistsError) as failure:
        companies.create_company(CompanyRequest(name = 'Andina S.R.L.'))
    assert failure.value.detail == CompanyError.DUPLICATE_COMPANY.value


def test_a_company_with_users_is_not_removed(companies) -> None:
    '''It is deactivated instead: its data keeps an owner.'''
    companies.create_company(CompanyRequest(name = 'Andina S.R.L.'))
    _add_user('Andina S.R.L.')
    with pytest.raises(InvalidInputError) as failure:
        companies.delete_company('Andina S.R.L.')
    assert failure.value.detail == CompanyError.COMPANY_HAS_USERS.value
    changed = companies.update_company('Andina S.R.L.', CompanyUpdateRequest(active = False))
    assert changed.active is False


def test_the_sector_and_the_invoicing_product_are_stored_and_changed(companies) -> None:
    '''Stored as codes; an update changes only what it names.'''
    created = companies.create_company(CompanyRequest(name = 'Andina S.R.L.',
                                                      sector = Sector.WHOLESALE))
    assert (created.sector, created.includes_billing) == (Sector.WHOLESALE, False)
    changed = companies.update_company('Andina S.R.L.', CompanyUpdateRequest(
        includes_billing = True))
    assert (changed.sector, changed.includes_billing) == (Sector.WHOLESALE, True)
    assert companies.get_company('Andina S.R.L.')['sector'] == 'WHOLESALE'


def test_a_user_only_gets_an_existing_active_company(companies) -> None:
    '''Unknown or inactive companies are refused with their code.'''
    with pytest.raises(InvalidInputError) as failure:
        companies.check_company_for_user('Nadie S.R.L.')
    assert failure.value.detail == CompanyError.COMPANY_NOT_FOUND.value
    companies.create_company(CompanyRequest(name = 'Andina S.R.L.'))
    companies.update_company('Andina S.R.L.', CompanyUpdateRequest(active = False))
    with pytest.raises(InvalidInputError) as failure:
        companies.check_company_for_user('Andina S.R.L.')
    assert failure.value.detail == CompanyError.COMPANY_INACTIVE.value


@pytest.fixture(name = 'admin_client')
def admin_client_fixture(
    companies,
    monkeypatch
):
    '''
        A test client acting as an ADMIN, whose controller calls the
        companies service reloaded inside the mock.

        Yields:
            TestClient: The client.
    '''
    # Imported here: the app reads the configuration on import.
    from datetime import datetime, timezone  # pylint: disable=import-outside-toplevel
    from fastapi.testclient import TestClient  # pylint: disable=import-outside-toplevel
    from controllers import companies as controller  # pylint: disable=import-outside-toplevel
    from controllers.users import get_current_admin_user  # pylint: disable=import-outside-toplevel
    from main import app  # pylint: disable=import-outside-toplevel
    from schemas.role import Role  # pylint: disable=import-outside-toplevel
    from schemas.users import UserResponse  # pylint: disable=import-outside-toplevel
    for name in ('list_companies', 'create_company', 'update_company', 'delete_company'):
        monkeypatch.setattr(controller, name, getattr(companies, name))
    now = datetime.now(timezone.utc)
    app.dependency_overrides[get_current_admin_user] = lambda: UserResponse(
        email = 'admin@bearsoft.com.bo', first_name = 'Ad', last_name = 'Min',
        client = 'BearSoft', role = Role.ADMIN, status = True,
        date_register = now, date_update = now)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_the_admin_adds_lists_and_changes_a_company(admin_client) -> None:
    '''POST answers 201 with the company, GET lists it, PATCH changes it; a repeat is 409.'''
    created = admin_client.post('/v1/auth/companies',
                                json = {'name': 'Andina S.R.L.', 'tax_id': '1020304050'})
    assert created.status_code == 201, created.text
    assert (created.json()['name'], created.json()['active']) == ('Andina S.R.L.', True)

    listed = admin_client.get('/v1/auth/companies')
    assert listed.status_code == 200
    assert [company['name'] for company in listed.json()] == ['Andina S.R.L.']

    changed = admin_client.patch('/v1/auth/companies/Andina S.R.L.', json = {'active': False})
    assert changed.status_code == 200, changed.text
    assert changed.json()['active'] is False

    repeated = admin_client.post('/v1/auth/companies', json = {'name': 'Andina S.R.L.'})
    assert repeated.status_code == 409
    assert repeated.json()['detail'] == CompanyError.DUPLICATE_COMPANY.value


def test_the_admin_removes_only_a_company_without_users(admin_client) -> None:
    '''DELETE refuses a company with users with its code and removes one without them.'''
    admin_client.post('/v1/auth/companies', json = {'name': 'Andina S.R.L.'})
    admin_client.post('/v1/auth/companies', json = {'name': 'Illimani S.A.'})
    _add_user('Andina S.R.L.')

    refused = admin_client.delete('/v1/auth/companies/Andina S.R.L.')
    assert refused.status_code == 400
    assert refused.json()['detail'] == CompanyError.COMPANY_HAS_USERS.value

    removed = admin_client.delete('/v1/auth/companies/Illimani S.A.')
    assert removed.status_code == 200, removed.text
    assert removed.json()['name'] == 'Illimani S.A.'
    assert [company['name'] for company in admin_client.get('/v1/auth/companies').json()] == [
        'Andina S.R.L.']
