'''
    The usage log and the audit record reach EVENTS before the answer leaves
    (Rafael, 19-oct-2026). In Lambda the function freezes as soon as it
    answers, and a send left as a background task could die unsent: a report
    of the 19th never reached EVENTS that way.

    asyncio.run cancels whatever is still pending when the call ends, as the
    frozen Lambda would; a send that was only scheduled is never recorded.
'''
import asyncio
from typing import Any
from unittest.mock import patch

from jose import jwt
from starlette.requests import Request

from services import utils


def _request(token: str = 'token') -> Request:
    '''
        A GET request as the API receives it, with a caller token.

        Args:
            token (str): The bearer token the caller sends.

        Returns:
            Request: The request.
    '''
    return Request({'type': 'http', 'method': 'GET', 'path': '/v1/finance/report',
                    'headers': [(b'authorization', f'Bearer {token}'.encode())],
                    'client': ('10.0.0.1', 1234), 'query_string': b'',
                    'server': ('api.bearsoft.com.bo', 443), 'scheme': 'https'})


def _recorder(sent: list[dict[str, Any]]):
    '''
        A stand-in for a send to EVENTS that records what it would post.

        Args:
            sent (list[dict[str, Any]]): Where the posted records are kept.

        Returns:
            Callable: The async stand-in.
    '''
    async def _send(
        data: dict[str, Any],
        authorization: str | None = None
    ) -> None:
        await asyncio.sleep(0)
        sent.append({'data': data, 'authorization': authorization})
    return _send


def test_usage_log_is_sent_before_answering() -> None:
    '''The controller's usage log is posted inside the call, with the caller's token.'''
    sent: list[dict[str, Any]] = []

    @utils.handle_service_errors('FINANCE')
    async def controller(
        request: Request,
        current_user: str
    ) -> dict[str, str]:
        return {'owner': current_user, 'path': request.url.path}

    with patch.object(utils, 'send_usage_log', _recorder(sent)):
        answer = asyncio.run(controller(request = _request(), current_user = 'acme'))
    assert answer == {'owner': 'acme', 'path': '/v1/finance/report'}
    assert len(sent) == 1
    assert sent[0]['data']['endpoint'] == '/v1/finance/report'
    assert sent[0]['authorization'] == 'Bearer token'


def test_audit_is_sent_before_answering() -> None:
    '''A change is audited inside the call: who, which entity and how.'''
    sent: list[dict[str, Any]] = []

    @utils.audit_event('FINANCE', 'Entry', 'UPDATE')
    async def controller(
        request: Request,  # pylint: disable=unused-argument
        current_user: str
    ) -> dict[str, str]:
        return {'id': 'MONTHLY#2026-09#1.1.01', 'owner': current_user}

    with patch.object(utils, 'send_audit_event', _recorder(sent)):
        asyncio.run(controller(request = _request(), current_user = 'acme'))
    assert len(sent) == 1
    record = sent[0]['data']
    assert (record['microservice'], record['entity_name'], record['action'],
            record['user_id']) == ('FINANCE', 'Entry', 'UPDATE', 'acme')
    assert sent[0]['authorization'] == 'Bearer token'


def test_audit_records_the_field_that_identifies_the_entity() -> None:
    '''An account is identified by its code, not by the "0" placeholder.'''
    sent: list[dict[str, Any]] = []

    @utils.audit_event('FINANCE', 'Account', 'CREATE', id_field = 'account_code')
    async def controller(
        request: Request,  # pylint: disable=unused-argument
        current_user: str  # pylint: disable=unused-argument
    ) -> dict[str, str]:
        return {'account_code': '6.1.99', 'name': 'Prueba'}

    with patch.object(utils, 'send_audit_event', _recorder(sent)):
        asyncio.run(controller(request = _request(), current_user = 'acme'))
    assert sent[0]['data']['entity_id'] == '6.1.99'


def test_the_logs_record_who_signed_in_not_the_company() -> None:
    '''
        The user is the e-mail in the token, never the company that owns the
        data (Rafael, 23-oct-2026): by the user we know the company.
    '''
    audits: list[dict[str, Any]] = []
    usage: list[dict[str, Any]] = []
    token = jwt.encode({'email': 'gerente@acme.com', 'role': 'MANAGER', 'client': 'Acme S.R.L.'},
                       'any-secret', algorithm = 'HS256')

    @utils.handle_service_errors('FINANCE')
    @utils.audit_event('FINANCE', 'Account', 'UPDATE', id_field = 'account_code')
    async def controller(
        request: Request,  # pylint: disable=unused-argument
        current_user: str  # pylint: disable=unused-argument
    ) -> dict[str, str]:
        return {'account_code': '6.1.99'}

    with patch.object(utils, 'send_audit_event', _recorder(audits)), \
         patch.object(utils, 'send_usage_log', _recorder(usage)):
        asyncio.run(controller(request = _request(token), current_user = 'Acme S.R.L.'))
    assert audits[0]['data']['user_id'] == 'gerente@acme.com'
    assert usage[0]['data']['user_app'] == 'gerente@acme.com'
