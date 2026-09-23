'''
    Billing: HTTP layer.

    Two kinds of access. Setting the shop up, editing the catalogue, receiving
    a delivery and voiding a note belong to whoever runs it; selling belongs to
    whoever is at the till. The owner of every row is the shop the token names,
    never a parameter — a request cannot ask for another shop's shelf.

    Every endpoint hands `request` and `current_user` to its controller: that
    is what lets the EVENTS decorators report the call and audit the change.
'''
from datetime import date as date_type
from typing import Optional

from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Body, Depends, Path, Query, Request, status

from controllers.billing import (
    cancel_sale_controller,
    create_product_controller,
    dashboard_controller,
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
from schemas.billing import (
    BillingDashboard,
    BillingSettings,
    DateWindow,
    LotEdit,
    LotPricePatch,
    LotQuery,
    LotsResponse,
    ProductIn,
    ProductEdit,
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

router = APIRouter(prefix = '/v1/billing', tags = ['Billing'])

# Running the shop: settings, catalogue, deliveries and voiding a note. A
# cashier sells; they do not re-price the shelf or annul their own sale.
MANAGERS = ('ADMIN', 'MANAGER')


def date_window(
    date_from: Optional[date_type] = Query(None, description = 'First day.'),
    date_to: Optional[date_type] = Query(None, description = 'Last day.')
) -> DateWindow:
    '''
        The window a listing covers, as one argument.

        Grouped as a dependency because the two bounds are one concept: they
        travel together and neither is useful without the other.

        Args:
            date_from (date | None): First day.
            date_to (date | None): Last day.

        Returns:
            DateWindow: The range the controller receives.
    '''
    return DateWindow(date_from = date_from, date_to = date_to)


def product_edit(
    patch: ProductPatch = Body(...),
    sku: str = Path(..., min_length = 1, max_length = 40)
) -> ProductEdit:
    '''
        Which SKU is edited and what changes about it.

        Args:
            patch (ProductPatch): Fields to change.
            sku (str): Product being edited.

        Returns:
            ProductEdit: The edit the controller receives.
    '''
    return ProductEdit(sku = sku, patch = patch)


def lot_query(
    sku: str = Path(..., min_length = 1, max_length = 40),
    only_available: bool = Query(True, description = 'Leave out exhausted batches.')
) -> LotQuery:
    '''
        Whose batches are being asked for.

        Args:
            sku (str): Product to read.
            only_available (bool): Leave out exhausted batches.

        Returns:
            LotQuery: The query the controller receives.
    '''
    return LotQuery(sku = sku, only_available = only_available)


def lot_edit(
    lot: LotPricePatch = Body(...),
    sku: str = Path(..., min_length = 1, max_length = 40),
    lot_id: str = Path(..., min_length = 1, max_length = 60)
) -> LotEdit:
    '''
        Which batch is re-priced and to what.

        Args:
            lot (LotPricePatch): The new price.
            sku (str): Product the batch belongs to.
            lot_id (str): Batch being re-priced.

        Returns:
            LotEdit: The edit the controller receives.
    '''
    return LotEdit(sku = sku, lot_id = lot_id, sale_price = lot.sale_price)


@router.get('/dashboard', response_model = BillingDashboard)
async def dashboard_endpoint(
    request: Request,
    window: DateWindow = Depends(date_window),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> BillingDashboard:
    ''' Endpoint for the counter summary. '''
    message = f'Shop {owner} opened its dashboard.'
    logger.info(message)
    return await dashboard_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, window = window,
        request = request, current_user = current_user
    )


@router.get('/settings', response_model = SettingsResponse)
async def get_settings_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> SettingsResponse:
    ''' Endpoint for the shop's own parameters. '''
    return await get_settings_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        request = request, current_user = current_user
    )


@router.put('/settings', response_model = SettingsResponse)
async def save_settings_endpoint(
    request: Request,
    settings: BillingSettings,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> SettingsResponse:
    ''' Endpoint to set the shop up. '''
    message = f'Shop {owner} saved its settings.'
    logger.info(message)
    return await save_settings_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, settings = settings,
        request = request, current_user = current_user
    )


@router.get('/products', response_model = ProductsResponse)
async def list_products_endpoint(
    request: Request,
    only_active: bool = Query(False, description = 'Leave out deactivated SKUs.'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> ProductsResponse:
    ''' Endpoint for the catalogue with availability. '''
    return await list_products_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        only_active = only_active, request = request, current_user = current_user
    )


@router.post('/products', response_model = ProductOut,
             status_code = status.HTTP_201_CREATED)
async def create_product_endpoint(
    request: Request,
    product: ProductIn,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> ProductOut:
    ''' Endpoint to register a SKU. '''
    message = f'Shop {owner} registered SKU {product.sku}.'
    logger.info(message)
    return await create_product_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, product = product,
        request = request, current_user = current_user
    )


@router.get('/products/{sku}', response_model = ProductOut)
async def get_product_endpoint(
    request: Request,
    sku: str = Path(..., min_length = 1, max_length = 40),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> ProductOut:
    ''' Endpoint for one SKU. '''
    return await get_product_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, sku = sku,
        request = request, current_user = current_user
    )


@router.patch('/products/{sku}', response_model = ProductOut)
async def update_product_endpoint(
    request: Request,
    edit: ProductEdit = Depends(product_edit),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> ProductOut:
    ''' Endpoint to edit a SKU. '''
    message = f'Shop {owner} edited SKU {edit.sku}.'
    logger.info(message)
    return await update_product_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, edit = edit,
        request = request, current_user = current_user
    )


@router.get('/products/{sku}/lots', response_model = LotsResponse)
async def lots_endpoint(
    request: Request,
    query: LotQuery = Depends(lot_query),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> LotsResponse:
    ''' Endpoint for the batches of one SKU, in selling order. '''
    return await lots_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, query = query,
        request = request, current_user = current_user
    )


@router.patch('/products/{sku}/lots/{lot_id}', response_model = LotsResponse)
async def reprice_lot_endpoint(
    request: Request,
    edit: LotEdit = Depends(lot_edit),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> LotsResponse:
    ''' Endpoint to re-price one batch. '''
    message = f'Shop {owner} re-priced lot {edit.lot_id} of {edit.sku}.'
    logger.info(message)
    return await reprice_lot_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, edit = edit,
        request = request, current_user = current_user
    )


@router.post('/purchases', response_model = PurchaseNoteOut,
             status_code = status.HTTP_201_CREATED)
async def receive_purchase_endpoint(
    request: Request,
    note: PurchaseNoteIn,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> PurchaseNoteOut:
    ''' Endpoint to record a delivery from a supplier. '''
    message = f'Shop {owner} received a delivery from {note.supplier_name}.'
    logger.info(message)
    return await receive_purchase_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, note = note,
        request = request, current_user = current_user
    )


@router.get('/purchases', response_model = PurchaseNotesResponse)
async def list_purchases_endpoint(
    request: Request,
    window: DateWindow = Depends(date_window),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> PurchaseNotesResponse:
    ''' Endpoint for the delivery notes of a window. '''
    return await list_purchases_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, window = window,
        request = request, current_user = current_user
    )


@router.get('/purchases/{purchase_id}', response_model = PurchaseNoteOut)
async def get_purchase_endpoint(
    request: Request,
    purchase_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> PurchaseNoteOut:
    ''' Endpoint for one delivery note. '''
    return await get_purchase_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        purchase_id = purchase_id, request = request, current_user = current_user
    )


@router.post('/sales', response_model = SaleNoteOut,
             status_code = status.HTTP_201_CREATED)
async def issue_sale_endpoint(
    request: Request,
    note: SaleNoteIn,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> SaleNoteOut:
    ''' Endpoint to sell over the counter. '''
    message = f'Shop {owner}: {current_user} is selling {len(note.lines)} line(s).'
    logger.info(message)
    return await issue_sale_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, note = note,
        request = request, current_user = current_user
    )


@router.get('/sales', response_model = SaleNotesResponse)
async def list_sales_endpoint(
    request: Request,
    window: DateWindow = Depends(date_window),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> SaleNotesResponse:
    ''' Endpoint for the sale notes of a window. '''
    return await list_sales_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, window = window,
        request = request, current_user = current_user
    )


@router.get('/sales/{sale_id}', response_model = SaleNoteOut)
async def get_sale_endpoint(
    request: Request,
    sale_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> SaleNoteOut:
    ''' Endpoint for one sale note, as it prints. '''
    return await get_sale_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, sale_id = sale_id,
        request = request, current_user = current_user
    )


@router.post('/sales/{sale_id}/cancel', response_model = SaleNoteOut)
async def cancel_sale_endpoint(
    request: Request,
    sale_id: str = Path(..., min_length = 1, max_length = 120),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(require_roles(*MANAGERS)),
    current_user: str = Depends(get_current_user)
) -> SaleNoteOut:
    ''' Endpoint to void a note and return its units to their batches. '''
    message = f'Shop {owner}: {current_user} cancelled sale {sale_id}.'
    logger.info(message)
    return await cancel_sale_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, sale_id = sale_id,
        request = request, current_user = current_user
    )
