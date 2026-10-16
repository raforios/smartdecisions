'''
    Financial analysis — HTTP layer.

    The catalog and the law rates are read by every client and changed only
    by an ADMIN of BearSoft: what is ours we move, what is the client's the
    client moves.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path as PathParam, Request, status

from controllers.finance import (
    create_account_controller,
    delete_account_controller,
    list_accounts_controller,
    list_law_parameters_controller,
    rename_account_controller,
    set_law_parameter_controller
)
from schemas.finance import (
    AccountListResponseSchema,
    AccountResponseSchema,
    AccountSchema,
    AccountUpdateSchema,
    LawParameterListResponseSchema,
    LawParameterResponseSchema,
    LawParameterSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner, require_roles

router = APIRouter(prefix = '/v1/finance', tags = ['Financial analysis'])

# A FastAPI endpoint declares its dependencies as parameters —resource, caller,
# body— so the five-argument budget does not describe it.
# pylint: disable=too-many-arguments, too-many-positional-arguments

# What is global or set by law is changed only by BearSoft (Rafael, 15-oct).
GLOBAL_EDITORS = ('ADMIN',)

_ACCOUNT_CODE = PathParam(..., min_length = 1, max_length = 20)


@router.get(
    '/accounts',
    response_model = AccountListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The chart of accounts',
    description = 'Groups and accounts, ordered by code. The same for every client.'
)
async def list_accounts_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> AccountListResponseSchema:
    '''
        Endpoint listing the catalog.
    '''
    message = f'User: {current_user}. Reading the chart of accounts.'
    logger.info(message)
    return await list_accounts_controller(
        dynamodb_resource = dynamodb_resource,
        current_user = current_user,
        request = request
    )


@router.post(
    '/accounts',
    response_model = AccountResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Add an account to the catalog (ADMIN)',
    description = (
        'A group has no `group_code`; an account points to an existing group '
        'of its own type.'
    )
)
async def create_account_endpoint(
    request: Request,
    account: AccountSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*GLOBAL_EDITORS))
) -> AccountResponseSchema:
    '''
        Endpoint adding an account.
    '''
    message = f'User: {current_user}. Adding account {account.account_code}.'
    logger.info(message)
    return await create_account_controller(
        dynamodb_resource = dynamodb_resource,
        account = account,
        current_user = current_user,
        request = request
    )


@router.patch(
    '/accounts/{account_code}',
    response_model = AccountResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Rename an account (ADMIN)',
    description = 'Only the name changes; the code, the type and the group stay.'
)
async def rename_account_endpoint(
    request: Request,
    update: AccountUpdateSchema,
    account_code: str = _ACCOUNT_CODE,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*GLOBAL_EDITORS))
) -> AccountResponseSchema:
    '''
        Endpoint renaming an account.
    '''
    message = f'User: {current_user}. Renaming account {account_code}.'
    logger.info(message)
    return await rename_account_controller(
        dynamodb_resource = dynamodb_resource,
        account_code = account_code,
        update = update,
        current_user = current_user,
        request = request
    )


@router.delete(
    '/accounts/{account_code}',
    response_model = AccountResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Remove an account from the catalog (ADMIN)',
    description = 'A group can only be removed once it has no accounts.'
)
async def delete_account_endpoint(
    request: Request,
    account_code: str = _ACCOUNT_CODE,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*GLOBAL_EDITORS))
) -> AccountResponseSchema:
    '''
        Endpoint removing an account.
    '''
    message = f'User: {current_user}. Removing account {account_code}.'
    logger.info(message)
    return await delete_account_controller(
        dynamodb_resource = dynamodb_resource,
        account_code = account_code,
        current_user = current_user,
        request = request
    )


@router.get(
    '/law-parameters',
    response_model = LawParameterListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The rates set by law, with the day each one applies from',
    description = 'Every value of every parameter, so a past month can be explained.'
)
async def list_law_parameters_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> LawParameterListResponseSchema:
    '''
        Endpoint listing the law parameters.
    '''
    message = f'User: {current_user}. Reading the law parameters.'
    logger.info(message)
    return await list_law_parameters_controller(
        dynamodb_resource = dynamodb_resource,
        current_user = current_user,
        request = request
    )


@router.post(
    '/law-parameters',
    response_model = LawParameterResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Set a rate from the day it applies (ADMIN)',
    description = (
        'A new date adds a value and keeps the earlier ones; the same date '
        'again corrects that value.'
    )
)
async def set_law_parameter_endpoint(
    request: Request,
    parameter: LawParameterSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*GLOBAL_EDITORS))
) -> LawParameterResponseSchema:
    '''
        Endpoint setting a law parameter.
    '''
    message = (f'User: {current_user}. Setting {parameter.parameter_code} '
               f'from {parameter.valid_from}.')
    logger.info(message)
    return await set_law_parameter_controller(
        dynamodb_resource = dynamodb_resource,
        parameter = parameter,
        current_user = current_user,
        request = request
    )
