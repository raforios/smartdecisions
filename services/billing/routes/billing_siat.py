'''
    Electronic invoicing with the SIN: HTTP layer.

    Anybody of the shop reads the codes in force and the catalogues; only
    whoever runs it synchronises the catalogues again. The owner is the shop
    the token names, never a parameter.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Request

from controllers.billing_siat import (
    current_codes_controller,
    get_catalog_controller,
    sync_catalogs_controller
)
from schemas.billing_siat import CatalogOut, CatalogsSyncResponse, SiatCatalog, SiatCodesOut
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner, get_current_user, require_roles

router = APIRouter(prefix = '/v1/billing/siat', tags = ['Billing — SIAT'])

# Same pair that runs the shop in `routes/billing.py`.
MANAGERS = ('ADMIN', 'MANAGER')


@router.get('/codes', response_model = SiatCodesOut)
async def current_codes_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> SiatCodesOut:
    ''' Endpoint for the CUIS and CUFD in force. '''
    return await current_codes_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        request = request, current_user = current_user
    )


@router.post('/catalogs/sync', response_model = CatalogsSyncResponse)
async def sync_catalogs_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> CatalogsSyncResponse:
    ''' Endpoint to bring every catalogue from the tax office. '''
    message = f'Shop {owner} synchronises the SIAT catalogues.'
    logger.info(message)
    return await sync_catalogs_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        request = request, current_user = current_user
    )


@router.get('/catalogs/{catalog}', response_model = CatalogOut)
async def get_catalog_endpoint(
    catalog: SiatCatalog,
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> CatalogOut:
    ''' Endpoint for one stored catalogue. '''
    return await get_catalog_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, catalog = catalog,
        request = request, current_user = current_user
    )
