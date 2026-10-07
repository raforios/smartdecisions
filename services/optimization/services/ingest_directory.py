'''
    What OPTIMIZATION asks INGEST, which owns every piece of data that comes in.

    One place for the call, so the stock of the day and the seller directory
    fail the same way: the caller's token is forwarded —INGEST answers for the
    real user and applies its own ownership rule— and an INGEST that cannot be
    reached is a stable code, never a hang or a half answer.
'''
from typing import Any

import requests

from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger

_SETTINGS = load_and_validate_env_vars({
    'INGEST_SERVICE_URL': str,
    'INGEST_REQUEST_TIMEOUT_SECONDS': int
})
INGEST_SERVICE_URL = _SETTINGS['INGEST_SERVICE_URL'].rstrip('/')
INGEST_REQUEST_TIMEOUT_SECONDS = _SETTINGS['INGEST_REQUEST_TIMEOUT_SECONDS']

# Code answered when INGEST cannot tell who a seller is.
SELLERS_UNAVAILABLE = 'SELLERS_UNAVAILABLE'


def ingest_get(
    path: str,
    auth_token: str,
    params: dict[str, Any] | None,
    unavailable_code: str
) -> requests.Response:
    '''
        GET against INGEST as the caller.

        A 4xx is returned for the caller to read —a missing day is an answer,
        not an outage—; a network error or a 5xx raises.

        Args:
            path (str): Path under the INGEST base URL, starting with '/'.
            auth_token (str): The caller's Authorization header.
            params (dict[str, Any] | None): Query string.
            unavailable_code (str): Code to answer when INGEST cannot be used.

        Returns:
            requests.Response: The answer, status below 500.

        Raises:
            ServiceUnavailableError: `unavailable_code`, on network error or 5xx.
    '''
    try:
        response = requests.get(
            f'{INGEST_SERVICE_URL}{path}',
            headers = {'Authorization': auth_token},
            params = params,
            timeout = INGEST_REQUEST_TIMEOUT_SECONDS
        )
    except requests.exceptions.RequestException as error:
        error_msg = f'Network error asking INGEST for {path}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = unavailable_code) from error

    if response.status_code >= 500:
        error_msg = (f'INGEST failed on {path}: status={response.status_code} '
                     f'body={response.text[:200]}')
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = unavailable_code)
    return response


def users_of_seller(
    seller: str,
    auth_token: str
) -> set[str]:
    '''
        The user emails a seller of the files signs in as.

        A plan names the seller the way the file does ("Ana"); the phone that
        runs it reports with the email it signed in with. The seller master in
        INGEST is where a manager said they are the same person.

        Args:
            seller (str): The seller as the files write it.
            auth_token (str): The caller's Authorization header.

        Returns:
            set[str]: Linked emails, lower case; empty when nobody is linked.

        Raises:
            ServiceUnavailableError: SELLERS_UNAVAILABLE when INGEST cannot answer.
    '''
    response = ingest_get('/v1/ingest/sellers', auth_token, None, SELLERS_UNAVAILABLE)
    if not response.ok:
        error_msg = (f'INGEST refused the seller master: status={response.status_code} '
                     f'body={response.text[:200]}')
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = SELLERS_UNAVAILABLE)
    return {
        str(item['user_email']).lower()
        for item in (response.json() or {}).get('sellers') or []
        if item.get('id') == seller and item.get('user_email')
    }
