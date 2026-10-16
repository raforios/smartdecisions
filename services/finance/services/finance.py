'''
    The financial analysis: its chart of accounts and the rates set by law.

    Both are global. Every client files its figures against the same codes and
    is taxed at the same rates, so there is one copy of each and only an ADMIN
    of BearSoft changes it: what is ours we move, what is the client's the
    client moves.

    An account never changes what it does. Its name can be corrected; its
    code and its type cannot, and it can only be removed while nothing
    depends on it.
'''
from datetime import date as date_type
from typing import Any

from boto3.dynamodb.conditions import Key
from boto3.resources.base import ServiceResource

from models.finance import AccountItem, LawParameterItem
from schemas.finance import (
    AccountListResponseSchema,
    AccountResponseSchema,
    AccountSchema,
    AccountUpdateSchema,
    FinanceError,
    LawParameterListResponseSchema,
    LawParameterResponseSchema,
    LawParameterSchema
)
from services.crud import create_item, find_item_by_key
from services.environment import load_and_validate_env_vars
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    ResourceNotFoundError
)
from services.finance_utils import scan_all, to_dynamo
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

ENV_VARS = load_and_validate_env_vars({
    'DYNAMODB_TABLE_NAME_FINANCE_ACCOUNTS': str,
    'DYNAMODB_TABLE_NAME_FINANCE_LAW_PARAMETERS': str,
    'DYNAMODB_TABLE_NAME_FINANCE_ENTRIES': str,
})
ACCOUNTS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_FINANCE_ACCOUNTS']
LAW_PARAMETERS_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_FINANCE_LAW_PARAMETERS']
ENTRIES_TABLE = ENV_VARS['DYNAMODB_TABLE_NAME_FINANCE_ENTRIES']
# The index of the amounts by account: whether any client used one.
ACCOUNT_INDEX = 'account_code-index'


def _code_key(code: str) -> list[int | str]:
    '''
        Sort key that orders 6.1.10 after 6.1.9, as a reader expects.

        Args:
            code (str): Account code, e.g. 6.1.07.

        Returns:
            list[int | str]: The segments, numeric where they are numbers.
    '''
    return [int(part) if part.isdigit() else part for part in code.split('.')]


def to_account_response(item: AccountItem | dict[str, Any]) -> AccountResponseSchema:
    '''
        Builds the response of one stored account.

        Args:
            item (AccountItem | dict[str, Any]): The stored item.

        Returns:
            AccountResponseSchema: The account.
    '''
    return AccountResponseSchema(
        account_code = item['account_code'],
        name = item['name'],
        account_type = item['account_type'],
        group_code = item.get('group_code'),
        subtracts = bool(item.get('subtracts', False)),
        invoiced = item.get('invoiced'),
        updated_at = item['updated_at']
    )


def _find_account(
    dynamodb_resource: ServiceResource,
    account_code: str
) -> dict[str, Any] | None:
    '''
        One stored account, or None.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            account_code (str): Account code.

        Returns:
            dict[str, Any] | None: The stored item.
    '''
    return find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = ACCOUNTS_TABLE,
        key = {'account_code': account_code}
    )


def _check_group(
    dynamodb_resource: ServiceResource,
    account: AccountSchema
) -> None:
    '''
        An account sits in an existing group of its own type: a Gastos
        account inside an Ingresos group would be added to the wrong line of
        every report.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            account (AccountSchema): The account to create.

        Raises:
            InvalidInputError: GROUP_NOT_FOUND or GROUP_TYPE_MISMATCH.
    '''
    if account.group_code is None:
        return
    group = _find_account(dynamodb_resource, account.group_code)
    if not group or group.get('group_code'):
        error_msg = f'Account {account.account_code}: group {account.group_code} not found.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = FinanceError.GROUP_NOT_FOUND.value)
    if group['account_type'] != account.account_type.value:
        error_msg = (f'Account {account.account_code} is type {account.account_type.value} '
                     f'but group {account.group_code} is type {group["account_type"]}.')
        logger.warning(error_msg)
        raise InvalidInputError(detail = FinanceError.GROUP_TYPE_MISMATCH.value)


def create_account(
    dynamodb_resource: ServiceResource,
    account: AccountSchema
) -> AccountResponseSchema:
    '''
        Adds an account, or a group, to the catalog.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            account (AccountSchema): The account.

        Returns:
            AccountResponseSchema: The stored account.

        Raises:
            InvalidInputError: GROUP_NOT_FOUND or GROUP_TYPE_MISMATCH.
            RegisterAlreadyExistsError: DUPLICATE_ACCOUNT_CODE.
    '''
    _check_group(dynamodb_resource, account)
    now = get_current_time_gmt().isoformat()
    item: AccountItem = {
        **account.model_dump(mode = 'json'),
        'created_at': now,
        'updated_at': now
    }
    try:
        create_item(
            dynamodb_resource = dynamodb_resource,
            table_name = ACCOUNTS_TABLE,
            item_data = dict(item),
            unique_key_attribute = 'account_code'
        )
    except RegisterAlreadyExistsError as error:
        raise RegisterAlreadyExistsError(
            detail = FinanceError.DUPLICATE_ACCOUNT_CODE.value
        ) from error
    message = f'Account {account.account_code} added to the catalog.'
    logger.info(message)
    return to_account_response(item)


def list_accounts(dynamodb_resource: ServiceResource) -> AccountListResponseSchema:
    '''
        The whole catalog, groups and accounts, ordered by code.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            AccountListResponseSchema: The catalog.
    '''
    items = scan_all(dynamodb_resource, ACCOUNTS_TABLE)
    accounts = [
        to_account_response(item)
        for item in sorted(items, key = lambda item: _code_key(item['account_code']))
    ]
    return AccountListResponseSchema(accounts = accounts, total = len(accounts))


def catalog_by_code(dynamodb_resource: ServiceResource) -> dict[str, dict[str, Any]]:
    '''
        The catalog as a lookup by code, for the validator of the loads.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            dict[str, dict[str, Any]]: Every group and account, by code.
    '''
    return {item['account_code']: item for item in scan_all(dynamodb_resource, ACCOUNTS_TABLE)}


def account_in_use(
    dynamodb_resource: ServiceResource,
    account_code: str
) -> bool:
    '''
        Whether any client filed an amount under the account. Asks the index
        for one key, whoever owns it: it answers with what is really stored.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            account_code (str): Account code.

        Returns:
            bool: True when at least one amount uses it.
    '''
    response = dynamodb_resource.Table(ENTRIES_TABLE).query(
        IndexName = ACCOUNT_INDEX,
        KeyConditionExpression = Key('account_code').eq(account_code),
        Limit = 1
    )
    return bool(response.get('Items'))


def rename_account(
    dynamodb_resource: ServiceResource,
    account_code: str,
    update: AccountUpdateSchema
) -> AccountResponseSchema:
    '''
        Corrects the name of an account. Only the text: its code, type and
        group stay, so the figures already filed under it mean the same.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            account_code (str): Account code.
            update (AccountUpdateSchema): The new name.

        Returns:
            AccountResponseSchema: The account after the change.

        Raises:
            ResourceNotFoundError: ACCOUNT_NOT_FOUND.
    '''
    stored = _find_account(dynamodb_resource, account_code)
    if not stored:
        error_msg = f'Account {account_code} not found to rename.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = FinanceError.ACCOUNT_NOT_FOUND.value)
    item = {**stored, 'name': update.name, 'updated_at': get_current_time_gmt().isoformat()}
    dynamodb_resource.Table(ACCOUNTS_TABLE).put_item(Item = to_dynamo(item))
    message = f'Account {account_code} renamed.'
    logger.info(message)
    return to_account_response(item)


def delete_account(
    dynamodb_resource: ServiceResource,
    account_code: str
) -> AccountResponseSchema:
    '''
        Removes an account no client used, or a group with no accounts left
        in it: a figure filed under a removed account would mean nothing.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            account_code (str): Account code.

        Returns:
            AccountResponseSchema: The account that was removed.

        Raises:
            ResourceNotFoundError: ACCOUNT_NOT_FOUND.
            InvalidInputError: GROUP_HAS_ACCOUNTS or ACCOUNT_IN_USE.
    '''
    stored = _find_account(dynamodb_resource, account_code)
    if not stored:
        error_msg = f'Account {account_code} not found to delete.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = FinanceError.ACCOUNT_NOT_FOUND.value)
    if not stored.get('group_code'):
        members = [
            item for item in scan_all(dynamodb_resource, ACCOUNTS_TABLE)
            if item.get('group_code') == account_code
        ]
        if members:
            error_msg = f'Group {account_code} still has {len(members)} account(s).'
            logger.warning(error_msg)
            raise InvalidInputError(detail = FinanceError.GROUP_HAS_ACCOUNTS.value)
    elif account_in_use(dynamodb_resource, account_code):
        error_msg = f'Account {account_code} has amounts loaded; it cannot be removed.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = FinanceError.ACCOUNT_IN_USE.value)
    dynamodb_resource.Table(ACCOUNTS_TABLE).delete_item(Key = {'account_code': account_code})
    message = f'Account {account_code} removed from the catalog.'
    logger.info(message)
    return to_account_response(stored)


def to_law_parameter_response(
    item: LawParameterItem | dict[str, Any]
) -> LawParameterResponseSchema:
    '''
        Builds the response of one stored law parameter value.

        Args:
            item (LawParameterItem | dict[str, Any]): The stored item.

        Returns:
            LawParameterResponseSchema: The value.
    '''
    return LawParameterResponseSchema(
        parameter_code = item['parameter_code'],
        name = item['name'],
        rate = float(item['rate']),
        valid_from = date_type.fromisoformat(item['valid_from']),
        updated_at = item['updated_at']
    )


def set_law_parameter(
    dynamodb_resource: ServiceResource,
    parameter: LawParameterSchema
) -> LawParameterResponseSchema:
    '''
        Stores the value of a law parameter from the day it applies.

        A new date adds a value and leaves the earlier ones in place, so the
        months before keep their rate. The same date again corrects that value
        instead of leaving two rates for one day.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            parameter (LawParameterSchema): The value.

        Returns:
            LawParameterResponseSchema: The stored value.
    '''
    now = get_current_time_gmt().isoformat()
    valid_from = parameter.valid_from.isoformat()
    stored = find_item_by_key(
        dynamodb_resource = dynamodb_resource,
        table_name = LAW_PARAMETERS_TABLE,
        key = {'parameter_code': parameter.parameter_code, 'valid_from': valid_from}
    ) or {}
    item: LawParameterItem = {
        **parameter.model_dump(mode = 'json'),
        'created_at': stored.get('created_at', now),
        'updated_at': now
    }
    dynamodb_resource.Table(LAW_PARAMETERS_TABLE).put_item(Item = to_dynamo(dict(item)))
    message = f'Law parameter {parameter.parameter_code} set from {valid_from}.'
    logger.info(message)
    return to_law_parameter_response(item)


def list_law_parameters(dynamodb_resource: ServiceResource) -> LawParameterListResponseSchema:
    '''
        Every value of every law parameter, ordered by code and date.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.

        Returns:
            LawParameterListResponseSchema: The values.
    '''
    items = scan_all(dynamodb_resource, LAW_PARAMETERS_TABLE)
    parameters = [
        to_law_parameter_response(item)
        for item in sorted(items, key = lambda item: (item['parameter_code'],
                                                       item['valid_from']))
    ]
    return LawParameterListResponseSchema(parameters = parameters, total = len(parameters))
