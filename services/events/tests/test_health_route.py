'''
    The tables health route: only the ADMIN reads it.
'''
from fastapi.testclient import TestClient
from jose import jwt

import main
from services import security


def _bearer(**claims) -> str:
    '''An Authorization header carrying `claims`, signed like AUTH signs.'''
    token = jwt.encode(claims, security.SECRET_KEY, algorithm = security.ALGORITHM)
    return f'Bearer {token}'


class _Client:  # pylint: disable=too-few-public-methods
    '''A DynamoDB client where every table is active.'''

    def describe_table( # pylint: disable=invalid-name
        self,
        TableName: str
    ) -> dict:
        '''The table, active.'''
        return {'Table': {'TableName': TableName, 'TableStatus': 'ACTIVE'}}


def test_only_the_admin_reads_the_tables(monkeypatch):
    '''A manager is refused with a code; the ADMIN gets every table.'''
    monkeypatch.setattr(main.boto3, 'client', lambda *args, **kwargs: _Client())
    client = TestClient(main.app)
    url = f'{main.DOCS_BASE}/health/tables'
    manager = client.get(url, headers = {'Authorization': _bearer(
        email = 'gerente@acme.com', role = 'MANAGER', client = 'acme')})
    assert (manager.status_code, manager.json()['detail']) == (403, 'ROLE_NOT_ALLOWED')
    admin = client.get(url, headers = {'Authorization': _bearer(
        email = 'admin@bearsoft.com.bo', role = 'ADMIN', client = None)})
    assert admin.status_code == 200
    assert admin.json()['healthy'] is True
    assert len(admin.json()['tables']) == len(main.HEALTH_TABLE_VARS)


def test_the_portal_may_call_events_from_the_browser():
    '''The browser's preflight from the portal is answered, not refused with 405.'''
    response = TestClient(main.app).options(f'{main.DOCS_BASE}/health/tables', headers = {
        'Origin': 'https://smartdecisions.bearsoft.com.bo',
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'authorization'})
    assert response.status_code == 200
    origin = response.headers['access-control-allow-origin']
    assert origin == 'https://smartdecisions.bearsoft.com.bo'
