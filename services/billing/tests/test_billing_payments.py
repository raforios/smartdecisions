'''
    Tests for combined payments.

    What they protect: the parts add up to the total and a method appears
    once; the invoice carries the SIN's code of the combination, read from
    its catalogue however the catalogue spells it; a card number travels when
    any part was a card; and the till counts each part in its own method.
'''
import pytest

from schemas.billing import (
    BillingError,
    Payment,
    PaymentMethod,
    PurchaseLineIn,
    SaleLineIn,
    SaleNoteIn
)
from services import billing_cash, billing_payments, billing_sales
from services.exceptions import InvalidInputError
from tests.test_billing import CASHIER, LATER, OWNER, _dynamodb, _receive, _register # pylint: disable=unused-import
from tests.test_billing_sale_invoice import ( # pylint: disable=unused-import
    BUYER,
    PAYMENT_CATALOGUE,
    _invoicing_shop,
    _sent
)

CASH, CARD, QR = PaymentMethod.EFECTIVO, PaymentMethod.TARJETA_DEBITO, PaymentMethod.QR


def _note(
    payments,
    **fields
):
    '''
        Two units of the consulting product, Bs 200 in all, paid as given.

        Args:
            payments: The parts, or None for a single method.
            **fields: Other fields of the note.

        Returns:
            SaleNoteIn: The note.
    '''
    return SaleNoteIn(lines = [SaleLineIn(sku = 'CONS1', quantity = 2)], buyer = BUYER,
                      payments = payments, **fields)


@pytest.mark.parametrize(('methods', 'code'), [
    ([CASH], 1), ([CARD], 2), ([CASH, CARD], 10), ([CARD, CASH], 10)
])
def test_the_sin_code_of_a_payment_comes_from_its_catalogue(
    methods,
    code
):
    '''
        One method or a combination, in any order, is one entry of the SIN.
    '''
    assert billing_payments.sin_payment_code(PAYMENT_CATALOGUE, methods) == code


def test_the_catalogues_spellings_are_read_as_one():
    '''
        "GIFT-CARD" is one part, and "VALE" is "VALES": the catalogue writes
        the same part several ways.
    '''
    parts = billing_payments._parts # pylint: disable=protected-access

    assert parts('GIFT-CARD') == parts('GIFT CARD') == frozenset({'GIFT CARD'})
    assert parts('EFECTIVO - TARJETA - VALE') == frozenset({'EFECTIVO', 'TARJETA', 'VALES'})
    assert parts('EFECTIVO – TRANSFERENCIA BANCARIA') == \
        frozenset({'EFECTIVO', 'TRANSFERENCIA BANCARIA'})


def test_a_combination_the_sin_does_not_have_is_refused():
    '''
        Cash with QR: QR travels as OTROS, and the SIN has no EFECTIVO-OTROS.
    '''
    with pytest.raises(InvalidInputError) as refused:
        billing_payments.sin_payment_code(PAYMENT_CATALOGUE, [CASH, QR])

    assert refused.value.detail == BillingError.PAYMENT_COMBINATION_UNKNOWN.value


def test_parts_that_do_not_add_up_are_refused():
    '''
        A combined payment must pay exactly the total.
    '''
    note = _note([Payment(method = CASH, amount = 100), Payment(method = CARD, amount = 50)])

    with pytest.raises(InvalidInputError) as refused:
        billing_payments.resolve_payments(note, 200)

    assert refused.value.detail == BillingError.PAYMENTS_DO_NOT_ADD_UP.value


def test_a_method_twice_is_refused():
    '''
        Two parts in cash are one part in cash.
    '''
    note = _note([Payment(method = CASH, amount = 100), Payment(method = CASH, amount = 100)])

    with pytest.raises(InvalidInputError) as refused:
        billing_payments.resolve_payments(note, 200)

    assert refused.value.detail == BillingError.PAYMENT_REPEATED.value


def test_a_combined_invoice_carries_the_combination_and_the_card(
    dynamodb,
    sent
):
    '''
        Cash and card: code 10 in the XML, the masked card number with it,
        and the card is the main method because it paid the most.
    '''
    # pylint: disable=import-outside-toplevel
    import gzip
    _invoicing_shop(dynamodb)

    note = billing_sales.issue_sale(dynamodb, OWNER, _note(
        [Payment(method = CASH, amount = 50), Payment(method = CARD, amount = 150)],
        card_number = '4111111111111111'
    ), CASHIER)

    xml = gzip.decompress(sent[0].archive).decode('utf-8')
    assert '<codigoMetodoPago>10</codigoMetodoPago>' in xml
    assert '<numeroTarjeta>4111000000001111</numeroTarjeta>' in xml
    assert note.payment_method == CARD
    assert [(part.method, part.amount) for part in note.payments] == [(CASH, 50), (CARD, 150)]


def test_an_impossible_combination_is_refused_before_stock_moves(
    dynamodb,
    sent
):
    '''
        Found at the counter, with the shelf untouched.
    '''
    _invoicing_shop(dynamodb)

    with pytest.raises(InvalidInputError):
        billing_sales.issue_sale(dynamodb, OWNER, _note(
            [Payment(method = CASH, amount = 100), Payment(method = QR, amount = 100)]
        ), CASHIER)

    assert not sent
    assert billing_sales.list_sales(dynamodb, OWNER).total == 0


def test_the_till_counts_each_part_in_its_own_method(dynamodb):
    '''
        Only the cash part is cash in the drawer.
    '''
    _register(dynamodb, sku = 'CONS1', description = 'Consultoría en TI')
    _receive(dynamodb, [PurchaseLineIn(sku = 'CONS1', quantity = 10, unit_cost = 50.0,
                                       sale_price = 100.0, expiry_date = LATER)])
    billing_sales.issue_sale(dynamodb, OWNER, _note(
        [Payment(method = CASH, amount = 30), Payment(method = QR, amount = 170)]
    ), CASHIER)
    billing_sales.issue_sale(dynamodb, OWNER, _note(None, payment_method = CASH), CASHIER)

    totals = {row.payment_method: (row.count, row.total)
              for row in billing_cash.method_totals(billing_sales.list_sales(dynamodb,
                                                                            OWNER).items)}

    assert totals == {CASH: (2, 230), QR: (1, 170)}
