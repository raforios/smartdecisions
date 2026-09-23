'''
    Pharmacy billing: HTTP layer.

    Two kinds of access. Setting the shop up, editing the catalogue, receiving
    a delivery and voiding a note belong to whoever runs the pharmacy; selling
    belongs to whoever is at the till. The owner of every row is the pharmacy
    the token names, never a parameter — a request cannot ask for another
    shop's shelf.
'''
from datetime import date as date_type
from typing import Optional

from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path, Query, status

from controllers.pharmacy import (
    cancel_sale_controller,
    dashboard_controller,
    create_product_controller,
    get_product_controller,
    get_purchase_controller,
    get_sale_controller,
    get_settings_controller,
    issue_sale_controller,
    list_products_controller,
    list_purchases_controller,
    list_sales_controller,
    lots_controller,
    receive_purchase_controller,
    reprice_lot_controller,
    save_settings_controller,
    update_product_controller
)
from schemas.pharmacy import (
    LotPricePatch,
    PharmacyDashboard,
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
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner, get_current_user, require_roles

router = APIRouter(prefix = '/v1/supplies/pharmacy', tags = ['Pharmacy billing'])

# Running the shop: settings, catalogue, deliveries and voiding a note. A
# cashier sells; they do not re-price the shelf or annul their own sale.
MANAGERS = ('ADMIN', 'MANAGER')


@router.get('/dashboard', response_model = PharmacyDashboard)
async def dashboard_endpoint(
    date_from: Optional[date_type] = Query(None, description = 'First day; today by default.'),
    date_to: Optional[date_type] = Query(None, description = 'Last day; today by default.'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner)
) -> PharmacyDashboard:
    ''' Endpoint for the counter summary. '''
    message = f'Pharmacy {owner} opened its dashboard.'
    logger.info(message)
    return await dashboard_controller(dynamodb_resource, owner, date_from, date_to)


@router.get('/settings', response_model = SettingsResponse)
async def get_settings_endpoint(
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner)
) -> SettingsResponse:
    ''' Endpoint for the pharmacy's own parameters. '''
    message = f'Pharmacy {owner} requested its settings.'
    logger.info(message)
    return await get_settings_controller(dynamodb_resource, owner)


@router.put('/settings', response_model = SettingsResponse)
async def save_settings_endpoint(
    settings: PharmacySettings,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS))
) -> SettingsResponse:
    ''' Endpoint to set the pharmacy up. '''
    message = f'Pharmacy {owner} saved its settings.'
    logger.info(message)
    return await save_settings_controller(dynamodb_resource, owner, settings)


@router.get('/products', response_model = ProductsResponse)
async def list_products_endpoint(
    only_active: bool = Query(False, description = 'Leave out deactivated SKUs.'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner)
) -> ProductsResponse:
    ''' Endpoint for the catalogue with availability. '''
    message = f'Pharmacy {owner} listed its catalogue.'
    logger.info(message)
    return await list_products_controller(dynamodb_resource, owner, only_active)


@router.post('/products', response_model = ProductOut,
             status_code = status.HTTP_201_CREATED)
async def create_product_endpoint(
    product: ProductIn,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS))
) -> ProductOut:
    ''' Endpoint to register a SKU. '''
    message = f'Pharmacy {owner} registered SKU {product.sku}.'
    logger.info(message)
    return await create_product_controller(dynamodb_resource, owner, product)


@router.get('/products/{sku}', response_model = ProductOut)
async def get_product_endpoint(
    sku: str = Path(..., min_length = 1, max_length = 40),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner)
) -> ProductOut:
    ''' Endpoint for one SKU. '''
    return await get_product_controller(dynamodb_resource, owner, sku)


@router.patch('/products/{sku}', response_model = ProductOut)
async def update_product_endpoint(
    patch: ProductPatch,
    sku: str = Path(..., min_length = 1, max_length = 40),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS))
) -> ProductOut:
    ''' Endpoint to edit a SKU. '''
    message = f'Pharmacy {owner} edited SKU {sku}.'
    logger.info(message)
    return await update_product_controller(dynamodb_resource, owner, sku, patch)


@router.get('/products/{sku}/lots', response_model = LotsResponse)
async def lots_endpoint(
    sku: str = Path(..., min_length = 1, max_length = 40),
    only_available: bool = Query(True, description = 'Leave out exhausted batches.'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner)
) -> LotsResponse:
    ''' Endpoint for the batches of one SKU, in selling order. '''
    return await lots_controller(dynamodb_resource, owner, sku, only_available)


@router.patch('/products/{sku}/lots/{lot_id}', response_model = LotsResponse)
async def reprice_lot_endpoint(
    patch: LotPricePatch,
    sku: str = Path(..., min_length = 1, max_length = 40),
    lot_id: str = Path(..., min_length = 1, max_length = 60),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS))
) -> LotsResponse:
    ''' Endpoint to re-price one batch. '''
    message = f'Pharmacy {owner} re-priced lot {lot_id} of {sku}.'
    logger.info(message)
    return await reprice_lot_controller(dynamodb_resource, owner, sku, lot_id, patch)


@router.post('/purchases', response_model = PurchaseNoteOut,
             status_code = status.HTTP_201_CREATED)
async def receive_purchase_endpoint(
    note: PurchaseNoteIn,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> PurchaseNoteOut:
    ''' Endpoint to record a delivery from a laboratory or distributor. '''
    message = f'Pharmacy {owner} received a delivery from {note.supplier_name}.'
    logger.info(message)
    return await receive_purchase_controller(
        dynamodb_resource, owner, note, current_user
    )


@router.get('/purchases', response_model = PurchaseNotesResponse)
async def list_purchases_endpoint(
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS))
) -> PurchaseNotesResponse:
    ''' Endpoint for the delivery notes of a window. '''
    return await list_purchases_controller(
        dynamodb_resource, owner,
        date_from.isoformat() if date_from else None,
        date_to.isoformat() if date_to else None
    )


@router.get('/purchases/{purchase_id}', response_model = PurchaseNoteOut)
async def get_purchase_endpoint(
    purchase_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS))
) -> PurchaseNoteOut:
    ''' Endpoint for one delivery note. '''
    return await get_purchase_controller(dynamodb_resource, owner, purchase_id)


@router.post('/sales', response_model = SaleNoteOut,
             status_code = status.HTTP_201_CREATED)
async def issue_sale_endpoint(
    note: SaleNoteIn,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> SaleNoteOut:
    ''' Endpoint to sell over the counter. '''
    message = f'Pharmacy {owner}: {current_user} is selling {len(note.lines)} line(s).'
    logger.info(message)
    return await issue_sale_controller(dynamodb_resource, owner, note, current_user)


@router.get('/sales', response_model = SaleNotesResponse)
async def list_sales_endpoint(
    date_from: Optional[date_type] = Query(None),
    date_to: Optional[date_type] = Query(None),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner)
) -> SaleNotesResponse:
    ''' Endpoint for the sale notes of a window. '''
    return await list_sales_controller(
        dynamodb_resource, owner,
        date_from.isoformat() if date_from else None,
        date_to.isoformat() if date_to else None
    )


@router.get('/sales/{sale_id}', response_model = SaleNoteOut)
async def get_sale_endpoint(
    sale_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner)
) -> SaleNoteOut:
    ''' Endpoint for one sale note, as it prints. '''
    return await get_sale_controller(dynamodb_resource, owner, sale_id)


@router.post('/sales/{sale_id}/cancel', response_model = SaleNoteOut)
async def cancel_sale_endpoint(
    sale_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> SaleNoteOut:
    ''' Endpoint to void a note and return its units to their batches. '''
    message = f'Pharmacy {owner}: {current_user} cancelled sale {sale_id}.'
    logger.info(message)
    return await cancel_sale_controller(dynamodb_resource, owner, sale_id, current_user)
