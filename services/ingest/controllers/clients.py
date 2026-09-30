'''
    The client master: the API door and the reading side.

    The other two doors —the uploaded workbook and the seller standing at a new
    address— feed the same service from their own controllers. Everything that
    changes the master is audited, because a coordinate that moves is a route
    that changes and somebody has to be able to say who moved it.
'''
from typing import Optional

from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.clients import (
    ClientBulkUpsertSchema,
    FieldClientSchema,
    ClientListResponseSchema,
    ClientResponseSchema,
    ClientSource,
    ClientUpdateSchema,
    ClientUpsertResultSchema
)
from services.clients import (
    get_client,
    register_field_client,
    list_clients,
    to_client_list_response,
    to_client_response,
    update_client,
    upsert_clients
)
from services.utils import audit_event, handle_service_errors


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Client', 'UPLOAD')
async def upsert_clients_controller(
    dynamodb_resource: ServiceResource,
    payload: ClientBulkUpsertSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ClientUpsertResultSchema:
    '''
        Feeds the master from the owner's ERP.

        Creates what is missing and completes what is empty; it never
        overwrites a field that already holds a value. That is what makes the
        call safe to repeat every night.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            payload (ClientBulkUpsertSchema): Clients pushed by the ERP.
            current_user (str): Authenticated caller and owner of the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ClientUpsertResultSchema: Created, completed and unchanged counts.
    '''
    return upsert_clients(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        clients = payload.clients,
        source = ClientSource.API
    )


@handle_service_errors('INGEST')
async def list_clients_controller(
    dynamodb_resource: ServiceResource,
    seller: Optional[str],
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ClientListResponseSchema:
    '''
        The owner's clients, optionally narrowed to one seller's portfolio.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            seller (Optional[str]): Salesperson the client is assigned to.
            current_user (str): Authenticated caller and owner of the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ClientListResponseSchema: The list and its counts.
    '''
    return to_client_list_response(list_clients(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        seller = seller
    ))


@handle_service_errors('INGEST')
async def get_client_controller(
    dynamodb_resource: ServiceResource,
    client_id: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ClientResponseSchema:
    '''
        One client of the owner's master.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            client_id (str): Client code.
            current_user (str): Authenticated caller and owner of the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ClientResponseSchema: The stored client.
    '''
    return to_client_response(get_client(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        client_id = client_id
    ))


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Client', 'UPDATE')
async def update_client_controller(
    dynamodb_resource: ServiceResource,
    client_id: str,
    changes: ClientUpdateSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ClientResponseSchema:
    '''
        Corrects a client, overwriting what the payload names.

        Separate from the load on purpose: a load completes, a correction
        replaces, and only one of the two is somebody deciding that what is
        stored is wrong.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            client_id (str): Client code.
            changes (ClientUpdateSchema): Attributes to overwrite.
            current_user (str): Authenticated caller and owner of the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ClientResponseSchema: The client after the change.
    '''
    return to_client_response(update_client(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        client_id = client_id,
        changes = changes
    ))


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Client', 'CREATE')
async def register_field_client_controller(
    dynamodb_resource: ServiceResource,
    client: FieldClientSchema,
    current_user: str,
    seller: str,
    request: Request # pylint: disable=unused-argument
) -> ClientResponseSchema:
    '''
        A seller registers a client from the street.

        This is the door that turns an off-plan stop into something reusable:
        once the client exists, the day can be turned into a plan and the next
        route can include it.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            client (FieldClientSchema): What the seller reported.
            current_user (str): Account that owns the data.
            seller (str): Email of the person reporting it.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ClientResponseSchema: The client, new or completed.
    '''
    return to_client_response(register_field_client(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        client = client,
        seller = seller
    ))
