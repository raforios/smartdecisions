'''
    SmartBilling → SmartDecisions: what a sale and a product look like on the
    way out, and that nothing leaves unless the shop turned the switch on.

    The queue is replaced by a recorder.
'''
import re
from types import SimpleNamespace
from unittest.mock import patch

from schemas.billing import (
    BillingSettings,
    PaymentMethod,
    ProductUnit,
    PurchaseLineIn,
    SaleLineIn
)
from services import billing, billing_bridge, billing_sales
from tests.test_billing import ( # pylint: disable=unused-import
    CASHIER,
    LATER,
    OWNER,
    _dynamodb,
    _receive,
    _register,
    _sell
)
from tests.test_billing_returns import ( # pylint: disable=unused-import
    _adjustments,
    _cancel,
    _cancellations,
    _return,
    _sale
)
from tests.test_billing_sale_invoice import _sent # pylint: disable=unused-import

AUTHORIZATION = 'Bearer cashier-token'


def _switch(
    resource,
    wanted: bool
) -> None:
    '''
        Turns the shop's SmartDecisions switch on or off.

        Args:
            resource: The DynamoDB resource.
            wanted (bool): Whether the shop sends.
    '''
    current = billing.get_settings(resource, OWNER)
    billing.save_settings(resource, OWNER, BillingSettings(**current.model_dump(
        include = set(BillingSettings.model_fields)) | {'send_to_smartdecisions': wanted}))


def _shared(
    action,
    resource,
    *arguments
) -> list:
    '''
        Runs a share and returns what was queued.

        Args:
            action: share_sale or share_product.
            resource: The DynamoDB resource.
            *arguments: What it shares.

        Returns:
            list: (owner, request) per queued request.
    '''
    queued: list = []
    request = SimpleNamespace(headers = {'Authorization': AUTHORIZATION})
    with patch.object(billing_bridge, '_queue', lambda *call: queued.append(call)):
        action(resource, OWNER, *arguments, request)
    return queued


def _a_sale(resource):
    '''
        One sale of two units paid by card.

        Args:
            resource: The DynamoDB resource.

        Returns:
            SaleNoteOut: The sale.
    '''
    _register(resource)
    _receive(resource, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER)])
    return _sell(resource, [SaleLineIn(sku = 'PARA500', quantity = 2)])


def test_a_sale_becomes_smartdecisions_sales_lines(dynamodb):
    '''One line per product, with price and cost per unit and the card as one.'''
    sale = _a_sale(dynamodb).model_copy(update = {'payment_method': PaymentMethod.DEBIT_CARD})
    rows = billing_bridge.sale_rows(sale)
    assert rows == [{
        'date': sale.created_at[:10], 'order_id': sale.number, 'pos_name': None,
        'seller': sale.created_by, 'product_id': 'PARA500',
        'product_name': sale.lines[0].description, 'quantity': 2, 'unit_price': 6.0,
        'unit_cost': 3.0, 'total_amount': 12.0, 'payment_terms': 'CASH',
        'payment_method': 'CARD'
    }]


def test_a_product_becomes_a_master_record(dynamodb):
    '''The laboratory is the supplier; the unit travels as its code.'''
    product = _register(dynamodb)
    record = billing_bridge.product_record(product)
    assert record['sku'] == 'PARA500' and record['supplier'] == product.laboratory
    assert record['unit'] == ProductUnit.UNIT.value


def test_nothing_leaves_with_the_switch_off(dynamodb):
    '''Off by default: the sale stays in SmartBilling.'''
    assert not _shared(billing_bridge.share_sale, dynamodb, _a_sale(dynamodb))


def test_with_the_switch_on_sale_and_product_are_queued_with_the_token(dynamodb):
    '''The sale goes to the live sales, the product to the master, both as the cashier.'''
    sale = _a_sale(dynamodb)
    _switch(dynamodb, True)
    assert _shared(billing_bridge.share_sale, dynamodb, sale) == [(OWNER, {
        'path': billing_bridge.LIVE_SALES_PATH, 'body': {'rows': billing_bridge.sale_rows(sale)},
        'authorization': AUTHORIZATION})]
    product = billing.get_product(dynamodb, OWNER, 'PARA500')
    queued = _shared(billing_bridge.share_product, dynamodb, product)
    assert queued[0][1]['path'] == billing_bridge.PRODUCTS_PATH
    assert queued[0][1]['body'] == {'products': [billing_bridge.product_record(product)]}


def test_a_queue_failure_is_logged_and_never_raises(monkeypatch):
    '''The sale is complete either way: a queue that refuses only leaves a log.'''
    class _Refusing:  # pylint: disable=too-few-public-methods
        '''An SQS client that refuses every message.'''

        def send_message(
            self,
            **_message
        ):
            '''Refuses, as a queue without permission does.'''
            raise billing_bridge.ClientError({'Error': {'Code': 'AccessDenied'}}, 'SendMessage')
    monkeypatch.setattr(billing_bridge.boto3, 'client', lambda _name: _Refusing())
    billing_bridge._queue(OWNER, {'path': billing_bridge.PRODUCTS_PATH, 'body': {}, # pylint: disable=protected-access
                                  'authorization': AUTHORIZATION})


def test_a_cancellation_undoes_the_sale_and_leaves_nothing_of_it(dynamodb):
    '''Cancelled, the record stands and the sale has no lines; valid again, it is reverted.'''
    sale = _a_sale(dynamodb)
    billing_sales.cancel_sale(dynamodb, OWNER, sale.sale_id, CASHIER)
    stored = billing_sales.read_sale(dynamodb, OWNER, sale.sale_id)
    record = billing_bridge.cancellation_record(dynamodb, OWNER, stored)
    assert (record['kind'], record['state'], record['order_id']) == ('CANCELLATION', 'ACTIVE',
                                                                     sale.number)
    assert record['lines'] == [{'product_id': 'PARA500', 'product_name': sale.lines[0].description,
                                'quantity': 2, 'amount': 12.0}]
    assert record['rows'] == [] and record['reason'] is None

    valid_again = billing_bridge.cancellation_record(dynamodb, OWNER,
                                                     {**stored, 'status': 'ISSUED'})
    assert valid_again['state'] == 'REVERTED'
    assert [row['quantity'] for row in valid_again['rows']] == [2]


def test_a_return_leaves_what_the_buyer_kept( # pylint: disable=unused-argument
    dynamodb,
    sale,
    adjustments,
    cancellations
):
    '''One of two units back: one undone, one kept; the note cancelled, both kept again.'''
    note = _return(dynamodb, sale.sale_id)
    stored = billing_sales.read_sale(dynamodb, OWNER, sale.sale_id)
    record = billing_bridge.return_record(stored, stored['credit_notes'][0])
    assert (record['kind'], record['state'], record['reversal_id']) == (
        'RETURN', 'ACTIVE', f'NC-{note.number}')
    assert [line['quantity'] for line in record['lines']] == [1]
    assert [row['quantity'] for row in record['rows']] == [1]

    _cancel(dynamodb, note)
    stored = billing_sales.read_sale(dynamodb, OWNER, sale.sale_id)
    record = billing_bridge.return_record(stored, stored['credit_notes'][0])
    assert record['state'] == 'REVERTED'
    assert [row['quantity'] for row in record['rows']] == [2]


def test_cancellations_and_returns_are_queued_with_the_switch_on( # pylint: disable=unused-argument
    dynamodb,
    sale,
    adjustments
):
    '''Both go to the reversals path, built from what BILLING stored.'''
    _switch(dynamodb, True)
    note = _return(dynamodb, sale.sale_id)
    queued = _shared(billing_bridge.share_return, dynamodb, note)
    assert queued[0][1]['path'] == billing_bridge.REVERSALS_PATH
    assert queued[0][1]['body']['kind'] == 'RETURN'
    queued = _shared(billing_bridge.share_cancellation, dynamodb, sale.sale_id)
    assert queued[0][1]['body']['kind'] == 'CANCELLATION'


def test_a_company_name_with_spaces_gets_a_valid_line_of_its_own(monkeypatch):
    '''SQS refuses spaces in a group id; each shop still gets one line, always the same.'''
    sent: list = []

    class _Recording:  # pylint: disable=too-few-public-methods
        '''An SQS client that keeps what it is sent.'''

        def send_message(
            self,
            **message
        ):
            '''Keeps the message.'''
            sent.append(message)
    monkeypatch.setattr(billing_bridge.boto3, 'client', lambda _name: _Recording())
    billing_bridge._queue('The Pharma', {'path': billing_bridge.PRODUCTS_PATH, 'body': {}, # pylint: disable=protected-access
                                         'authorization': AUTHORIZATION})
    group = sent[0]['MessageGroupId']
    assert re.fullmatch(r'[0-9a-f]{64}', group)
    assert group == billing_bridge.queue_group('The Pharma') != billing_bridge.queue_group('Otra')
