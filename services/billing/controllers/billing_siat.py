'''
    Electronic invoicing with the SIN: orchestration between the HTTP layer
    and the services.

    Same contract as `controllers/billing.py`: every controller carries
    `@handle_service_errors`, and the one that rewrites the stored catalogues
    carries `@audit_event`.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.billing_siat import CatalogOut, CatalogsSyncResponse, SiatCatalog, SiatCodesOut
from services import billing_siat_codes
from services.utils import audit_event, handle_service_errors

SERVICE = 'BILLING'


@handle_service_errors(SERVICE)
async def current_codes_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> SiatCodesOut:
    '''
        The CUIS and CUFD in force, renewed when missing or expired.
    '''
    return billing_siat_codes.current_codes(dynamodb_resource, owner)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'SiatCatalog', 'SYNC')
async def sync_catalogs_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> CatalogsSyncResponse:
    '''
        Brings every catalogue from the tax office and stores it.
    '''
    return billing_siat_codes.sync_catalogs(dynamodb_resource, owner)


@handle_service_errors(SERVICE)
async def get_catalog_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    catalog: SiatCatalog,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> CatalogOut:
    '''
        One stored catalogue.
    '''
    return billing_siat_codes.get_catalog(dynamodb_resource, owner, catalog)
