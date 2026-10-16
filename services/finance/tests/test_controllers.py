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
from routes import entries as entry_routes
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
from schemas.entries import (
    EntryFileLoadSchema,
    EntryListResponseSchema,
    EntryLoadSchema,
    EntryRowSchema,
    EntrySchema,
    EntryUpdateSchema,
    LoadFlow,
    LoadListResponseSchema,
    LoadResultSchema,
    PeriodDeleteResultSchema,
    Periodicity
)
from services import entries, security


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


def test_every_entry_route_answers_its_model(
    catalog,
    monkeypatch
):
    '''Load by API and by file, list, correct and delete, called as the API calls them.'''
    who = {'dynamodb_resource': catalog, 'client': 'acme', 'current_user': 'ana@acme.com'}
    rent = {'date': '2026-03', 'periodicity': 'MONTHLY', 'account_code': '6.1.03', 'amount': 3500}
    loaded = _run(entry_routes.load_entries_endpoint(
        request = None, load = EntryLoadSchema(flow = LoadFlow.PROCESSED,
                                               rows = [EntryRowSchema(**rent)]), **who
    ))
    assert isinstance(loaded, LoadResultSchema)

    monkeypatch.setattr(entries, 'read_file_rows', lambda key, token: [
        {'Fecha': '2026-02', 'Periodicidad': 'Mensual', 'Código de cuenta': '6.1.03', 'Monto': 1}
    ])
    monkeypatch.setattr(entries, 'delete_stored_file', lambda key, token: None)
    from_file = _run(entry_routes.load_entries_file_endpoint(
        request = None, load = EntryFileLoadSchema(flow = LoadFlow.BASE, file_key = 'f.xlsx'),
        authorization = 'Bearer x', **who
    ))
    assert from_file.accepted == 1

    assert isinstance(_run(entry_routes.list_loads_endpoint(request = None, **who)),
                      LoadListResponseSchema)
    listed = _run(entry_routes.list_entries_endpoint(
        request = None, periodicity = Periodicity.MONTHLY, date = '2026', **who
    ))
    assert isinstance(listed, EntryListResponseSchema)
    assert listed.total == 2

    fixed = _run(entry_routes.update_entry_endpoint(
        request = None, update = EntryUpdateSchema(amount = 3600),
        periodicity = Periodicity.MONTHLY, date = '2026-03', account_code = '6.1.03', **who
    ))
    assert isinstance(fixed, EntrySchema)
    removed = _run(entry_routes.delete_entry_endpoint(
        request = None, periodicity = Periodicity.MONTHLY, date = '2026-03',
        account_code = '6.1.03', **who
    ))
    assert isinstance(removed, EntrySchema)
    emptied = _run(entry_routes.delete_period_endpoint(
        request = None, periodicity = Periodicity.MONTHLY, date = '2026-02', **who
    ))
    assert isinstance(emptied, PeriodDeleteResultSchema)
    assert emptied.deleted == 1


def test_a_seller_cannot_see_the_finances():
    '''«Sólo la plana mayor»: a SELLER is refused before reaching the tables.'''
    response = TestClient(app).get('/v1/finance/entries', headers = {
        'Authorization': _bearer(email = 'vendedor@acme.com', role = 'SELLER', client = 'acme')
    })
    assert response.status_code == 403
    assert response.json()['detail'] == 'ROLE_NOT_ALLOWED'
