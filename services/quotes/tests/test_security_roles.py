'''
    Tests for the role and client claims `services.security` reads from the
    token: the owner key falls back to the email, and `require_roles` lets the
    allowed roles through under that key and refuses the rest with a code.
'''
import asyncio

import pytest
from jose import jwt

from services import security
from services.exceptions import ForbiddenError, UnauthorizedError


def _bearer(**claims) -> str:
    '''
        An Authorization header carrying `claims`, signed like AUTH signs.
    '''
    token = jwt.encode(claims, security.SECRET_KEY, algorithm = security.ALGORITHM)
    return f'Bearer {token}'


def test_get_current_payload_returns_the_claims_or_refuses():
    '''Valid token: every claim; missing token: the same refusal as get_current_user.'''
    header = _bearer(email = 'ana@acme.com', role = 'SELLER', client = 'acme')
    payload = asyncio.run(security.get_current_payload(header))
    assert payload['email'] == 'ana@acme.com'
    assert (payload['role'], payload['client']) == ('SELLER', 'acme')
    with pytest.raises(UnauthorizedError):
        asyncio.run(security.get_current_payload(None))


def test_resolve_owner_prefers_the_client_and_falls_back_to_the_email():
    '''Grouped users share the client; accounts without one keep their email.'''
    assert security.resolve_owner({'email': 'ana@acme.com', 'client': 'acme'}) == 'acme'
    assert security.resolve_owner({'email': 'yo@mi.com', 'client': None}) == 'yo@mi.com'
    assert security.resolve_owner({'email': 'yo@mi.com'}) == 'yo@mi.com'


def test_require_roles_lets_allowed_roles_through_under_the_owner_key():
    '''Allowed: the owner key comes back; refused: ForbiddenError with a bare code.'''
    checker = security.require_roles('ADMIN', 'MANAGER')
    owner = asyncio.run(checker(
        {'email': 'gerente@acme.com', 'role': 'MANAGER', 'client': 'acme'}
    ))
    assert owner == 'acme'
    with pytest.raises(ForbiddenError) as failure:
        asyncio.run(checker({'email': 'ana@acme.com', 'role': 'SELLER', 'client': 'acme'}))
    assert failure.value.detail == 'ROLE_NOT_ALLOWED'
