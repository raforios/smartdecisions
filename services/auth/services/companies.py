'''
    Companies: the customers of the platform, in their own table.

    The users table keeps each user's `client`; this table says which
    clients exist, with their NIT and whether they are active.
'''
from collections import Counter
from typing import Any

import boto3
from botocore.exceptions import ClientError

from schemas.companies import (
    CompanyError,
    CompanyRequest,
    CompanyResponse,
    CompanyUpdateRequest
)
from services.dynamodb import scan_all_users
from services.environment import load_and_validate_env_vars
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

ENV_VARS = load_and_validate_env_vars({'TABLE_NAME_COMPANIES': str})
COMPANIES_TABLE = ENV_VARS['TABLE_NAME_COMPANIES']



def _table() -> Any:
    '''
        The companies table, opened when used, like the users table.

        Returns:
            Any: The DynamoDB table.
    '''
    return boto3.resource('dynamodb').Table(COMPANIES_TABLE)


def _users_per_company() -> Counter:
    '''
        How many users each client has.

        Returns:
            Counter: Users by client name.
    '''
    return Counter(user.get('client') for user in scan_all_users() if user.get('client'))


def _to_response(
    item: dict[str, Any],
    users: int
) -> CompanyResponse:
    '''
        A stored company with its user count.

        Args:
            item (dict[str, Any]): The DynamoDB item.
            users (int): Its users.

        Returns:
            CompanyResponse: The company.
    '''
    return CompanyResponse(
        name = item['name'],
        tax_id = item.get('tax_id'),
        active = bool(item.get('active', True)),
        users = users,
        created_at = item['created_at'],
        updated_at = item['updated_at']
    )


def get_company(name: str) -> dict[str, Any] | None:
    '''
        One company as stored, or None.

        Args:
            name (str): Company name.

        Returns:
            dict[str, Any] | None: The item.
    '''
    return _table().get_item(Key = {'name': name}).get('Item')


def list_companies() -> list[CompanyResponse]:
    '''
        Every company, by name, with how many users each has.

        Returns:
            list[CompanyResponse]: The companies.
    '''
    items: list[dict[str, Any]] = []
    response = _table().scan()
    items.extend(response.get('Items', []))
    while 'LastEvaluatedKey' in response:
        response = _table().scan(ExclusiveStartKey = response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    users = _users_per_company()
    message = f'Listed {len(items)} companies.'
    logger.info(message)
    return sorted((_to_response(item, users[item['name']]) for item in items),
                  key = lambda company: company.name.lower())


def create_company(company: CompanyRequest) -> CompanyResponse:
    '''
        Adds a company, active.

        Args:
            company (CompanyRequest): The company.

        Returns:
            CompanyResponse: The stored company.

        Raises:
            RegisterAlreadyExistsError: DUPLICATE_COMPANY.
    '''
    now = get_current_time_gmt().isoformat()
    item = {'name': company.name.strip(), 'tax_id': company.tax_id, 'active': True,
            'created_at': now, 'updated_at': now}
    try:
        _table().put_item(Item = item, ConditionExpression = 'attribute_not_exists(#n)',
                        ExpressionAttributeNames = {'#n': 'name'})
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            raise RegisterAlreadyExistsError(
                detail = CompanyError.DUPLICATE_COMPANY.value) from error
        raise
    message = f'Company "{item["name"]}" created.'
    logger.info(message)
    return _to_response(item, 0)


def update_company(
    name: str,
    update: CompanyUpdateRequest
) -> CompanyResponse:
    '''
        Changes a company's NIT or whether it is active; never its name.

        Args:
            name (str): Company name.
            update (CompanyUpdateRequest): What changes.

        Returns:
            CompanyResponse: The company as it is now.

        Raises:
            RegisterNotFoundError: COMPANY_NOT_FOUND.
    '''
    item = get_company(name)
    if not item:
        raise RegisterNotFoundError(detail = CompanyError.COMPANY_NOT_FOUND.value)
    changes = update.model_dump(exclude_unset = True)
    item = {**item, **changes, 'updated_at': get_current_time_gmt().isoformat()}
    _table().put_item(Item = item)
    message = f'Company "{name}" updated: {sorted(changes)}.'
    logger.info(message)
    return _to_response(item, _users_per_company()[name])


def delete_company(name: str) -> CompanyResponse:
    '''
        Removes a company that has no users; one with users is deactivated
        instead, so its data keeps an owner.

        Args:
            name (str): Company name.

        Returns:
            CompanyResponse: The company removed.

        Raises:
            RegisterNotFoundError: COMPANY_NOT_FOUND.
            InvalidInputError: COMPANY_HAS_USERS.
    '''
    item = get_company(name)
    if not item:
        raise RegisterNotFoundError(detail = CompanyError.COMPANY_NOT_FOUND.value)
    users = _users_per_company()[name]
    if users:
        raise InvalidInputError(detail = CompanyError.COMPANY_HAS_USERS.value)
    _table().delete_item(Key = {'name': name})
    message = f'Company "{name}" deleted.'
    logger.info(message)
    return _to_response(item, 0)


def check_company_for_user(name: str) -> None:
    '''
        A user may only be given a company that exists and is active.

        Args:
            name (str): The client the user is being given.

        Raises:
            InvalidInputError: COMPANY_NOT_FOUND or COMPANY_INACTIVE.
    '''
    item = get_company(name)
    if not item:
        raise InvalidInputError(detail = CompanyError.COMPANY_NOT_FOUND.value)
    if not item.get('active', True):
        raise InvalidInputError(detail = CompanyError.COMPANY_INACTIVE.value)
