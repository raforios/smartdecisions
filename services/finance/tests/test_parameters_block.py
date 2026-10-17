'''
    Tests for the PARAMETERS block of the boilerplate: business values read by
    HTTP, kept for a while, and never replaced by a default.
'''
from unittest.mock import Mock, patch

import pytest

from schemas.parameters import ParametersError
from services import utils
from services.exceptions import ServiceUnavailableError


def _response(
    status: int,
    payload: dict
) -> Mock:
    '''
        A stand-in for requests.Response.

        Returns:
            Mock: The response.
    '''
    return Mock(status_code = status, ok = status < 400, text = str(payload),
                json = lambda: payload)


def test_values_are_read_once_and_kept():
    '''A second read inside the cache time does not ask PARAMETERS again.'''
    utils._PARAMETERS_CACHE.clear()  # pylint: disable=protected-access
    calls = []
    body = {'parameters': [{'code': 'AMOUNT_DECIMALS', 'value': 2.0}]}
    with patch.object(utils.req, 'get', lambda *a, **k: calls.append(a) or _response(200, body)):
        assert utils.read_parameters('global', 'Bearer x') == {'AMOUNT_DECIMALS': 2.0}
        assert utils.read_parameters('global', 'Bearer x') == {'AMOUNT_DECIMALS': 2.0}
    assert len(calls) == 1


def test_a_refusal_or_a_missing_value_stops_the_request():
    '''No answer, or no value, is a code: the report never runs on a guess.'''
    utils._PARAMETERS_CACHE.clear()  # pylint: disable=protected-access
    with patch.object(utils.req, 'get', lambda *a, **k: _response(401, {})):
        with pytest.raises(ServiceUnavailableError) as failure:
            utils.read_parameters('finance', None)
    assert failure.value.detail == ParametersError.REJECTED.value
    with pytest.raises(ServiceUnavailableError) as failure:
        utils.required_parameters({'A': 1}, ('A', 'B'))
    assert failure.value.detail == ParametersError.MISSING.value
