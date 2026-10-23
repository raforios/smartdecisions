'''
    Regression test for the error contract of `handle_service_errors`.

    The decorator used to flatten our own HTTP errors into a 400 whose detail
    was `str(e)` ("409: ROUTE_CODE_ALREADY_EXISTS"). The frontend only maps a
    detail to a code when it is exactly the code, so both the status and the
    detail must survive the decorator untouched.
'''
import asyncio
from typing import Any
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from services import utils
from services.utils import handle_service_errors


@pytest.mark.parametrize('error, status', [
    (InvalidInputError, 400),
    (RegisterNotFoundError, 404),
    (RegisterAlreadyExistsError, 409)
])
def test_handle_service_errors_keeps_status_and_code(
    error,
    status
):
    '''Each of our errors leaves with its own status and the bare code.'''
    @handle_service_errors('TEST')
    async def failing_controller(
        request,
        current_user
    ): # pylint: disable=unused-argument
        raise error(detail = 'SOME_STABLE_CODE')

    with pytest.raises(HTTPException) as failure:
        asyncio.run(failing_controller(request = None, current_user = 'tester'))
    assert failure.value.status_code == status
    assert failure.value.detail == 'SOME_STABLE_CODE'


def test_the_callers_token_travels_to_events(monkeypatch: pytest.MonkeyPatch) -> None:
    '''
        EVENTS validates a token on every write, because its POST endpoints
        are reachable from the internet. The token is the one this service
        already validated for the request it is logging.
    '''
    sent: list = []

    def _post(
        url: str,
        **kwargs: Any
    ) -> Mock:
        sent.append((url, kwargs.get('headers')))
        return Mock(status_code = 201, text = '')

    monkeypatch.setattr(utils.req, 'post', _post)
    request = Mock(headers = {'authorization': 'Bearer del-usuario'})
    asyncio.run(utils.send_audit_event({'action': 'TEST'}, utils._caller_authorization(request))) # pylint: disable=protected-access
    asyncio.run(utils.send_usage_log({'endpoint': '/x'}, None))

    assert sent[0][0].endswith('/v1/events/audit')
    assert sent[0][1] == {'Authorization': 'Bearer del-usuario'}
    # A call with no request has nothing to forward and sends no header.
    assert sent[1][1] is None
