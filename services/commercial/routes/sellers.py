'''
    Seller master — HTTP layer.

    The loads feed the master on their own; the API reads it and lets a manager
    say which user each seller signs in as.
'''

from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path as PathParam, Query, Request, status

from controllers.sellers import list_sellers_controller, update_seller_controller
from schemas.sellers import (
    LINKING_ROLES,
    SellerListResponseSchema,
    SellerResponseSchema,
    SellerUpdateSchema
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner, require_roles

router = APIRouter(prefix = '/v1/ingest/sellers', tags = ['Seller master'])

_SELLER_ID = PathParam(..., min_length = 1, max_length = 128)


@router.get(
    '',
    response_model = SellerListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'The sellers of the account',
    description = 'Every seller the loaded files mention, with the user each one '
                  'signs in as. `user_email` narrows it to the sellers one user is, '
                  'which is how a phone finds its own routes.'
)
async def list_sellers_endpoint(
    request: Request,
    user_email: str | None = Query(None, max_length = 100),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> SellerListResponseSchema:
    '''
        Endpoint listing the owner's seller master.
    '''
    message = f'User: {current_user}. Reading the seller master (user={user_email}).'
    logger.info(message)
    return await list_sellers_controller(
        dynamodb_resource = dynamodb_resource,
        user_email = user_email,
        current_user = current_user,
        request = request
    )


@router.patch(
    '/{seller_id}',
    response_model = SellerResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Link a seller to a user, or rename them',
    description = 'Overwrites what it names. Unlike a load, this is a manager '
                  'deciding who the seller in the files is.'
)
async def update_seller_endpoint(
    request: Request,
    changes: SellerUpdateSchema,
    seller_id: str = _SELLER_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*LINKING_ROLES))
) -> SellerResponseSchema:
    '''
        Endpoint updating one seller of the master.
    '''
    message = f'User: {current_user}. Updating seller {seller_id}.'
    logger.info(message)
    return await update_seller_controller(
        dynamodb_resource = dynamodb_resource,
        seller_id = seller_id,
        changes = changes,
        current_user = current_user,
        request = request
    )
