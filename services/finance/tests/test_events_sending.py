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

from starlette.requests import Request

from services import utils


def _request() -> Request:
    '''
        A GET request as the API receives it, with a caller token.

        Returns:
            Request: The request.
    '''
    return Request({'type': 'http', 'method': 'GET', 'path': '/v1/finance/report',
                    'headers': [(b'authorization', b'Bearer token')],
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
