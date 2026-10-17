'''
    Route-level tests: every PARAMETERS endpoint must return its response
    model fully built, and only an ADMIN changes a value.
'''
import asyncio

from fastapi.testclient import TestClient
from jose import jwt

from main import app
from routes import parameters as routes
from schemas.parameters import (
    ParameterListResponseSchema,
    ParameterResponseSchema,
    ParameterSchema,
    ValueType
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
        Runs a coroutine without extra plugins.

        Args:
            coroutine: The coroutine to execute.

        Returns:
            Any: Whatever the coroutine returns.
    '''
    return asyncio.run(coroutine)


def test_every_route_answers_its_model(parameters_store):
    '''Set, read a scope, read all and delete, called as the API calls them.'''
    stored = _run(routes.set_parameter_endpoint(
        request = None, parameter = ParameterSchema(value_type = ValueType.NUMBER, value = 2,
                                                    description = 'Decimales.'),
        scope = 'global', code = 'AMOUNT_DECIMALS', dynamodb_resource = parameters_store,
        current_user = 'admin'))
    assert isinstance(stored, ParameterResponseSchema)
    for listed in (
        _run(routes.scope_parameters_endpoint(request = None, scope = 'global',
                                              dynamodb_resource = parameters_store,
                                              current_user = 'acme')),
        _run(routes.all_parameters_endpoint(request = None, dynamodb_resource = parameters_store,
                                            current_user = 'admin'))
    ):
        assert isinstance(listed, ParameterListResponseSchema)
        assert listed.total == 1
    removed = _run(routes.delete_parameter_endpoint(
        request = None, scope = 'global', code = 'AMOUNT_DECIMALS',
        dynamodb_resource = parameters_store, current_user = 'admin'))
    assert isinstance(removed, ParameterResponseSchema)


def test_only_an_admin_changes_a_value():
    '''A client's MANAGER is refused before the request reaches the table.'''
    response = TestClient(app).put(
        '/v1/parameters/global/AMOUNT_DECIMALS',
        json = {'value_type': 'NUMBER', 'value': 2, 'description': 'x'},
        headers = {'Authorization': _bearer(email = 'g@acme.com', role = 'MANAGER',
                                            client = 'acme')})
    assert response.status_code == 403
    assert response.json()['detail'] == 'ROLE_NOT_ALLOWED'
