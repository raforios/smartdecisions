'''
    Pharmacy billing: orchestration between the HTTP layer and the services.

    Thin on purpose. Everything the pharmacy product decides — which batch
    leaves, what a line is worth, whether a discount is allowed — lives in
    `services/pharmacy*.py`; here the owner and the caller are handed down and
    the DTO comes back.
'''
from typing import Optional

from boto3.resources.base import ServiceResource

from schemas.pharmacy import (
    LotPricePatch,
    LotsResponse,
    PharmacySettings,
    ProductIn,
    ProductOut,
    ProductPatch,
    ProductsResponse,
    PurchaseNoteIn,
    PurchaseNoteOut,
    PurchaseNotesResponse,
    SaleNoteIn,
    SaleNoteOut,
    SaleNotesResponse,
    SettingsResponse
)
from services import pharmacy, pharmacy_purchases, pharmacy_sales, pharmacy_stock


# --- settings ----------------------------------------------------------------

async def get_settings_controller(
    dynamodb_resource: ServiceResource,
    owner: str
) -> SettingsResponse:
    '''
        The pharmacy's own parameters and counters.
    '''
    return pharmacy.get_settings(dynamodb_resource, owner)


async def save_settings_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    settings: PharmacySettings
) -> SettingsResponse:
    '''
        Creates or replaces the pharmacy's parameters.
    '''
    return pharmacy.save_settings(dynamodb_resource, owner, settings)


# --- catalogue ---------------------------------------------------------------

async def create_product_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    product: ProductIn
) -> ProductOut:
    '''
        Registers a SKU.
    '''
    return pharmacy.create_product(dynamodb_resource, owner, product)


async def update_product_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sku: str,
    patch: ProductPatch
) -> ProductOut:
    '''
        Changes what a SKU says about itself.
    '''
    return pharmacy.update_product(dynamodb_resource, owner, sku, patch)


async def list_products_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    only_active: bool
) -> ProductsResponse:
    '''
        The catalogue with availability and the price that would be charged.
    '''
    return pharmacy.list_products(dynamodb_resource, owner, only_active)


async def get_product_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sku: str
) -> ProductOut:
    '''
        One SKU with its availability.
    '''
    return pharmacy.get_product(dynamodb_resource, owner, sku)


# --- lots --------------------------------------------------------------------

async def lots_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sku: str,
    only_available: bool
) -> LotsResponse:
    '''
        The batches of one SKU, in the order they will be sold.
    '''
    return pharmacy_stock.lots_of(dynamodb_resource, owner, sku, only_available)


async def reprice_lot_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sku: str,
    lot_id: str,
    patch: LotPricePatch
) -> LotsResponse:
    '''
        Re-prices one batch and answers with the SKU's batches as they stand.
    '''
    pharmacy_stock.reprice_lot(dynamodb_resource, owner, sku, lot_id, patch)
    return pharmacy_stock.lots_of(dynamodb_resource, owner, sku)


# --- purchase notes ----------------------------------------------------------

async def receive_purchase_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    note: PurchaseNoteIn,
    current_user: str
) -> PurchaseNoteOut:
    '''
        Records a delivery and puts its batches on the shelf.
    '''
    return pharmacy_purchases.receive_purchase(
        dynamodb_resource, owner, note, current_user
    )


async def list_purchases_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    date_from: Optional[str],
    date_to: Optional[str]
) -> PurchaseNotesResponse:
    '''
        Delivery notes of a window.
    '''
    return pharmacy_purchases.list_purchases(
        dynamodb_resource, owner, date_from, date_to
    )


async def get_purchase_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    purchase_id: str
) -> PurchaseNoteOut:
    '''
        One delivery note.
    '''
    return pharmacy_purchases.get_purchase(dynamodb_resource, owner, purchase_id)


# --- sale notes --------------------------------------------------------------

async def issue_sale_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    note: SaleNoteIn,
    current_user: str
) -> SaleNoteOut:
    '''
        Registers a sale and takes the units out of stock.
    '''
    return pharmacy_sales.issue_sale(dynamodb_resource, owner, note, current_user)


async def cancel_sale_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str,
    current_user: str
) -> SaleNoteOut:
    '''
        Cancels a note and returns its units to the batches they left.
    '''
    return pharmacy_sales.cancel_sale(dynamodb_resource, owner, sale_id, current_user)


async def list_sales_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    date_from: Optional[str],
    date_to: Optional[str]
) -> SaleNotesResponse:
    '''
        Sale notes of a window, newest first.
    '''
    return pharmacy_sales.list_sales(dynamodb_resource, owner, date_from, date_to)


async def get_sale_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    sale_id: str
) -> SaleNoteOut:
    '''
        One note, as it prints.
    '''
    return pharmacy_sales.get_sale(dynamodb_resource, owner, sale_id)
