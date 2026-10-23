'''
    "Lo último que hiciste": each signed-in user reads only their own changes.
'''
from typing import Any

from fastapi.testclient import TestClient
from jose import jwt

import main
from services import security
from services.db_connection import GET_DB_DEPENDENCY

URL = f'{main.DOCS_BASE}/my-changes'
RECORDS = [
    {'microservice': 'FINANCE', 'timestamp': '2026-10-23T10:29:41-04:00', 'entity_name': 'Account',
     'entity_id': '6.1.98', 'action': 'CREATE', 'user_id': 'ana@acme.com'},
    {'microservice': 'FINANCE', 'timestamp': '2026-10-23T11:30:38-04:00', 'entity_name': 'Account',
     'entity_id': '6.1.98', 'action': 'DELETE', 'user_id': 'ana@acme.com'},
    {'microservice': 'QUOTES', 'timestamp': '2026-10-23T12:00:00-04:00', 'entity_name': 'Factor',
     'entity_id': '7', 'action': 'UPDATE', 'user_id': 'otro@acme.com'}
]


def _bearer(**claims: Any) -> str:
    '''An Authorization header carrying `claims`, signed like AUTH signs.'''
    token = jwt.encode(claims, security.SECRET_KEY, algorithm = security.ALGORITHM)
    return f'Bearer {token}'


class _Table:  # pylint: disable=too-few-public-methods
    '''The audit table: answers each service's query, applying the user filter.'''

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def query(
        self,
        **kwargs: Any
    ) -> dict[str, Any]:
        '''The records of the queried service, of the filtered user only.'''
        self.calls.append(kwargs)
        service = kwargs['KeyConditionExpression'].get_expression()['values'][0] \
            .get_expression()['values'][1]
        user = kwargs['FilterExpression'].get_expression()['values'][1]
        return {'Items': [record for record in RECORDS
                          if record['microservice'] == service and record['user_id'] == user]}


class _Resource:  # pylint: disable=too-few-public-methods
    '''A DynamoDB resource with the one table.'''

    def __init__(self) -> None:
        self.table = _Table()

    def Table( # pylint: disable=invalid-name
        self,
        _name: str
    ) -> _Table:
        '''The audit table.'''
        return self.table


def test_a_user_reads_only_their_own_changes_newest_first() -> None:
    '''The user comes from the token; another user's change never shows.'''
    resource = _Resource()
    main.app.dependency_overrides[GET_DB_DEPENDENCY] = lambda: resource
    try:
        response = TestClient(main.app).get(
            URL, params = {'microservices': 'FINANCE,QUOTES', 'limit': 5},
            headers = {'Authorization': _bearer(email = 'ana@acme.com', role = 'MANAGER',
                                                client = 'acme')})
    finally:
        main.app.dependency_overrides.clear()
    assert response.status_code == 200
    changes = response.json()['changes']
    assert [(change['action'], change['entity_id']) for change in changes] == [
        ('DELETE', '6.1.98'), ('CREATE', '6.1.98')]
    assert len(resource.table.calls) == 2
    assert all(call['IndexName'] == 'microservice-timestamp-index'
               for call in resource.table.calls)


def test_without_a_token_nothing_is_read() -> None:
    '''No token, no changes: 401 before touching the table.'''
    response = TestClient(main.app).get(URL, params = {'microservices': 'FINANCE'})
    assert response.status_code == 401
