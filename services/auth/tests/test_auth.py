'''
    services/auth/tests/test_auth.py

    GitHub Actions runs this suite with no `.env`, and every module under
    `routes/`, `controllers/` and `services/utils.py` validates the environment
    on import. So only pure schemas are exercised here; the token itself (email,
    role, client) is verified against the deployed service.
'''
from datetime import datetime, timezone

from schemas.role import Role
from schemas.users import InternalUser, UserResponse


def test_smartdecisions_roles_exist():
    '''MANAGER and SELLER are part of the vocabulary the services check.'''
    assert Role('MANAGER') is Role.MANAGER
    assert Role('SELLER') is Role.SELLER
    assert Role('REQUESTER') is Role.REQUESTER


def test_user_schemas_carry_the_client_that_groups_them():
    '''`client` is optional, travels in the response and defaults to none.'''
    now = datetime.now(timezone.utc)
    grouped = InternalUser(
        email = 'ana@acme.com', first_name = 'Ana', last_name = 'Quispe',
        client = 'acme', role = Role.SELLER, status = True,
        date_register = now, date_update = now, hashed_password = 'x'
    )
    alone = UserResponse(
        email = 'yo@mi.com', first_name = 'Rafael', last_name = 'Rios',
        role = Role.REQUESTER, status = True, date_register = now, date_update = now
    )
    assert grouped.client == 'acme' and grouped.role is Role.SELLER
    assert alone.client is None
