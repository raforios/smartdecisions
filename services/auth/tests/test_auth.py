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

    import pytest
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
