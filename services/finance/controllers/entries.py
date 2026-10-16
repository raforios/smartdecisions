'''
    What a client loads — orchestration.

    Loads, corrections and deletions are changes, so they are audited: a
    figure that moved a report is a number somebody typed, and it has to be
    possible to say who.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.entries import (
    EntryFileLoadSchema,
    EntryListResponseSchema,
    EntryLoadSchema,
    EntrySchema,
    EntryUpdateSchema,
    LoadListResponseSchema,
    LoadResultSchema,
    PeriodDeleteResultSchema,
    Periodicity
)
from services.entries import (
    delete_entry,
    delete_period,
    list_entries,
    list_loads,
    load_entries,
    load_entries_from_file,
    update_entry
)
from services.utils import audit_event, handle_service_errors

# Besides its own input, a controller receives what the decorators read
# —current_user for the audit, request for the usage log— so two of them pass
# the five-argument budget without carrying more than they need.
# pylint: disable=too-many-arguments, too-many-positional-arguments


@handle_service_errors('FINANCE')
@audit_event('FINANCE', 'Load', 'CREATE')
async def load_entries_controller(
    dynamodb_resource: ServiceResource,
    load: EntryLoadSchema,
    client: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> LoadResultSchema:
    '''
        A load pushed by API.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            load (EntryLoadSchema): The flow and the rows.
            client (str): The owner of the data, from the token.
            current_user (str): The user loading, recorded and audited.
            request (Request): Incoming request, used by the decorators.

        Returns:
            LoadResultSchema: What went in and what was set aside.
    '''
    return load_entries(dynamodb_resource, client, current_user, load.flow, load.rows)


@handle_service_errors('FINANCE')
@audit_event('FINANCE', 'Load', 'CREATE')
async def load_entries_file_controller(
    dynamodb_resource: ServiceResource,
    load: EntryFileLoadSchema,
    client: str,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> LoadResultSchema:
    '''
        A load from a file uploaded through FILES.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            load (EntryFileLoadSchema): The flow and the file key.
            client (str): The owner of the data, from the token.
            current_user (str): The user loading, recorded and audited.
            auth_token (str): The caller's Authorization header, for FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            LoadResultSchema: What went in and what was set aside.
    '''
    return load_entries_from_file(dynamodb_resource, client, current_user,
                                  (load.flow, load.file_key), auth_token)


@handle_service_errors('FINANCE')
async def list_loads_controller(
    dynamodb_resource: ServiceResource,
    client: str,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> LoadListResponseSchema:
    '''
        The loads of the client.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            client (str): The owner of the data, from the token.
            current_user (str): The user, read by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            LoadListResponseSchema: The history, newest first.
    '''
    return list_loads(dynamodb_resource, client)


@handle_service_errors('FINANCE')
async def list_entries_controller(
    dynamodb_resource: ServiceResource,
    period: tuple[Periodicity | None, str | None],
    client: str,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> EntryListResponseSchema:
    '''
        The amounts of the client, all or those of a period.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            period (tuple[Periodicity | None, str | None]): Periodicity and date prefix.
            client (str): The owner of the data, from the token.
            current_user (str): The user, read by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            EntryListResponseSchema: The amounts.
    '''
    return list_entries(dynamodb_resource, client, period)


@handle_service_errors('FINANCE')
@audit_event('FINANCE', 'Entry', 'UPDATE')
async def update_entry_controller(
    dynamodb_resource: ServiceResource,
    target: tuple[Periodicity, str, str],
    update: EntryUpdateSchema,
    client: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> EntrySchema:
    '''
        Corrects one amount.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            target (tuple[Periodicity, str, str]): Periodicity, date and account.
            update (EntryUpdateSchema): What changes.
            client (str): The owner of the data, from the token.
            current_user (str): The user correcting it, recorded and audited.
            request (Request): Incoming request, used by the decorators.

        Returns:
            EntrySchema: The amount after the correction.
    '''
    return update_entry(dynamodb_resource, (client, current_user), target, update)


@handle_service_errors('FINANCE')
@audit_event('FINANCE', 'Entry', 'DELETE')
async def delete_entry_controller(
    dynamodb_resource: ServiceResource,
    target: tuple[Periodicity, str, str],
    client: str,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> EntrySchema:
    '''
        Removes one amount.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            target (tuple[Periodicity, str, str]): Periodicity, date and account.
            client (str): The owner of the data, from the token.
            current_user (str): The user, read by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            EntrySchema: The amount that was removed.
    '''
    return delete_entry(dynamodb_resource, client, target)


@handle_service_errors('FINANCE')
@audit_event('FINANCE', 'Period', 'DELETE')
async def delete_period_controller(
    dynamodb_resource: ServiceResource,
    period: tuple[Periodicity, str],
    client: str,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> PeriodDeleteResultSchema:
    '''
        Empties a period.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            period (tuple[Periodicity, str]): Periodicity and date prefix.
            client (str): The owner of the data, from the token.
            current_user (str): The user, read by the decorators.
            request (Request): Incoming request, used by the decorators.

        Returns:
            PeriodDeleteResultSchema: How many amounts were removed.
    '''
    return delete_period(dynamodb_resource, client, period)
