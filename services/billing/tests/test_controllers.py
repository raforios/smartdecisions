'''
    Controller-level tests for the cash tills: each endpoint returns its model
    assembled, and every change is audited.

    `request` is None, so no usage log leaves; the audit hook is replaced by a
    recorder.
'''
import asyncio
from unittest.mock import patch

import pytest

from controllers import billing as billing_controllers
from controllers import billing_cash as controllers
from schemas.billing import (
    BillingError,
    BillingSettings,
    DateWindow,
    LotEdit,
    LotQuery,
    LotsResponse,
    ProductEdit,
    ProductIn,
    ProductOut,
    ProductPatch,
    ProductsResponse,
    PurchaseLineIn,
    PurchaseNoteIn,
    PurchaseNoteOut,
    PurchaseNotesResponse,
    SaleLineIn,
    SaleNoteIn,
    SaleNoteOut,
    SaleNotesResponse,
    SettingsResponse
)
from schemas.billing_reports import BillingDashboard
from schemas.billing_cash import (
    CashAlertsResponse,
    CashCloseIn,
    CashOpenIn,
    CashSessionOut,
    CashSessionsResponse,
    CashSessionStatus,
    ExpenseIn,
    ExpenseType,
    TillClose,
    TillExpense,
    TillExpenseRef,
    TillQuery,
    TillRef
)
from schemas.billing_siat import InvoiceQrOut
from services import utils
from services.exceptions import InvalidInputError, RegisterAlreadyExistsError, RegisterNotFoundError
from tests.test_billing import ( # pylint: disable=unused-import
    CASHIER,
    LATER,
    OWNER,
    _dynamodb,
    _receive,
    _register,
    _sell
)
from tests.test_billing_sale_invoice import ( # pylint: disable=unused-import
    BUYER,
    _invoicing_shop,
    _sent
)

SELLER = 'vendedor@farmacia.bo'


@pytest.fixture(name = 'audited')
def _audited():
    '''
        Records every audit the controllers send, without reaching EVENTS.

        Returns:
            list: (entity, action) pairs, in order.
    '''
    calls: list = []

    def _record(
        result, # pylint: disable=unused-argument
        kwargs, # pylint: disable=unused-argument
        spec
    ):
        calls.append((spec.entity_name, spec.action))
        return {}

    async def _no_send(
        audit_data, # pylint: disable=unused-argument
        authorization # pylint: disable=unused-argument
    ):
        return None

    with patch.object(utils, '_audit_payload', _record), \
            patch.object(utils, 'send_audit_event', _no_send):
        yield calls


def _call(
    controller,
    current_user = SELLER,
    **arguments
):
    '''
        Runs a controller as the endpoint would, in the demo shop.

        Args:
            controller: The async controller.
            current_user (str): Who calls; SELLER unless the till matters.
            **arguments: Its specific arguments.

        Returns:
            Any: What it returned.
    '''
    return asyncio.run(controller(owner = OWNER, request = None, current_user = current_user,
                                  **arguments))


def test_every_till_action_is_audited_and_returns_its_model(
    dynamodb,
    audited
):
    '''Case 16: open, expense, cancel and close audited; the reads are not.'''
    opened = _call(controllers.open_till_controller, dynamodb_resource = dynamodb,
                   opening = CashOpenIn(opening_cash = 200))
    assert isinstance(opened, CashSessionOut)
    session_id = opened.session_id

    current = _call(controllers.current_till_controller, dynamodb_resource = dynamodb)
    assert current.session_id == session_id

    spent = _call(controllers.add_expense_controller, dynamodb_resource = dynamodb,
                  target = TillExpense(session_id = session_id, expense = ExpenseIn(
                      expense_type = ExpenseType.PETTY_CASH, amount = 20,
                      concept = 'Bolsas')))
    movement_id = spent.movements[0].movement_id

    _call(controllers.cancel_expense_controller, dynamodb_resource = dynamodb,
          target = TillExpenseRef(session_id = session_id, movement_id = movement_id))

    one = _call(controllers.get_till_controller, dynamodb_resource = dynamodb,
                ref = TillRef(session_id = session_id))
    assert one.expected_cash == 200

    listed = _call(controllers.list_tills_controller, dynamodb_resource = dynamodb,
                   query = TillQuery())
    assert isinstance(listed, CashSessionsResponse)

    alerts = _call(controllers.till_alerts_controller, dynamodb_resource = dynamodb,
                   is_manager = False)
    assert isinstance(alerts, CashAlertsResponse)

    closed = _call(controllers.close_till_controller, dynamodb_resource = dynamodb,
                   target = TillClose(session_id = session_id,
                                      closing = CashCloseIn(counted_cash = 200)))
    assert closed.status is CashSessionStatus.CLOSED

    assert audited == [('CashSession', 'OPEN'), ('CashSession', 'EXPENSE'),
                       ('CashSession', 'CANCEL_EXPENSE'), ('CashSession', 'CLOSE')]


# --- settings and dashboard --------------------------------------------------

def test_settings_are_saved_audited_and_read_back(
    dynamodb,
    audited
):
    '''Saving is audited and answers the settings with their counters; reading is not.'''
    before = _call(billing_controllers.get_settings_controller, dynamodb_resource = dynamodb)
    assert before.trade_name == 'Farmacia Demo'
    saved = _call(billing_controllers.save_settings_controller, dynamodb_resource = dynamodb,
                  settings = BillingSettings(trade_name = 'Farmacia Central', sale_series = 'B'))
    assert isinstance(saved, SettingsResponse)

    read = _call(billing_controllers.get_settings_controller, dynamodb_resource = dynamodb)
    assert (read.trade_name, read.sale_series) == ('Farmacia Central', 'B')
    assert audited == [('Settings', 'UPSERT')]


def test_the_dashboard_returns_its_model(dynamodb):
    '''Today's sale is on the dashboard of today.'''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER)])
    _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 2)])
    board = _call(billing_controllers.dashboard_controller, dynamodb_resource = dynamodb,
                  window = DateWindow())
    assert isinstance(board, BillingDashboard)
    assert (board.sales_count, board.sales_amount) == (1, 12.0)


# --- catalogue, lots and purchases ---------------------------------------------

def test_the_catalogue_endpoints_return_their_models(
    dynamodb,
    audited
):
    '''
        Register, edit, receive, list and re-price a SKU: the changes are
        audited, a repeated SKU and an unknown one answer with their codes.
    '''
    created = _call(billing_controllers.create_product_controller, dynamodb_resource = dynamodb,
                    product = ProductIn(sku = 'PARA500', description = 'Paracetamol 500 mg',
                                        laboratory = 'Lab Demo'))
    assert isinstance(created, ProductOut)
    with pytest.raises(RegisterAlreadyExistsError) as repeated:
        _call(billing_controllers.create_product_controller, dynamodb_resource = dynamodb,
              product = ProductIn(sku = 'PARA500', description = 'Otro', laboratory = 'Lab'))
    assert repeated.value.detail == BillingError.SKU_ALREADY_EXISTS.value

    edited = _call(billing_controllers.update_product_controller, dynamodb_resource = dynamodb,
                   edit = ProductEdit(sku = 'PARA500', patch = ProductPatch(min_stock = 5)))
    assert edited.min_stock == 5

    received = _call(billing_controllers.receive_purchase_controller,
                     dynamodb_resource = dynamodb, note = PurchaseNoteIn(
                         supplier_name = 'Droguería Demo', lines = [PurchaseLineIn(
                             sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                             sale_price = 6.0, expiry_date = LATER)]))
    assert isinstance(received, PurchaseNoteOut)
    one = _call(billing_controllers.get_purchase_controller, dynamodb_resource = dynamodb,
                purchase_id = received.purchase_id)
    assert one.purchase_id == received.purchase_id
    purchases = _call(billing_controllers.list_purchases_controller,
                      dynamodb_resource = dynamodb, window = DateWindow())
    assert isinstance(purchases, PurchaseNotesResponse) and purchases.total == 1

    listed = _call(billing_controllers.list_products_controller, dynamodb_resource = dynamodb,
                   only_active = True)
    assert isinstance(listed, ProductsResponse)
    assert listed.items[0].available_quantity == 10
    product = _call(billing_controllers.get_product_controller, dynamodb_resource = dynamodb,
                    sku = 'PARA500')
    assert product.sale_price == 6.0

    lots = _call(billing_controllers.lots_controller, dynamodb_resource = dynamodb,
                 query = LotQuery(sku = 'PARA500'))
    assert isinstance(lots, LotsResponse)
    repriced = _call(billing_controllers.reprice_lot_controller, dynamodb_resource = dynamodb,
                     edit = LotEdit(sku = 'PARA500', lot_id = lots.items[0].lot_id,
                                    sale_price = 6.5))
    assert repriced.items[0].sale_price == 6.5

    with pytest.raises(RegisterNotFoundError) as unknown:
        _call(billing_controllers.get_product_controller, dynamodb_resource = dynamodb,
              sku = 'NADA')
    assert unknown.value.detail == BillingError.PRODUCT_NOT_FOUND.value
    assert audited == [('Product', 'CREATE'), ('Product', 'UPDATE'),
                       ('PurchaseNote', 'CREATE'), ('Lot', 'REPRICE')]


# --- sales -----------------------------------------------------------------------

def test_a_sale_is_issued_audited_listed_and_its_qr_printed(
    dynamodb,
    audited,
    sent
):
    '''
        The sale path of the counter: issue an invoiced sale, read it, list it
        and print its QR; a sale beyond the stock charges nothing.
    '''
    _invoicing_shop(dynamodb)
    note = _call(billing_controllers.issue_sale_controller, current_user = CASHIER,
                 dynamodb_resource = dynamodb, note = SaleNoteIn(
                     lines = [SaleLineIn(sku = 'CONS1', quantity = 2)], buyer = BUYER))
    assert isinstance(note, SaleNoteOut)
    assert note.invoice is not None and len(sent) == 1

    one = _call(billing_controllers.get_sale_controller, dynamodb_resource = dynamodb,
                sale_id = note.sale_id)
    assert one.sale_id == note.sale_id
    listed = _call(billing_controllers.list_sales_controller, dynamodb_resource = dynamodb,
                   window = DateWindow())
    assert isinstance(listed, SaleNotesResponse) and listed.total == 1
    qr = _call(billing_controllers.sale_qr_controller, dynamodb_resource = dynamodb,
               sale_id = note.sale_id)
    assert isinstance(qr, InvoiceQrOut) and qr.svg.startswith('<svg')

    with pytest.raises(InvalidInputError) as refused:
        _call(billing_controllers.issue_sale_controller, current_user = CASHIER,
              dynamodb_resource = dynamodb, note = SaleNoteIn(
                  lines = [SaleLineIn(sku = 'CONS1', quantity = 99)], buyer = BUYER))
    assert refused.value.detail == BillingError.INSUFFICIENT_STOCK.value
    assert audited == [('SaleNote', 'ISSUE')]
