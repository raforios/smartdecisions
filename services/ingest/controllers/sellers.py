'''
    The seller master: reading it and linking a seller to the user they sign in as.

    The loads feed it on their own through `sync_master`; what is left for the
    API is the part only a person can decide. Linking is audited, because it
    decides whose phone sees which route.
'''

from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.sellers import SellerListResponseSchema, SellerResponseSchema, SellerUpdateSchema
from services.sellers import (
    list_sellers,
    to_seller_list_response,
    to_seller_response,
    update_seller
)
from services.utils import audit_event, handle_service_errors


@handle_service_errors('INGEST')
async def list_sellers_controller(
    dynamodb_resource: ServiceResource,
    user_email: str | None,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> SellerListResponseSchema:
    '''
        The owner's sellers, optionally only the ones a user signs in as.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            user_email (str | None): Keep only the sellers linked to this user.
            current_user (str): Authenticated caller and owner of the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            SellerListResponseSchema: The sellers and how many are linked.
    '''
    return to_seller_list_response(list_sellers(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        user_email = user_email
    ))


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Seller', 'UPDATE')
async def update_seller_controller(
    dynamodb_resource: ServiceResource,
    seller_id: str,
    changes: SellerUpdateSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> SellerResponseSchema:
    '''
        Links a seller to a user, or renames them.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            seller_id (str): Seller code, as the files write it.
            changes (SellerUpdateSchema): Attributes to overwrite.
            current_user (str): Authenticated caller and owner of the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            SellerResponseSchema: The seller after the change.
    '''
    return to_seller_response(update_seller(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        seller_id = seller_id,
        changes = changes
    ))
