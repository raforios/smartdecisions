'''
    services/auth/tests/test_auth.py

    The token is the contract every other service reads: it must name the
    user, their role and the client that groups them.
'''
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

from schemas.auth import LoginRequest
from schemas.role import Role
from schemas.users import InternalUser
from routes import auth as auth_routes
from services.jwt_token import decode_access_token


def _user(
    client: str | None,
    role: Role
) -> InternalUser:
    '''
        A stored user as `authenticate_user` returns it.
    '''
    now = datetime.now(timezone.utc)
    return InternalUser(
        email = 'ana@miempresa.com', first_name = 'Ana', last_name = 'Quispe',
        client = client, role = role, status = True,
        date_register = now, date_update = now, hashed_password = 'x'
    )


def _login_payload(user: InternalUser) -> dict:
    '''
        Logs `user` in through the route and decodes the token it issues.
    '''
    async def _authenticate(
        email: str,
        password: str
    ):
        assert (email, password) == ('ana@miempresa.com', 'secreto123')
        return user

    with patch.object(auth_routes, 'authenticate_user', _authenticate):
        token = asyncio.run(auth_routes.login(
            LoginRequest(email = 'ana@miempresa.com', password = 'secreto123')
        ))
    return decode_access_token(token.access_token)


def test_token_carries_email_role_and_client():
    '''A seller of a client logs in: the three claims travel in the token.'''
    payload = _login_payload(_user('bearsoft', Role.SELLER))
    assert payload['email'] == 'ana@miempresa.com'
    assert payload['role'] == 'SELLER'
    assert payload['client'] == 'bearsoft'


def test_token_of_a_user_without_client_says_so():
    '''Accounts predating the grouping keep working: `client` is null, not missing.'''
    payload = _login_payload(_user(None, Role.REQUESTER))
    assert 'client' in payload and payload['client'] is None


def test_smartdecisions_roles_exist():
    '''MANAGER and SELLER are part of the vocabulary the services check.'''
    assert Role('MANAGER') is Role.MANAGER
    assert Role('SELLER') is Role.SELLER
