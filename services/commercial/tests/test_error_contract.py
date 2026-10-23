'''
    Regression test for the error contract of `handle_service_errors`.

    The decorator used to flatten our own HTTP errors into a 400 whose detail
    was `str(e)` ("409: ROUTE_CODE_ALREADY_EXISTS"). The frontend only maps a
    detail to a code when it is exactly the code, so both the status and the
    detail must survive the decorator untouched.
'''
import asyncio

import pytest
from fastapi import HTTPException

from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
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
