'''
    Tests for electronic invoicing: nominatividad, the card number, the XML
    against the SIN's own XSD, and the SOAP client.

    Split out of `test_billing.py` when that file passed a thousand lines. The
    seam is the natural one: everything here is about the document the tax
    office receives, while the other file is about the pharmacy's counter and
    its shelf.
'''
import sys
from pathlib import Path

import pytest

from schemas.billing import (
    SIN_PAYMENT_CODES,
    BillingError,
    BillingSettings,
    Buyer,
    InvoiceContext,
    InvoiceLine,
    PaymentMethod,
    PurchaseLineIn,
    SaleLineIn,
    SaleNoteIn
)
# `_dynamodb` is the shared fixture, used by pytest and not by name here: it
# is imported rather than copied so both files build the pharmacy's tables the
# same way. `_create_tables` is what it needs.
from tests.test_billing import ( # pylint: disable=unused-import
    CASHIER,
    LATER,
    OWNER,
    _create_tables,
    _dynamodb,
    _receive,
    _register,
    _sell
)
from services import billing, billing_sales
from services import billing_siat_client as siat_client
from services.billing_invoice_xml import build_invoice_xml, validate_against_schema
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    ServiceUnavailableError
)


# --- electronic invoicing: nominatividad -------------------------------------

def test_a_sale_without_a_buyer_is_refused_once_invoicing_electronically(dynamodb):
    '''
        Phase II names the buyer on every invoice, whatever the amount, so a
        pharmacy that is authorised cannot issue to the counter.
    '''
    billing.save_settings(dynamodb, OWNER, BillingSettings(
        trade_name = 'Farmacia Demo', buyer_required = True
    ))
    _register(dynamodb)

    with pytest.raises(InvalidInputError) as refused:
        _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 1)])

    assert refused.value.detail == BillingError.BUYER_REQUIRED.value


def test_the_document_is_what_the_norm_asks_for_not_the_name(dynamodb):
    '''
        The norm is explicit: nominatividad means the DOCUMENT NUMBER, not the
        name or business name. So a document alone is a valid sale and a name
        alone is not — demanding both would refuse a sale the norm accepts,
        over a field the buyer is not obliged to give.
    '''
    billing.save_settings(dynamodb, OWNER, BillingSettings(
        trade_name = 'Farmacia Demo', buyer_required = True
    ))
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER)])

    # The document with no name is enough.
    note = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 1)],
                 buyer = Buyer(document = '4567890'))
    assert note.buyer.document == '4567890'

    # The name with no document is not.
    with pytest.raises(InvalidInputError) as refused:
        _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 1)],
              buyer = Buyer(name = 'Ana Quispe'))
    assert refused.value.detail == BillingError.BUYER_REQUIRED.value


def test_a_pharmacy_not_yet_authorised_still_sells_to_the_counter(dynamodb):
    '''
        The default. A pharmacy issuing internal notes has to keep working
        until the authorisation exists.
    '''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER)])
    note = _sell(dynamodb, [SaleLineIn(sku = 'PARA500', quantity = 1)])

    assert note.number


def test_branch_and_point_of_sale_are_stored_for_the_cuf(dynamodb):
    '''
        They go INTO the CUF, so they are per-pharmacy settings and not
        service configuration: a CUF built with the wrong branch is a
        document the tax office rejects.
    '''
    billing.save_settings(dynamodb, OWNER, BillingSettings(
        trade_name = 'Farmacia Demo', branch = 2, point_of_sale = 7
    ))

    stored = billing.get_settings(dynamodb, OWNER)

    assert (stored.branch, stored.point_of_sale) == (2, 7)


def test_a_card_number_is_stored_masked_and_never_whole(dynamodb):
    '''
        The norm requires the middle digits zeroed. Masking at the boundary is
        what makes it true of the table and the printed note too: the full
        number never gets written anywhere.
    '''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER)])

    note = billing_sales.issue_sale(dynamodb, OWNER, SaleNoteIn(
        lines = [SaleLineIn(sku = 'PARA500', quantity = 1)],
        payment_method = PaymentMethod.TARJETA,
        card_number = '4797123456787896'
    ), CASHIER)

    assert note.card_number == '4797000000007896'
    stored = billing_sales.get_sale(dynamodb, OWNER, note.sale_id)
    assert stored.card_number == '4797000000007896'


def test_a_card_number_on_a_cash_sale_is_refused(dynamodb):
    '''
        The tax office reports it as an error, so it is refused here instead
        of being sent and bounced.
    '''
    _register(dynamodb)
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER)])

    with pytest.raises(InvalidInputError) as refused:
        billing_sales.issue_sale(dynamodb, OWNER, SaleNoteIn(
            lines = [SaleLineIn(sku = 'PARA500', quantity = 1)],
            payment_method = PaymentMethod.EFECTIVO,
            card_number = '4797123456787896'
        ), CASHIER)

    assert refused.value.detail == BillingError.CARD_WITHOUT_CARD_PAYMENT.value


def test_every_payment_method_has_a_code_for_the_tax_office(dynamodb): # pylint: disable=unused-argument
    '''
        Cash and card have their own; QR travels as OTROS, which is what the
        norm says to use when the method is not in its list.
    '''
    assert SIN_PAYMENT_CODES[PaymentMethod.EFECTIVO] == 1
    assert SIN_PAYMENT_CODES[PaymentMethod.TARJETA] == 2
    assert SIN_PAYMENT_CODES[PaymentMethod.QR] == 5
    assert set(SIN_PAYMENT_CODES) == set(PaymentMethod)


# --- electronic invoicing: the XML -------------------------------------------

XSD_PATH = str(Path(__file__).resolve().parents[3] / 'docs' / 'siat' /
               'facturaComputarizadaCompraVenta.xsd')


def _context(**overrides):
    '''
        An invoice context with plausible registration data.

        Args:
            **overrides: Fields to change.

        Returns:
            InvoiceContext: The context.
    '''
    return InvoiceContext(**{
        'issuer_document': '1234567',
        'trade_name': 'Farmacia Demo',
        'municipality': 'La Paz',
        'address': 'Av. Arce 2020',
        'phone': '2211234',
        'branch': 0,
        'point_of_sale': 0,
        'invoice_number': 1,
        'cuf': '1' * 54,
        'cufd': 'ABC123',
        'issued_at': '2026-09-29T10:15:30.000',
        'legend': 'Ley N 453: Tienes derecho a recibir informacion.',
        'currency_code': 1,
        'exchange_rate': 1.0,
        **overrides
    })


def _invoice_line(**overrides):
    '''
        A homologated invoice line.

        Args:
            **overrides: Fields to change.

        Returns:
            InvoiceLine: The line.
    '''
    return InvoiceLine(**{
        'sku': 'PARA500', 'description': 'Paracetamol 500 mg x 10',
        'quantity': 2.0, 'unit_price': 6.0, 'discount': 0.0, 'subtotal': 12.0,
        'sin_activity_code': '477310', 'sin_product_code': '99100',
        'sin_unit_code': 57, **overrides
    })


def _issued_sale(
    dynamodb,
    **note_overrides
):
    '''
        A sale issued over stocked product.

        Args:
            dynamodb: The resource.
            **note_overrides: Fields of the note.

        Returns:
            SaleNoteOut: The issued sale.
    '''
    # Tolerates being called twice in one test: the second sale of the same
    # product needs stock, not another catalogue entry.
    try:
        _register(dynamodb)
    except RegisterAlreadyExistsError:
        pass
    _receive(dynamodb, [PurchaseLineIn(sku = 'PARA500', quantity = 10, unit_cost = 3.0,
                                       sale_price = 6.0, expiry_date = LATER)])
    note = SaleNoteIn(**{
        'lines': [SaleLineIn(sku = 'PARA500', quantity = 2)],
        'payment_method': PaymentMethod.EFECTIVO,
        'buyer': Buyer(name = 'Ana Quispe', document = '4567890', document_type = 1),
        **note_overrides
    })
    return billing_sales.issue_sale(dynamodb, OWNER, note, CASHIER)


def test_the_invoice_xml_validates_against_the_siat_schema(dynamodb):
    '''
        The only test that means anything here: the document is checked against
        the XSD the tax office publishes, not against our idea of it. An
        element out of order is invalid even when every value is right, and
        that is exactly the mistake a hand-written builder makes.
    '''
    sale = _issued_sale(dynamodb)

    xml = build_invoice_xml(sale, _context(), [_invoice_line()])
    problems = validate_against_schema(xml, XSD_PATH)

    assert problems == [], problems


def test_a_card_sale_carries_the_masked_number_and_a_cash_sale_does_not(dynamodb):
    '''
        The norm reports a card number on a non-card sale as an error, so the
        element stays empty there. On a card sale it travels masked.
    '''
    card_sale = _issued_sale(dynamodb, payment_method = PaymentMethod.TARJETA,
                             card_number = '4797123456787896')
    xml = build_invoice_xml(card_sale, _context(), [_invoice_line()])

    assert '<numeroTarjeta>4797000000007896</numeroTarjeta>' in xml
    assert validate_against_schema(xml, XSD_PATH) == []

    # Absent, and it has to SAY so: an empty element is not a valid integer,
    # which is what the schema reported when it was written that way.
    cash_xml = build_invoice_xml(_issued_sale(dynamodb), _context(), [_invoice_line()])
    assert 'numeroTarjeta' in cash_xml and 'nil="true"' in cash_xml
    assert validate_against_schema(cash_xml, XSD_PATH) == []


def test_a_product_without_its_sin_codes_cannot_be_invoiced(dynamodb):
    '''
        Refused here rather than filled with a plausible number. An invoice
        with a made-up product code is rejected by the tax office AFTER the
        sale is already in the client's hands.
    '''
    sale = _issued_sale(dynamodb)

    with pytest.raises(InvalidInputError) as refused:
        build_invoice_xml(sale, _context(),
                          [_invoice_line(sin_product_code = None)])

    assert refused.value.detail == BillingError.PRODUCT_NOT_HOMOLOGATED.value


def test_amounts_carry_exactly_two_decimals(dynamodb):
    '''
        The schema types every amount as a decimal with two fraction digits.
        Sending a float's repr is how 0.1 + 0.2 reaches the tax office as
        0.30000000000000004 and the document is rejected.
    '''
    sale = _issued_sale(dynamodb)

    xml = build_invoice_xml(sale, _context(),
                            [_invoice_line(unit_price = 6.005, subtotal = 12.01)])

    assert '<precioUnitario>6.01</precioUnitario>' in xml
    assert validate_against_schema(xml, XSD_PATH) == []


# --- electronic invoicing: the SIAT client ------------------------------------
#
# What is testable without the authorization: which parameters each call sends
# and how the answer maps to a DTO. The calls themselves cannot be proven right
# from here, so `_invoke` is the seam that gets stubbed.

class _Answer:
    '''A zeep response: attributes read off the wire.''' # pylint: disable=too-few-public-methods

    def __init__(
        self,
        **fields
    ):
        self.__dict__.update(fields)


EMITTER = siat_client.Emitter(nit = '1234567', branch = 0, point_of_sale = 3)


def _captured(
    monkeypatch,
    answer
):
    '''
        Stubs the seam and records what it was called with.

        Args:
            monkeypatch: pytest's patcher.
            answer: What the stub returns.

        Returns:
            list: Filled with (service, operation, request) on each call.
    '''
    calls = []

    def _stub(
        service,
        operation,
        request
    ):
        calls.append((service, operation, request))
        return answer

    monkeypatch.setattr(siat_client, '_invoke', _stub)
    return calls


def test_the_cuis_request_carries_the_system_code_and_the_environment(monkeypatch):
    '''
        The system code and the environment are what identify us to the tax
        office. A code asked for in the pilot does not work in production, so
        both travel on every call and neither is hardcoded.
    '''
    calls = _captured(monkeypatch, _Answer(codigo = 'CUIS123',
                                          fechaVigencia = '2027-09-29'))

    answer = siat_client.request_cuis(EMITTER)

    service, operation, request = calls[0]
    assert (service, operation) == (siat_client.SERVICE_CODES, 'cuis')
    assert request['codigoSistema'] == siat_client.CODIGO_SISTEMA
    assert request['codigoAmbiente'] == siat_client.ENVIRONMENT
    assert request['codigoModalidad'] == siat_client.MODALITY
    assert (request['nit'], request['codigoSucursal']) == ('1234567', 0)
    assert answer.cuis == 'CUIS123'


def test_the_cufd_request_carries_the_cuis_and_returns_the_control_code(monkeypatch):
    '''
        The control code is what closes the CUF, so it has to come back — a
        CUFD without it cannot produce a valid invoice.
    '''
    calls = _captured(monkeypatch, _Answer(
        codigo = 'CUFD456', codigoControl = 'A19E23EF34124CD',
        direccion = 'Av. Arce 2020', fechaVigencia = '2026-09-29'
    ))

    answer = siat_client.request_cufd(EMITTER, 'CUIS123')

    assert calls[0][2]['cuis'] == 'CUIS123'
    assert answer.control_code == 'A19E23EF34124CD'


def test_a_point_of_sale_travels_only_when_there_is_one(monkeypatch):
    '''
        A pharmacy with no point of sale must not send a zero as if it had
        one: the tax office issues codes against what it is told.
    '''
    calls = _captured(monkeypatch, _Answer(codigo = 'C', fechaVigencia = 'D'))

    siat_client.request_cuis(siat_client.Emitter(nit = '1234567', branch = 0))
    assert 'codigoPuntoVenta' not in calls[0][2]

    siat_client.request_cuis(EMITTER)
    assert calls[1][2]['codigoPuntoVenta'] == 3


def test_the_receipt_keeps_the_tax_offices_own_messages(monkeypatch):
    '''
        The one place this backend returns prose instead of a code. They carry
        the SIN's own code and they are what a person reads to argue with
        them; rewording them would lose exactly that.
    '''
    _captured(monkeypatch, _Answer(
        transaccion = True, codigoRecepcion = 'REC789', codigoEstado = '901',
        mensajesList = [_Answer(codigo = 981, descripcion = 'Recepcion exitosa')]
    ))

    receipt = siat_client.send_invoice(EMITTER, {'cuis': 'C', 'cufd': 'D'}, 'H4sI')

    assert receipt.accepted is True
    assert receipt.reception_code == 'REC789'
    assert receipt.messages == ['981: Recepcion exitosa']


def test_a_refused_document_comes_back_as_not_accepted(monkeypatch):
    '''
        A refusal is an answer, not a failure: the caller has to read why.
    '''
    _captured(monkeypatch, _Answer(
        transaccion = False, codigoEstado = '904',
        mensajesList = [_Answer(codigo = 1004, descripcion = 'CUFD no vigente')]
    ))

    receipt = siat_client.cancel_invoice(EMITTER, {'cuis': 'C', 'cufd': 'D', 'cuf': 'F'}, 1)

    assert receipt.accepted is False
    assert receipt.messages == ['1004: CUFD no vigente']


def test_a_missing_wsdl_is_reported_and_not_downloaded(monkeypatch):
    '''
        The WSDL is read from disk on purpose: fetching it would be a network
        round trip on every cold start and would turn an outage of the SIAT
        into an outage of ours. Absent, it says so with a code.
    '''
    monkeypatch.setattr(siat_client, 'WSDL_DIR', '/tmp/no-hay-wsdl-aqui')
    monkeypatch.setattr(siat_client, '_clients', {})

    with pytest.raises(ServiceUnavailableError) as refused:
        siat_client.request_cuis(EMITTER)

    assert refused.value.detail == BillingError.SIAT_WSDL_MISSING.value


def test_the_dry_run_produces_a_valid_document():
    '''
        The demonstration tool is exercised here so it cannot rot silently: it
        is what shows a client the whole chain works while the SIAT pilot
        answers 503, and a broken demo is worse than no demo.

        The repository root is put on the path by the test itself rather than
        by an environment variable: a test that only passes with the right
        PYTHONPATH is a test that passes on one machine.
    '''
    root = str(Path(__file__).resolve().parents[3])
    if root not in sys.path:
        sys.path.insert(0, root)
    # Imported here and not at module level because the path has to exist
    # first, which is also why Pylint cannot resolve it statically: `tools`
    # becomes importable only after the insert above.
    # pylint: disable=import-outside-toplevel, import-error
    from tools.billing.dry_run_invoice import main

    assert main(['--lines', '3']) == 0
