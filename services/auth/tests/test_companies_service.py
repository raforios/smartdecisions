'''
    Companies: stored in their own table, counted against the users table,
    never removed while they have users. Needs the configuration (moto, the
    table names), so the CI leaves it out like the other configured tests.
'''
import importlib

import pytest

from schemas.companies import CompanyError, CompanyRequest, CompanyUpdateRequest
from services.exceptions import InvalidInputError, RegisterAlreadyExistsError


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
