'''
    Financial analysis — orchestration.

    Every change to the catalog or to a law rate is audited: a rate that moved
    every client's taxes is a number somebody typed, and it has to be possible
    to say who.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.finance import (
    AccountListResponseSchema,
    AccountResponseSchema,
    AccountSchema,
    AccountUpdateSchema,
    LawParameterListResponseSchema,
    LawParameterResponseSchema,
    LawParameterSchema
)
from services.finance import (
    create_account,
    delete_account,
    list_accounts,
    list_law_parameters,
    rename_account,
    set_law_parameter
)
from services.utils import audit_event, handle_service_errors


@handle_service_errors('FINANCE')
@audit_event('FINANCE', 'Account', 'CREATE', id_field = 'account_code')
async def create_account_controller(
    dynamodb_resource: ServiceResource,
    account: AccountSchema,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> AccountResponseSchema:
    '''
        Adds an account to the catalog.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            account (AccountSchema): The account.
            current_user (str): The ADMIN making the change, read by the decorators for the audit.
            request (Request): Incoming request, used by the decorators.

        Returns:
            AccountResponseSchema: The stored account.
    '''
    return create_account(dynamodb_resource = dynamodb_resource, account = account)


@handle_service_errors('FINANCE')
async def list_accounts_controller(
    dynamodb_resource: ServiceResource,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> AccountListResponseSchema:
    '''
        The whole catalog.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            current_user (str): Authenticated caller, used by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            AccountListResponseSchema: The catalog.
    '''
    return list_accounts(dynamodb_resource = dynamodb_resource)


@handle_service_errors('FINANCE')
@audit_event('FINANCE', 'Account', 'UPDATE', id_field = 'account_code')
async def rename_account_controller(
    dynamodb_resource: ServiceResource,
    account_code: str,
    update: AccountUpdateSchema,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> AccountResponseSchema:
    '''
        Corrects the name of an account.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            account_code (str): Account code.
            update (AccountUpdateSchema): The new name.
            current_user (str): The ADMIN making the change, read by the decorators for the audit.
            request (Request): Incoming request, used by the decorators.

        Returns:
            AccountResponseSchema: The account after the change.
    '''
    return rename_account(
        dynamodb_resource = dynamodb_resource,
        account_code = account_code,
        update = update
    )


@handle_service_errors('FINANCE')
@audit_event('FINANCE', 'Account', 'DELETE', id_field = 'account_code')
async def delete_account_controller(
    dynamodb_resource: ServiceResource,
    account_code: str,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> AccountResponseSchema:
    '''
        Removes an account from the catalog.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            account_code (str): Account code.
            current_user (str): The ADMIN making the change, read by the decorators for the audit.
            request (Request): Incoming request, used by the decorators.

        Returns:
            AccountResponseSchema: The account that was removed.
    '''
    return delete_account(dynamodb_resource = dynamodb_resource, account_code = account_code)


@handle_service_errors('FINANCE')
@audit_event('FINANCE', 'LawParameter', 'UPDATE', id_field = 'parameter_code')
async def set_law_parameter_controller(
    dynamodb_resource: ServiceResource,
    parameter: LawParameterSchema,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> LawParameterResponseSchema:
    '''
        Stores the value of a law parameter from the day it applies.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            parameter (LawParameterSchema): The value.
            current_user (str): The ADMIN making the change, read by the decorators for the audit.
            request (Request): Incoming request, used by the decorators.

        Returns:
            LawParameterResponseSchema: The stored value.
    '''
    return set_law_parameter(dynamodb_resource = dynamodb_resource, parameter = parameter)


@handle_service_errors('FINANCE')
async def list_law_parameters_controller(
    dynamodb_resource: ServiceResource,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> LawParameterListResponseSchema:
    '''
        Every value of every law parameter.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            current_user (str): Authenticated caller, used by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            LawParameterListResponseSchema: The values.
    '''
    return list_law_parameters(dynamodb_resource = dynamodb_resource)
