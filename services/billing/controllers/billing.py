'''
    Billing: orchestration between the HTTP layer and the services.

    Thin on purpose. Everything the product decides — which batch leaves, what
    a line is worth, whether a discount is allowed — lives in
    `services/billing*.py`; here the owner and the caller are handed down and
    the DTO comes back.

    Every controller carries `@handle_service_errors`, which reports the call
    to EVENTS, and every one that changes something carries `@audit_event`,
    which records who did it and to which row. `request` and `current_user`
    are declared for those decorators, not for the body.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.billing import (
    BillingDashboard,
    BillingSettings,
    DateWindow,
    LotEdit,
    LotPricePatch,
    LotQuery,
    LotsResponse,
    ProductEdit,
    ProductIn,
    ProductOut,
    ProductsResponse,
    PurchaseNoteIn,
    PurchaseNoteOut,
    PurchaseNotesResponse,
    SaleNoteIn,
    SaleNoteOut,
    SaleNotesResponse,
    SettingsResponse
)
from services import (
    billing,
    billing_purchases,
    billing_reports,
    billing_sales,
    billing_stock
)
from services.utils import audit_event, handle_service_errors

SERVICE = 'BILLING'


# --- counter dashboard -------------------------------------------------------

@handle_service_errors(SERVICE)
async def dashboard_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    window: DateWindow,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> BillingDashboard:
    '''
        What was sold, what it left, what is about to expire and what is about
        to run out.
    '''
    return billing_reports.dashboard(dynamodb_resource, owner,
                                     window.date_from, window.date_to)


# --- settings ----------------------------------------------------------------

@handle_service_errors(SERVICE)
async def get_settings_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> SettingsResponse:
    '''
        The shop's own parameters and counters.
    '''
    return billing.get_settings(dynamodb_resource, owner)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'Settings', 'UPSERT')
async def save_settings_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    settings: BillingSettings,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> SettingsResponse:
    '''
        Creates or replaces the shop's parameters.
    '''
    return billing.save_settings(dynamodb_resource, owner, settings)


# --- catalogue ---------------------------------------------------------------

@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'Product', 'CREATE')
async def create_product_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    product: ProductIn,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductOut:
    '''
        Registers a SKU.
    '''
    return billing.create_product(dynamodb_resource, owner, product)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'Product', 'UPDATE')
async def update_product_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    edit: ProductEdit,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductOut:
    '''
        Changes what a SKU says about itself.
    '''
    return billing.update_product(dynamodb_resource, owner, edit.sku, edit.patch)


@handle_service_errors(SERVICE)
async def list_products_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    only_active: bool,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductsResponse:
    '''
        The catalogue with availability and the price that would be charged.
    '''
    return billing.list_products(dynamodb_resource, owner, only_active)


@handle_service_errors(SERVICE)
async def get_product_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sku: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> ProductOut:
    '''
        One SKU with its availability.
    '''
    return billing.get_product(dynamodb_resource, owner, sku)


# --- lots --------------------------------------------------------------------

@handle_service_errors(SERVICE)
async def lots_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    query: LotQuery,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> LotsResponse:
    '''
        The batches of one SKU, in the order they will be sold.
    '''
    return billing_stock.lots_of(dynamodb_resource, owner,
                                 query.sku, query.only_available)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'Lot', 'REPRICE')
async def reprice_lot_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    edit: LotEdit,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> LotsResponse:
    '''
        Re-prices one batch and answers with the SKU's batches as they stand.
    '''
    billing_stock.reprice_lot(dynamodb_resource, owner, edit.sku, edit.lot_id,
                              LotPricePatch(sale_price = edit.sale_price))
    return billing_stock.lots_of(dynamodb_resource, owner, edit.sku)


# --- purchase notes ----------------------------------------------------------

@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'PurchaseNote', 'CREATE')
async def receive_purchase_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    note: PurchaseNoteIn,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> PurchaseNoteOut:
    '''
        Records a delivery and puts its batches on the shelf.
    '''
    return billing_purchases.receive_purchase(
        dynamodb_resource, owner, note, current_user
    )


@handle_service_errors(SERVICE)
async def list_purchases_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    window: DateWindow,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PurchaseNotesResponse:
    '''
        Delivery notes of a window.
    '''
    return billing_purchases.list_purchases(
        dynamodb_resource, owner,
        window.date_from.isoformat() if window.date_from else None,
        window.date_to.isoformat() if window.date_to else None
    )


@handle_service_errors(SERVICE)
async def get_purchase_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    purchase_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PurchaseNoteOut:
    '''
        One delivery note.
    '''
    return billing_purchases.get_purchase(dynamodb_resource, owner, purchase_id)


# --- sale notes --------------------------------------------------------------

@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'SaleNote', 'ISSUE')
async def issue_sale_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    note: SaleNoteIn,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> SaleNoteOut:
    '''
        Registers a sale and takes the units out of stock.
    '''
    return billing_sales.issue_sale(dynamodb_resource, owner, note, current_user)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'SaleNote', 'CANCEL')
async def cancel_sale_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> SaleNoteOut:
    '''
        Cancels a note and returns its units to the batches they left.
    '''
    return billing_sales.cancel_sale(dynamodb_resource, owner, sale_id, current_user)


@handle_service_errors(SERVICE)
async def list_sales_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    window: DateWindow,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> SaleNotesResponse:
    '''
        Sale notes of a window, newest first.
    '''
    return billing_sales.list_sales(
        dynamodb_resource, owner,
        window.date_from.isoformat() if window.date_from else None,
        window.date_to.isoformat() if window.date_to else None
    )


@handle_service_errors(SERVICE)
async def get_sale_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> SaleNoteOut:
    '''
        One note, as it prints.
    '''
    return billing_sales.get_sale(dynamodb_resource, owner, sale_id)
