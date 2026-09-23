'''
    Tests for the pharmacy billing module, against DynamoDB (moto) — which is
    what the deployment serves.

    What they are here to protect: the batch that leaves is the one expiring
    first, a sale that cannot be covered charges nothing, cancelling a note
    puts the units back where they came from, and one pharmacy never sees
    another's shelf.
'''
from datetime import date, timedelta

import boto3
import pytest
from moto import mock_aws

from models.pharmacy import (
    LOTS_TABLE,
    PRODUCTS_TABLE,
    PURCHASES_TABLE,
    SALES_TABLE,
    SETTINGS_TABLE
)
from schemas.pharmacy import (
    Buyer,
    LotPricePatch,
    PaymentMethod,
    PharmacyError,
    PharmacySettings,
    ProductIn,
    PurchaseLineIn,
    PurchaseNoteIn,
    SaleLineIn,
    SaleNoteIn,
    SaleStatus
)
from services import pharmacy, pharmacy_purchases, pharmacy_sales, pharmacy_stock
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)

OWNER = 'farmacia.demo@bearsoft.com.bo'
OTHER_OWNER = 'otra.farmacia@bearsoft.com.bo'
CASHIER = 'cajera@farmacia.bo'

TODAY = date(2026, 9, 22)
SOON = TODAY + timedelta(days = 30)
LATER = TODAY + timedelta(days = 400)


def _create_tables(resource):
    '''
        The five tables, with the same keys `create_dynamodb_tables.sh` gives
        them in AWS.

        Args:
            resource: The moto DynamoDB resource.
    '''
    for name, sort_key in ((PRODUCTS_TABLE, 'sku'), (LOTS_TABLE, 'lot_key'),
                           (SALES_TABLE, 'sale_id'), (PURCHASES_TABLE, 'purchase_id'),
                           (SETTINGS_TABLE, 'setting_key')):
        resource.create_table(
            TableName = name,
            KeySchema = [{'AttributeName': 'owner', 'KeyType': 'HASH'},
                         {'AttributeName': sort_key, 'KeyType': 'RANGE'}],
            AttributeDefinitions = [{'AttributeName': 'owner', 'AttributeType': 'S'},
                                    {'AttributeName': sort_key, 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )


@pytest.fixture(name = 'dynamodb')
def _dynamodb():
    '''
        A mocked DynamoDB with the five tables and one pharmacy set up.

        Returns:
            ServiceResource: Ready to use.
    '''
    with mock_aws():
        resource = boto3.resource('dynamodb', region_name = 'us-east-1')
        _create_tables(resource)
        pharmacy.save_settings(resource, OWNER, PharmacySettings(
            trade_name = 'Farmacia Demo', document = '1234567', sale_series = 'A'
        ))
        yield resource


def _register(
    resource,
    sku = 'PARA500',
    description = 'Paracetamol 500 mg x 10'
):
    '''
        Registers one SKU in the demo pharmacy.

        Args:
            resource: The DynamoDB resource.
            sku (str): Code to register.
            description (str): What it is.

        Returns:
            ProductOut: The stored product.
    '''
    return pharmacy.create_product(resource, OWNER, ProductIn(
        sku = sku, description = description, laboratory = 'Lab Demo'
    ))


def _receive(
    resource,
    lines,
    supplier = 'Droguería Demo'
):
    '''
        Records a delivery of the given lines.

        Args:
            resource: The DynamoDB resource.
            lines (list): PurchaseLineIn entries.
            supplier (str): Who delivered.

        Returns:
            PurchaseNoteOut: The recorded note.
    '''
    return pharmacy_purchases.receive_purchase(
        resource, OWNER, PurchaseNoteIn(supplier_name = supplier, lines = lines), CASHIER
    )


def _sell(
    resource,
    lines,
    buyer = None
):
    '''
        Issues a sale note.

        Args:
            resource: The DynamoDB resource.
            lines (list): SaleLineIn entries.
            buyer: Optional buyer.

        Returns:
            SaleNoteOut: The issued note.
    '''
    note = SaleNoteIn(lines = lines, payment_method = PaymentMethod.EFECTIVO,
                      buyer = buyer or Buyer())
    return pharmacy_sales.issue_sale(resource, OWNER, note, CASHIER)


# --- catalogue ---------------------------------------------------------------

def test_a_sku_is_registered_once(dynamodb):
    '''The same code twice is the same product, not a second one.'''
    _register(dynamodb)
    with pytest.raises(RegisterAlreadyExistsError) as error:
        _register(dynamodb)
    assert error.value.detail == PharmacyError.SKU_ALREADY_EXISTS.value


def test_catalogue_reports_stock_and_the_price_that_will_be_charged(dynamodb):
    '''
        The price shown is the one on the batch that leaves next, not an
        average and not the newest: it is what the shelf label says.
    '''
    _register(dynamodb)
    _receive(dynamodb, [
        PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                       sale_price = 6.0, expiry_date = LATER),
        PurchaseLineIn(sku = 'PARA500', quantity = 5, unit_cost = 3.5,
                       sale_price = 7.5, expiry_date = SOON)
    ])

    catalogue = pharmacy.list_products(dynamodb, OWNER)

    assert catalogue.total == 1
    product = catalogue.items[0]
    assert product.available_quantity == 15
    assert product.sale_price == 7.5
    assert product.next_expiry == SOON


def test_a_product_below_its_minimum_is_flagged(dynamodb):
    '''The pharmacy has to see what it is about to run out of.'''
    pharmacy.create_product(dynamodb, OWNER, ProductIn(
        sku = 'IBU400', description = 'Ibuprofeno 400 mg', laboratory = 'Lab Demo',
        min_stock = 20
    ))
    _receive(dynamodb, [PurchaseLineIn(sku = 'IBU400', quantity = 5,
                                       unit_cost = 2.0, sale_price = 4.0)])

    product = pharmacy.get_product(dynamodb, OWNER, 'IBU400')

    assert product.available_quantity == 5
    assert product.below_minimum is True


# --- FEFO --------------------------------------------------------------------

def test_the_batch_that_expires_first_leaves_first(dynamodb):
    '''
        PEPS with the clock: what governs is the expiry date, not the order the
        boxes arrived in. The batch received second expires sooner, so it is
        the one that must be sold.
    '''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER,
                                       lot_code = 'VIEJO')])
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 4, unit_cost = 3.5,
                                       sale_price = 7.5, expiry_date = SOON,
                                       lot_code = 'PRONTO')])

    note = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 4)])

    allocations = note.lines[0].allocations
    assert len(allocations) == 1
    assert allocations[0].lot_code == 'PRONTO'
    assert note.total == 30.0
    assert note.cost == 14.0


def test_a_line_spans_batches_and_each_keeps_its_own_price(dynamodb):
    '''
        When the soonest batch does not cover the line, the rest comes from the
        next one — at the next one's price, because that is what the pharmacy
        paid for and priced.
    '''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 3, unit_cost = 3.5,
                                       sale_price = 7.5, expiry_date = SOON)])
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER)])

    note = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 5)])

    allocations = note.lines[0].allocations
    assert [allocation.quantity for allocation in allocations] == [3, 2]
    assert [allocation.unit_price for allocation in allocations] == [7.5, 6.0]
    # 3 x 7,50 + 2 x 6,00
    assert note.total == 34.5
    assert note.cost == 16.5
    assert note.margin == 18.0


def test_a_batch_with_no_expiry_is_sold_last(dynamodb):
    '''
        An unknown date must never jump ahead of a box that is about to expire:
        the one that can spoil goes first.
    '''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 5, unit_cost = 3.0,
                                       sale_price = 6.0, lot_code = 'SIN_FECHA')])
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 5, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = SOON,
                                       lot_code = 'CON_FECHA')])

    note = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 2)])

    assert note.lines[0].allocations[0].lot_code == 'CON_FECHA'


# --- selling -----------------------------------------------------------------

def test_a_sale_without_stock_charges_nothing(dynamodb):
    '''
        Overselling is the failure that matters at a counter: the note must not
        exist and the numbering must not advance.
    '''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 2, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = SOON)])

    with pytest.raises(InvalidInputError) as error:
        _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 3)])

    assert error.value.detail == PharmacyError.INSUFFICIENT_STOCK.value
    assert pharmacy_sales.list_sales(dynamodb, OWNER).total == 0
    assert pharmacy_stock.lots_of(dynamodb, OWNER, 'PARA500').available_quantity == 2


def test_selling_takes_the_units_off_the_shelf(dynamodb):
    '''What was sold is no longer available to sell again.'''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = SOON)])

    _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 4)])

    assert pharmacy_stock.lots_of(dynamodb, OWNER, 'PARA500').available_quantity == 6


def test_an_unknown_sku_cannot_be_sold(dynamodb):
    '''Selling what is not in the catalogue would price nothing.'''
    with pytest.raises(RegisterNotFoundError) as error:
        _sell(dynamodb, [SaleLineIn(sku = 'NO_EXISTE', quantity = 1)])
    assert error.value.detail == PharmacyError.PRODUCT_NOT_FOUND.value


def test_the_same_sku_twice_in_one_note_is_refused(dynamodb):
    '''
        The second line would be priced against the batches the first already
        took, so the note would charge two different prices for one purchase.
    '''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0)])

    with pytest.raises(InvalidInputError) as error:
        _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 1),
                         SaleLineIn(sku = 'PARA500', quantity = 2)])

    assert error.value.detail == PharmacyError.DUPLICATE_LINE.value


def test_a_discount_is_refused_where_discounts_are_off(dynamodb):
    '''
        Discounts are a decision of each pharmacy, not of the software: with
        them off, a line carrying one is a mistake at the till.
    '''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0)])

    with pytest.raises(InvalidInputError) as error:
        _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 1, discount = 1.0)])

    assert error.value.detail == PharmacyError.DISCOUNTS_DISABLED.value


def test_a_discount_applies_once_enabled(dynamodb):
    '''With discounts on, the line total drops by the amount given.'''
    pharmacy.save_settings(dynamodb, OWNER, PharmacySettings(
        trade_name = 'Farmacia Demo', discounts_enabled = True
    ))
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0)])

    note = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 2, discount = 2.0)])

    assert note.subtotal == 12.0
    assert note.discount == 2.0
    assert note.total == 10.0


def test_a_discount_larger_than_its_line_is_refused(dynamodb):
    '''A line cannot be worth less than nothing.'''
    pharmacy.save_settings(dynamodb, OWNER, PharmacySettings(
        trade_name = 'Farmacia Demo', discounts_enabled = True
    ))
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0)])

    with pytest.raises(InvalidInputError) as error:
        _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 1, discount = 99.0)])

    assert error.value.detail == PharmacyError.DISCOUNT_ABOVE_LINE.value


def test_notes_are_numbered_per_pharmacy_and_never_repeat(dynamodb):
    '''
        Each pharmacy numbers its own documents, and the counter only moves
        forward: two notes sharing a number would be two papers claiming to be
        the same sale.
    '''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0)])

    numbers = [_sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 1)]).number
               for _ in range(3)]

    assert numbers == ['A-000001', 'A-000002', 'A-000003']
    assert pharmacy.get_settings(dynamodb, OWNER).next_sale_number == 4


def test_the_buyer_travels_with_the_note(dynamodb):
    '''A pharmacy asks for name and NIT to invoice, and it has to survive.'''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0)])

    issued = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 1)],
                   buyer = Buyer(name = 'Juan Pérez', document = '9876543'))
    stored = pharmacy_sales.get_sale(dynamodb, OWNER, issued.sale_id)

    assert stored.buyer.name == 'Juan Pérez'
    assert stored.buyer.document == '9876543'


# --- cancelling --------------------------------------------------------------

def test_cancelling_returns_the_units_to_their_own_batches(dynamodb):
    '''
        Not "to stock": to the very batches they left, each with its cost and
        its expiry. Anything else would quietly re-cost the shelf.
    '''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 3, unit_cost = 3.5,
                                       sale_price = 7.5, expiry_date = SOON,
                                       lot_code = 'PRONTO')])
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER,
                                       lot_code = 'LEJOS')])
    note = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 5)])

    cancelled = pharmacy_sales.cancel_sale(dynamodb, OWNER, note.sale_id, CASHIER)

    assert cancelled.status == SaleStatus.CANCELLED
    lots = pharmacy_stock.lots_of(dynamodb, OWNER, 'PARA500')
    by_code = {lot.lot_code: lot.quantity_remaining for lot in lots.items}
    assert by_code == {'PRONTO': 3, 'LEJOS': 10}


def test_a_note_is_cancelled_once(dynamodb):
    '''Cancelling twice would return the units twice.'''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0)])
    note = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 2)])
    pharmacy_sales.cancel_sale(dynamodb, OWNER, note.sale_id, CASHIER)

    with pytest.raises(InvalidInputError) as error:
        pharmacy_sales.cancel_sale(dynamodb, OWNER, note.sale_id, CASHIER)

    assert error.value.detail == PharmacyError.SALE_ALREADY_CANCELLED.value
    assert pharmacy_stock.lots_of(dynamodb, OWNER, 'PARA500').available_quantity == 10


def test_a_cancelled_note_stops_counting_as_money(dynamodb):
    '''The day's total is what was charged, not what was written.'''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0)])
    kept = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 1)])
    voided = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 2)])
    pharmacy_sales.cancel_sale(dynamodb, OWNER, voided.sale_id, CASHIER)

    listing = pharmacy_sales.list_sales(dynamodb, OWNER)

    assert listing.total == 2
    assert listing.total_amount == kept.total


# --- isolation and pricing ---------------------------------------------------

def test_one_pharmacy_never_sees_another(dynamodb):
    '''
        The owner is part of the key, so another pharmacy's SKU answers exactly
        like one that does not exist.
    '''
    _register(dynamodb)

    assert pharmacy.list_products(dynamodb, OTHER_OWNER).total == 0
    with pytest.raises(RegisterNotFoundError):
        pharmacy.get_product(dynamodb, OTHER_OWNER, 'PARA500')


def test_repricing_a_batch_leaves_its_cost_alone(dynamodb):
    '''
        Rewriting the cost would rewrite the margin of every sale already made
        from the batch.
    '''
    _register(dynamodb)
    note = _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10,
                                              unit_cost = 3.0, sale_price = 6.0)])
    lot_id = note.lines[0].lot_id

    updated = pharmacy_stock.reprice_lot(dynamodb, OWNER, 'PARA500', lot_id,
                                         LotPricePatch(sale_price = 8.0))

    assert updated.sale_price == 8.0
    assert updated.unit_cost == 3.0
    assert pharmacy_stock.lots_of(dynamodb, OWNER, 'PARA500').items[0].sale_price == 8.0


def test_a_delivery_of_an_unknown_sku_is_refused(dynamodb):
    '''A batch has to belong to a product the pharmacy knows how to sell.'''
    with pytest.raises(RegisterNotFoundError) as error:
        _receive(dynamodb, [PurchaseLineIn(sku = 'NO_EXISTE', quantity = 1,
                                           unit_cost = 1.0, sale_price = 2.0)])
    assert error.value.detail == PharmacyError.PRODUCT_NOT_FOUND.value


def test_a_pharmacy_without_settings_cannot_sell(dynamodb):
    '''
        The note carries the shop's name and its numbering series: selling
        before the shop exists would print a paper belonging to nobody.
    '''
    with pytest.raises(RegisterNotFoundError) as error:
        pharmacy_sales.issue_sale(
            dynamodb, OTHER_OWNER,
            SaleNoteIn(lines = [SaleLineIn(sku = 'PARA500', quantity = 1)]), CASHIER
        )
    assert error.value.detail == PharmacyError.SETTINGS_NOT_FOUND.value
