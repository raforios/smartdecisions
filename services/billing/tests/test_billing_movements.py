'''
    The shelf and the purchases SmartBilling sends to SmartDecisions, the
    category that travels with a product, and a movement telling both
    analyses at once.
'''
from types import SimpleNamespace
from unittest.mock import patch

from schemas.billing import ProductIn, PurchaseLineIn, SaleLineIn
from services import billing, billing_bridge, billing_finance, billing_movements
from tests.test_billing import ( # pylint: disable=unused-import
    LATER,
    OWNER,
    _dynamodb,
    _receive,
    _register,
    _sell
)
from tests.test_billing_bridge import _switch

TODAY = '2026-11-08'


def test_the_shelf_is_each_products_units_cost_and_next_price(dynamodb):
    '''Two batches: units added, cost averaged, price of the one that leaves first.'''
    _register(dynamodb)
    _register(dynamodb, sku = 'EMPTY', description = 'Sin stock')
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER),
                        PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 5.0,
                                       sale_price = 8.0)])
    _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 4)])
    rows = {row['product_id']: row for row in billing_bridge.stock_rows(dynamodb, OWNER, TODAY)}
    assert (rows['PARA500']['on_hand'], rows['PARA500']['unit_price']) == (16.0, 6.0)
    assert rows['PARA500']['unit_cost'] == round((6 * 3.0 + 10 * 5.0) / 16, 2)
    assert (rows['EMPTY']['on_hand'], rows['EMPTY']['unit_cost']) == (0, None)
    assert rows['PARA500']['snapshot_date'] == TODAY


def test_a_purchase_and_a_movement_reach_smartdecisions(dynamodb):
    '''The purchase goes as its lines; a movement sends its month and the shelf.'''
    _register(dynamodb)
    _switch(dynamodb, True)
    purchase = _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 5,
                                                  unit_cost = 3.0, sale_price = 6.0,
                                                  expiry_date = LATER)])
    queued: list = []
    request = SimpleNamespace(headers = {'Authorization': 'Bearer t'})
    with patch.object(billing_bridge, 'queue_request', lambda *call: queued.append(call)):
        billing_bridge.share_purchase(dynamodb, OWNER, purchase, request)
        billing_movements.share_movement(dynamodb, OWNER, purchase.created_at, request)
    paths = [sent['path'] for _url, _owner, sent in queued]
    assert paths == [billing_bridge.PURCHASES_PATH, billing_finance.LOADS_PATH,
                     billing_bridge.STOCK_PATH]
    line = queued[0][2]['body']['rows'][0]
    assert (line['product_id'], line['quantity'], line['currency']) == ('PARA500', 5, 'BOB')


def test_the_category_travels_with_the_product(dynamodb):
    '''What the shop groups a product under reaches SmartDecisions' master.'''
    product = billing.create_product(dynamodb, OWNER, ProductIn(
        sku = 'IBU400', description = 'Ibuprofeno 400', laboratory = 'Lab',
        category = 'Analgésicos'))
    assert billing_bridge.product_record(product)['category'] == 'Analgésicos'
