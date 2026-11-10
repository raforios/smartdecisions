'''
    The users table (DynamoDB).

    Every call goes through `_guarded`: a failure of the table is logged here
    with what DynamoDB said, and the caller receives only the code
    STORAGE_UNAVAILABLE —the table's own words are for the log, not for the
    client.
'''
from collections.abc import Callable
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from core.environment import load_and_validate_env_vars
from core.exceptions import RegisterAlreadyExistsError, ServiceUnavailableError
from core.logger_config import custom_logger as logger
from schemas.auth import AuthError

dynamodb = boto3.resource('dynamodb')

ENV_VARS = load_and_validate_env_vars({'TABLE_NAME': str})
TABLE_NAME = ENV_VARS['TABLE_NAME']


def get_table() -> Any:
    '''
        The users table.

        Returns:
            Any: The DynamoDB table.
    '''
    return dynamodb.Table(TABLE_NAME)


def _guarded(
    action: str,
    call: Callable[[], Any]
) -> Any:
    '''
        Runs one call to the table, turning a failure of DynamoDB into
        STORAGE_UNAVAILABLE.

        Args:
            action (str): What was being done, for the log.
            call (Callable[[], Any]): The call.

        Returns:
            Any: What the call returned.

        Raises:
            ServiceUnavailableError: STORAGE_UNAVAILABLE.
    '''
    try:
        return call()
    except (ClientError, BotoCoreError) as error:
        error_msg = f'DynamoDB failed while {action} in {TABLE_NAME}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = AuthError.STORAGE_UNAVAILABLE.value) from error


def create_user_item(user_data: dict[str, Any]) -> dict[str, Any]:
    '''
        Stores a new user; its e-mail is the key and must be new.

        Args:
            user_data (dict[str, Any]): The user, its e-mail as the key.

        Returns:
            dict[str, Any]: The user as stored.

        Raises:
            RegisterAlreadyExistsError: EMAIL_TAKEN.
            ServiceUnavailableError: STORAGE_UNAVAILABLE.
    '''
    email = user_data['email']

    def _put() -> None:
        get_table().put_item(Item = user_data,
                             ConditionExpression = 'attribute_not_exists(email)')

    try:
        _guarded(f'creating {email}', _put)
    except ServiceUnavailableError as error:
        cause = error.__cause__
        # The check in the service cannot see two sign-ups of one e-mail at
        # once; the condition can.
        if isinstance(cause, ClientError) \
                and cause.response['Error']['Code'] == 'ConditionalCheckFailedException':
            error_msg = f'User "{email}" already exists.'
            logger.warning(error_msg)
            raise RegisterAlreadyExistsError(detail = AuthError.EMAIL_TAKEN.value) from cause
        raise
    message = f'User "{email}" created in DynamoDB.'
    logger.info(message)
    return user_data


def get_user_by_email(email: str) -> dict[str, Any] | None:
    '''
        One user as stored, or None.

        Args:
            email (str): The user.

        Returns:
            dict[str, Any] | None: The item.

        Raises:
            ServiceUnavailableError: STORAGE_UNAVAILABLE.
    '''
    return _guarded(f'reading {email}',
                    lambda: get_table().get_item(Key = {'email': email}).get('Item'))


def update_user_item(
    email: str,
    update_expression: str,
    expression_attribute_values: dict[str, Any],
    expression_attribute_names: dict[str, str] | None = None
) -> dict[str, Any] | None:
    '''
        Applies an update to one user and returns it as it is now.

        Args:
            email (str): The user.
            update_expression (str): The DynamoDB update expression.
            expression_attribute_values (dict[str, Any]): Its values.
            expression_attribute_names (dict[str, str] | None): Its aliased
                names, for reserved words.

        Returns:
            dict[str, Any] | None: The user updated.

        Raises:
            ServiceUnavailableError: STORAGE_UNAVAILABLE.
    '''
    update_kwargs: dict[str, Any] = {
        'Key': {'email': email},
        'UpdateExpression': update_expression,
        'ExpressionAttributeValues': expression_attribute_values,
        'ReturnValues': 'ALL_NEW'
    }
    if expression_attribute_names:
        update_kwargs['ExpressionAttributeNames'] = expression_attribute_names
    updated = _guarded(f'updating {email}',
                       lambda: get_table().update_item(**update_kwargs).get('Attributes'))
    message = f'User "{email}" updated in DynamoDB.'
    logger.info(message)
    return updated


def delete_user_item(email: str) -> bool:
    '''
        Deletes one user.

        Args:
            email (str): The user.

        Returns:
            bool: Whether there was such a user.

        Raises:
            ServiceUnavailableError: STORAGE_UNAVAILABLE.
    '''
    old = _guarded(f'deleting {email}', lambda: get_table().delete_item(
        Key = {'email': email}, ReturnValues = 'ALL_OLD').get('Attributes'))
    if not old:
        error_msg = f'User "{email}" not found for deletion.'
        logger.warning(error_msg)
        return False
    message = f'User "{email}" deleted from DynamoDB.'
    logger.info(message)
    return True


def scan_all_users() -> list[dict[str, Any]]:
    '''
        Every user. A scan: the table holds the platform's users, a few dozen,
        and the admin screens and the account list read them all.

        Returns:
            list[dict[str, Any]]: The users.

        Raises:
            ServiceUnavailableError: STORAGE_UNAVAILABLE.
    '''
    def _scan() -> list[dict[str, Any]]:
        table = get_table()
        response = table.scan()
        users = response.get('Items', [])
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey = response['LastEvaluatedKey'])
            users.extend(response.get('Items', []))
        return users

    users = _guarded('scanning the users', _scan)
    message = f'Scanned {len(users)} user(s) from DynamoDB.'
    logger.info(message)
    return users
