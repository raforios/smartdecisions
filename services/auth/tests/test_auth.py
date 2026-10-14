'''
    services/auth/tests/test_auth.py

    GitHub Actions runs this suite with no `.env`, and every module under
    `routes/`, `controllers/` and `services/utils.py` validates the environment
    on import. So only pure schemas are exercised here; the token itself (email,
    role, client) is verified against the deployed service.
'''
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from schemas.role import Role
from schemas.users import InternalUser, PasswordChangeRequest, UserResponse
from services.sessions import company_members, login_update


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


def test_a_duplicate_caught_by_dynamodb_answers_already_registered(monkeypatch):
    '''
        Two sign-ups of one e-mail at once pass the controller's check and
        meet at the conditional write. That branch raised `ValueError` with an
        unbound `message`, which surfaced as a 500 instead of the 409.

        The environment is set before the import because CI runs without
        `.env` and `services/dynamodb.py` validates it on import.
    '''
    # pylint: disable=import-outside-toplevel
    import importlib

    from botocore.exceptions import ClientError

    monkeypatch.setenv('TABLE_NAME', 'auth-users-test')
    monkeypatch.setenv('AWS_DEFAULT_REGION', 'us-east-1')
    dynamodb = importlib.import_module('services.dynamodb')
    exceptions = importlib.import_module('services.exceptions')

    class _Table: # pylint: disable=too-few-public-methods
        '''A table whose conditional write always finds the e-mail taken.'''
        def put_item(
            self,
            **_kwargs: object
        ) -> None:
            '''Fails the condition, as DynamoDB does for an existing key.'''
            raise ClientError(
                {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'exists'}},
                'PutItem'
            )

    monkeypatch.setattr(dynamodb, 'get_table', _Table)

    with pytest.raises(exceptions.RegisterAlreadyExistsError):
        dynamodb.create_user_item({'email': 'dup@bearsoft.com.bo'})


def test_a_first_sign_in_starts_the_count_without_a_previous_one():
    '''The first sign-in has nothing before it: no previous session is written.'''
    now = datetime(2026, 10, 13, 9, 0, tzinfo = timezone.utc)
    expression, values = login_update({}, now)
    assert 'previous_login' not in expression
    assert values[':now'] == now.isoformat()
    assert values[':one'] == 1


def test_the_last_sign_in_becomes_the_previous_one():
    '''"Your last session" on the next visit is the sign-in before this one.'''
    now = datetime(2026, 10, 13, 9, 0, tzinfo = timezone.utc)
    expression, values = login_update({'last_login': '2026-10-12T18:30:00+00:00'}, now)
    assert 'previous_login = :previous' in expression
    assert values[':previous'] == '2026-10-12T18:30:00+00:00'


USERS = [
    {'email': 'gerente@andina.bo', 'client': 'andina'},
    {'email': 'vendedor@andina.bo', 'client': 'andina'},
    {'email': 'gerente@illimani.bo', 'client': 'illimani'},
    {'email': 'suelto@mail.com'},
    {'email': 'otro@mail.com'},
]


def test_a_manager_sees_only_the_users_of_their_account():
    '''Another account's users answer as if they did not exist.'''
    visible = company_members(USERS, 'gerente@andina.bo', 'andina', False)
    assert [user['email'] for user in visible] == ['gerente@andina.bo', 'vendedor@andina.bo']


def test_somebody_without_a_client_sees_only_themselves():
    '''Matching "no client" would show every unrelated user who has none.'''
    visible = company_members(USERS, 'suelto@mail.com', None, False)
    assert [user['email'] for user in visible] == ['suelto@mail.com']


def test_an_administrator_sees_every_user():
    '''The platform administrator has no client and manages them all.'''
    assert len(company_members(USERS, 'admin@bearsoft.com.bo', None, True)) == len(USERS)


def test_a_new_password_keeps_the_minimum_length():
    '''The same eight characters a sign-up requires.'''
    with pytest.raises(ValidationError):
        PasswordChangeRequest(current_password = 'Actual2026!', new_password = 'corta')


def test_a_user_never_signed_in_has_no_last_session():
    '''Users created before sign-ins were recorded read as never signed in.'''
    now = datetime.now(timezone.utc)
    user = UserResponse(email = 'yo@mi.com', first_name = 'Rafael', last_name = 'Rios',
                        role = Role.MANAGER, status = True, date_register = now, date_update = now)
    assert user.last_login is None and user.previous_login is None and user.login_count == 0
