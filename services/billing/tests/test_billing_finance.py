'''
    SmartBilling → FINANCE: each month as its accounts' totals, a cancelled
    sale counted nowhere, a return in the month of its note, and the opening
    and closing inventory rebuilt from today's shelf.
'''
from types import SimpleNamespace
from unittest.mock import patch

from schemas.billing import PurchaseLineIn, PurchaseNoteIn, SaleLineIn
from services import billing_bridge, billing_finance, billing_purchases, billing_sales
from services.utils import get_current_time_gmt
from tests.test_billing import ( # pylint: disable=unused-import
    CASHIER,
    LATER,
    OWNER,
    _dynamodb,
    _receive,
    _register,
    _sell
)
from tests.test_billing_bridge import _switch
from tests.test_billing_returns import ( # pylint: disable=unused-import
    _adjustments,
    _return,
    _sale
)
from tests.test_billing_sale_invoice import _sent # pylint: disable=unused-import

ACCOUNTS = billing_finance.ACCOUNTS


def _amounts(rows: list) -> dict:
    '''{account: amount} of the current month's rows.'''
    month = get_current_time_gmt().date().isoformat()[:7]
    return {row['account_code']: row['amount'] for row in rows if row['date'] == month}


def test_a_month_is_its_accounts_and_its_inventory(dynamodb):
    '''Ten units bought at 3, two sold at 6, one sold and cancelled.'''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER)])
    _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 2)])
    cancelled = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 1)])
    billing_sales.cancel_sale(dynamodb, OWNER, cancelled.sale_id, CASHIER)

    month = get_current_time_gmt().date().isoformat()[:7]
    rows = billing_finance.finance_rows(dynamodb, OWNER, month)
    amounts = _amounts(rows)
    assert len(rows) == len(ACCOUNTS)
    assert amounts[ACCOUNTS['BILLING_FINANCE_SALES_UNINVOICED']] == 12.0
    assert amounts[ACCOUNTS['BILLING_FINANCE_SALES_INVOICED']] == 0.0
    assert amounts[ACCOUNTS['BILLING_FINANCE_PURCHASES_UNINVOICED']] == 30.0
    assert amounts[ACCOUNTS['BILLING_FINANCE_CLOSING_INVENTORY']] == 24.0
    assert amounts[ACCOUNTS['BILLING_FINANCE_INVENTORY']] == 24.0
    assert amounts[ACCOUNTS['BILLING_FINANCE_OPENING_INVENTORY']] == 0.0
    taxed = {row['account_code'] for row in rows if row['taxes_included']}
    assert taxed == {ACCOUNTS['BILLING_FINANCE_SALES_INVOICED'],
                     ACCOUNTS['BILLING_FINANCE_SERVICES_INVOICED'],
                     ACCOUNTS['BILLING_FINANCE_PURCHASES_INVOICED']}


def test_an_invoiced_purchase_values_the_shelf_without_its_vat(dynamodb):
    '''FINANCE takes the VAT off an invoiced purchase; the inventory must too, or the
    cost of sales comes out short by that VAT (seen live on 8-nov).'''
    _register(dynamodb)
    billing_purchases.receive_purchase(dynamodb, OWNER, PurchaseNoteIn(
        supplier_name = 'Droguería Demo', invoice_number = 'F-1', lines = [PurchaseLineIn(
            sku = 'PARA500', quantity = 10, unit_cost = 3.0, sale_price = 6.0,
            expiry_date = LATER)]), CASHIER)
    _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 2)])
    month = get_current_time_gmt().date().isoformat()[:7]
    amounts = _amounts(billing_finance.finance_rows(dynamodb, OWNER, month))
    net = 1 - billing_bridge.VAT_RATE
    assert amounts[ACCOUNTS['BILLING_FINANCE_PURCHASES_INVOICED']] == 30.0
    assert amounts[ACCOUNTS['BILLING_FINANCE_CLOSING_INVENTORY']] == round(8 * 3.0 * net, 2)
    cost_of_sales = (amounts[ACCOUNTS['BILLING_FINANCE_OPENING_INVENTORY']] +
                     amounts[ACCOUNTS['BILLING_FINANCE_PURCHASES_INVOICED']] * net -
                     amounts[ACCOUNTS['BILLING_FINANCE_CLOSING_INVENTORY']])
    assert round(cost_of_sales, 2) == round(2 * 3.0 * net, 2)


def test_a_return_counts_in_its_month_and_its_units_come_back( # pylint: disable=unused-argument
    dynamodb,
    sale,
    adjustments
):
    '''The invoiced sale stays whole; what came back goes to returns and to the shelf.'''
    month = get_current_time_gmt().date().isoformat()[:7]
    before = _amounts(billing_finance.finance_rows(dynamodb, OWNER, month))
    note = _return(dynamodb, sale.sale_id)
    after = _amounts(billing_finance.finance_rows(dynamodb, OWNER, month))
    assert after[ACCOUNTS['BILLING_FINANCE_SERVICES_INVOICED']] + after[
        ACCOUNTS['BILLING_FINANCE_SALES_INVOICED']] == sale.total
    assert after[ACCOUNTS['BILLING_FINANCE_RETURNS']] == note.amount_returned
    back = sum(allocation.quantity * allocation.unit_cost
               for line in note.lines for allocation in line.allocations)
    assert after[ACCOUNTS['BILLING_FINANCE_CLOSING_INVENTORY']] == round(
        before[ACCOUNTS['BILLING_FINANCE_CLOSING_INVENTORY']] + back, 2)


def test_the_month_is_queued_to_finance_only_with_the_switch_on(dynamodb):
    '''Off, nothing leaves; on, the month goes to FINANCE's queue as the cashier.'''
    _register(dynamodb)
    queued: list = []
    request = SimpleNamespace(headers = {'Authorization': 'Bearer t'})
    today = get_current_time_gmt().date().isoformat()
    with patch.object(billing_bridge, 'queue_request', lambda *call: queued.append(call)):
        billing_finance.share_month(dynamodb, OWNER, today, request)
        assert not queued
        _switch(dynamodb, True)
        billing_finance.share_month(dynamodb, OWNER, today, request)
        billing_finance.share_month(dynamodb, OWNER, '2999-01-01', request)
    assert len(queued) == 1
    queue_url, owner, sent = queued[0]
    assert (queue_url, owner, sent['path']) == (billing_finance.FINANCE_QUEUE_URL, OWNER,
                                                billing_finance.LOADS_PATH)
    assert sent['body']['flow'] == 'PROCESSED' and sent['authorization'] == 'Bearer t'
