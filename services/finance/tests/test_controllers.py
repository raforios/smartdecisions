'''
    Route-level tests: every FINANCE endpoint must return its response model
    fully built. The domain tests alone once stayed green in sibling services
    while the API answered 500, because the break was in the route.
'''
import asyncio
from datetime import date

from fastapi.testclient import TestClient
from jose import jwt

from main import app
from routes import finance as routes
from schemas.finance import (
    AccountListResponseSchema,
    AccountResponseSchema,
    AccountSchema,
    AccountType,
    AccountUpdateSchema,
    LawParameterListResponseSchema,
    LawParameterResponseSchema,
    LawParameterSchema
)
from services import security


def _bearer(**claims) -> str:
    '''
        An Authorization header carrying `claims`, signed like AUTH signs.
    '''
    token = jwt.encode(claims, security.SECRET_KEY, algorithm = security.ALGORITHM)
    return f'Bearer {token}'


def _run(coroutine):
    '''
        Runs a coroutine without extra plugins, as the domain tests do.

        Args:
            coroutine: The coroutine to execute.

        Returns:
            Any: Whatever the coroutine returns.
    '''
    return asyncio.run(coroutine)


def test_every_account_route_answers_its_model(finance_store):
    '''Create, list, rename and delete, called as the API calls them.'''
    created = _run(routes.create_account_endpoint(
        request = None,
        account = AccountSchema(account_code = '1.1', name = 'Activo corriente',
                                account_type = AccountType.ASSET),
        dynamodb_resource = finance_store, current_user = 'admin'
    ))
    assert isinstance(created, AccountResponseSchema)

    listed = _run(routes.list_accounts_endpoint(
        request = None, dynamodb_resource = finance_store, current_user = 'acme'
    ))
    assert isinstance(listed, AccountListResponseSchema)
    assert listed.total == 1

    renamed = _run(routes.rename_account_endpoint(
        request = None, update = AccountUpdateSchema(name = 'Activo circulante'),
        account_code = '1.1', dynamodb_resource = finance_store, current_user = 'admin'
    ))
    assert renamed.name == 'Activo circulante'

    deleted = _run(routes.delete_account_endpoint(
        request = None, account_code = '1.1',
        dynamodb_resource = finance_store, current_user = 'admin'
    ))
    assert isinstance(deleted, AccountResponseSchema)


def test_every_law_parameter_route_answers_its_model(finance_store):
    '''Set and list, called as the API calls them.'''
    stored = _run(routes.set_law_parameter_endpoint(
        request = None,
        parameter = LawParameterSchema(parameter_code = 'IUE', name = 'Impuesto a las Utilidades',
                                       rate = 25.0, valid_from = date(1995, 1, 1)),
        dynamodb_resource = finance_store, current_user = 'admin'
    ))
    assert isinstance(stored, LawParameterResponseSchema)

    listed = _run(routes.list_law_parameters_endpoint(
        request = None, dynamodb_resource = finance_store, current_user = 'acme'
    ))
    assert isinstance(listed, LawParameterListResponseSchema)
    assert listed.parameters[0].rate == 25.0


def test_a_manager_cannot_change_what_is_global():
    '''
        The catalog and the law are BearSoft's: a client's MANAGER is refused
        before the request reaches the tables, and an ADMIN is not.
    '''
    client = TestClient(app)
    body = {'account_code': '1.1', 'name': 'Activo corriente', 'account_type': '1'}
    for path, payload in (('/v1/finance/accounts', body),
                          ('/v1/finance/law-parameters',
                           {'parameter_code': 'IVA', 'name': 'IVA', 'rate': 13,
                            'valid_from': '1992-01-01'})):
        response = client.post(path, json = payload, headers = {
            'Authorization': _bearer(email = 'gerente@acme.com', role = 'MANAGER',
                                     client = 'acme')
        })
        assert response.status_code == 403
        assert response.json()['detail'] == 'ROLE_NOT_ALLOWED'
