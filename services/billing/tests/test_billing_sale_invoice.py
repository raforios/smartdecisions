'''
    Tests for a sale becoming an invoice.

    What they protect: with invoicing on, every sale goes to the SIN with a
    document that validates against its XSD; a sale that cannot be invoiced is
    refused before any stock moves; and one the SIN refuses or cannot receive
    gives its units back and is not issued. The tax office is stubbed at the
    client's seam; the pilot is exercised by hand, not by the suite.
'''
import asyncio
import gzip
import hashlib
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from controllers import billing as controllers
from models.billing import OWNER_KEY, SETTINGS_TABLE, SETTING_SORT_KEY
from schemas.billing import (
    BillingError,
    BillingSettings,
    Buyer,
    CufInput,
    ProductIn,
    ProductPatch,
    PurchaseLineIn,
    SaleAllocation,
    SaleLineIn,
    SaleLineOut,
    SaleNoteIn,
    SaleNoteOut,
    SaleStatus,
    SiatReceipt
)
from schemas.billing_siat import (
    CatalogEntry,
    CatalogOut,
    InvoiceState,
    SaleCancellation,
    SiatCatalog,
    SiatCodesOut
)
from services import billing, billing_customers, billing_invoicing, billing_sales, utils
from services import billing_siat_client as siat_client
from services.billing_invoice_xml import validate_against_schema
from services.billing_siat import build_cuf, check_digit, cuf_chain
from services.exceptions import InvalidInputError
from tests.test_billing import ( # pylint: disable=unused-import
    CASHIER,
    LATER,
    OWNER,
    _dynamodb,
    _receive
)
from tests.test_billing_invoicing import XSD_PATH

ACTIVITY = '620000'
CODES = SiatCodesOut(branch = 0, point_of_sale = 0, cuis = 'CUIS1',
                     cuis_valid_until = '2099-01-01T00:00:00-04:00', cufd = 'CUFD1',
                     control_code = 'A19E23EF34124CD', cufd_valid_until = '2099-01-01',
                     address = 'Calle 1')
# A slice of the SIN's PAYMENT_METHODS, spelled as the pilot sent it on 27-oct.
PAYMENT_CATALOGUE = [CatalogEntry(code = code, description = description) for code, description in (
    ('1', 'EFECTIVO'), ('2', 'TARJETA'), ('5', 'OTROS'), ('7', 'TRANSFERENCIA BANCARIA'),
    ('10', 'EFECTIVO-TARJETA'), ('13', 'EFECTIVO – TRANSFERENCIA BANCARIA'),
    ('27', 'GIFT-CARD'), ('29', 'EFECTIVO - TARJETA - VALE'), ('35', 'EFECTIVO – GIFT CARD')
)]
BUYER = Buyer(name = 'Ana Quispe', document = '4567890', document_type = 1)


@pytest.fixture(name = 'sent')
def _sent(monkeypatch: pytest.MonkeyPatch) -> list:
    '''
        The SIN, standing in: it accepts every invoice and records what came.

        Returns:
            list: Each `InvoiceSubmission` received.
    '''
    received = []

    def _send(
        emitter, # pylint: disable=unused-argument
        submission
    ):
        received.append(submission)
        return SiatReceipt(accepted = True, reception_code = 'REC1', state = '908')

    monkeypatch.setattr(billing_invoicing, 'current_codes', lambda *_: CODES)
    monkeypatch.setattr(siat_client, 'send_invoice', _send)
    return received


def _invoicing_shop(
    dynamodb,
    homologated = True
):
    '''
        A shop that invoices, with one stocked product and its legends synced.

        Args:
            dynamodb: The resource.
            homologated (bool): Whether the product carries its SIN codes.
    '''
    billing.save_settings(dynamodb, OWNER, BillingSettings(
        trade_name = 'Consultora Demo', document = '4746720010', municipality = 'La Paz',
        invoicing_enabled = True
    ))
    codes = {'sin_activity_code': ACTIVITY, 'sin_product_code': '83131',
             'sin_unit_code': 58} if homologated else {}
    billing.create_product(dynamodb, OWNER, ProductIn(
        sku = 'CONS1', description = 'Consultoría en TI', laboratory = 'Propio', **codes
    ))
    _receive(dynamodb, [PurchaseLineIn(sku = 'CONS1', quantity = 10, unit_cost = 50.0,
                                       sale_price = 100.0, expiry_date = LATER)])
    billing.write_item(dynamodb, SETTINGS_TABLE, {
        OWNER_KEY: OWNER, SETTING_SORT_KEY: f'siat#catalog#{SiatCatalog.LEGENDS.name}',
        **CatalogOut(catalog = SiatCatalog.LEGENDS, synced_at = '2026-10-26', entries = [
            CatalogEntry(code = '', description = 'Ley 453: leyenda de TI.',
                         activity_code = ACTIVITY),
            CatalogEntry(code = '', description = 'Leyenda de otra actividad.',
                         activity_code = '477300')
        ]).model_dump(mode = 'json')
    })
    billing.write_item(dynamodb, SETTINGS_TABLE, {
        OWNER_KEY: OWNER, SETTING_SORT_KEY: f'siat#catalog#{SiatCatalog.PAYMENT_METHODS.name}',
        **CatalogOut(catalog = SiatCatalog.PAYMENT_METHODS, synced_at = '2026-10-27',
                     entries = PAYMENT_CATALOGUE).model_dump(mode = 'json')
    })


def _sell(
    dynamodb,
    buyer = BUYER
):
    '''
        Sells two units of the consulting product.

        Args:
            dynamodb: The resource.
            buyer (Buyer): Who buys.

        Returns:
            SaleNoteOut: The issued sale.
    '''
    return billing_sales.issue_sale(dynamodb, OWNER, SaleNoteIn(
        lines = [SaleLineIn(sku = 'CONS1', quantity = 2)], buyer = buyer
    ), CASHIER)


def _stock(dynamodb) -> float:
    '''
        Units of the consulting product still on the shelf.
    '''
    return sum(lot['quantity_remaining'] for lot in
               billing_sales._available_lots_by_sku(dynamodb, OWNER)['CONS1']) # pylint: disable=protected-access


def test_an_invoicing_sale_sends_a_document_the_xsd_accepts(
    dynamodb,
    sent
):
    '''
        The document is checked against the XSD the tax office publishes, and
        the CUF it carries is closed by the day's control code.
    '''
    _invoicing_shop(dynamodb)

    note = _sell(dynamodb)

    xml = gzip.decompress(sent[0].archive).decode('utf-8')
    assert validate_against_schema(xml, XSD_PATH) == []
    assert note.invoice.number == 1
    assert note.invoice.cuf.endswith(CODES.control_code)
    assert note.invoice.cuf in xml
    assert note.invoice.legend == 'Ley 453: leyenda de TI.'
    assert note.invoice.qr_url.endswith(
        f'?nit=4746720010&cuf={note.invoice.cuf}&numero=1&t=1')
    assert (sent[0].cuis, sent[0].cufd) == ('CUIS1', 'CUFD1')
    assert billing_sales.get_sale(dynamodb, OWNER, note.sale_id).invoice == note.invoice


def test_invoice_numbers_follow_one_another(
    dynamodb,
    sent
):
    '''
        The SIN's sequence is the shop's own and does not repeat.
    '''
    _invoicing_shop(dynamodb)

    assert [_sell(dynamodb).invoice.number for _ in range(2)] == [1, 2]
    assert len(sent) == 2


def test_a_shop_that_does_not_invoice_never_calls_the_sin(
    dynamodb,
    sent
):
    '''
        The default: internal notes, as before the switch existed.
    '''
    _invoicing_shop(dynamodb)
    settings = billing.get_settings(dynamodb, OWNER)
    billing.save_settings(dynamodb, OWNER, BillingSettings(**{
        **settings.model_dump(include = set(BillingSettings.model_fields)),
        'invoicing_enabled': False
    }))

    note = _sell(dynamodb, buyer = Buyer())

    assert note.invoice is None
    assert not sent


def test_a_product_without_its_sin_codes_is_refused_before_stock_moves(
    dynamodb,
    sent
):
    '''
        Found out at the counter, not at the tax office after the units left.
    '''
    _invoicing_shop(dynamodb, homologated = False)

    with pytest.raises(InvalidInputError) as refused:
        _sell(dynamodb)

    assert refused.value.detail == BillingError.PRODUCT_NOT_HOMOLOGATED.value
    assert _stock(dynamodb) == 10
    assert not sent


def test_an_invoice_needs_the_buyers_document_type(
    dynamodb,
    sent
):
    '''
        The XSD has no empty `codigoTipoDocumentoIdentidad`.
    '''
    _invoicing_shop(dynamodb)

    with pytest.raises(InvalidInputError) as refused:
        _sell(dynamodb, buyer = Buyer(document = '4567890'))

    assert refused.value.detail == BillingError.BUYER_REQUIRED.value
    assert not sent


def test_a_refused_invoice_gives_the_units_back_and_issues_nothing(
    dynamodb,
    monkeypatch
):
    '''
        A sale whose invoice the SIN refuses is not a sale: no note, and the
        shelf as it was.
    '''
    _invoicing_shop(dynamodb)
    monkeypatch.setattr(billing_invoicing, 'current_codes', lambda *_: CODES)
    monkeypatch.setattr(siat_client, 'send_invoice', lambda *_: SiatReceipt(
        accepted = False, state = '902', messages = ['1037: NIT invalido']
    ))

    with pytest.raises(InvalidInputError) as refused:
        _sell(dynamodb)

    assert refused.value.detail == BillingError.SIAT_REFUSED.value
    assert _stock(dynamodb) == 10
    assert billing_sales.list_sales(dynamodb, OWNER).total == 0


def test_no_legend_for_the_activity_is_refused(
    dynamodb,
    sent
):
    '''
        A legend of another activity is not one the law allows on this invoice.
    '''
    _invoicing_shop(dynamodb)
    billing.update_product(dynamodb, OWNER, 'CONS1', ProductPatch(sin_activity_code = '999999'))

    with pytest.raises(InvalidInputError) as refused:
        _sell(dynamodb)

    assert refused.value.detail == BillingError.LEGEND_NOT_FOUND.value
    assert not sent


def test_a_line_sold_at_two_prices_becomes_two_details():
    '''
        The SIN checks quantity times price against each subtotal; an averaged
        price would not add up. The discount is spent from the first detail.
    '''
    line = SaleLineOut(
        sku = 'CONS1', description = 'Consultoría en TI', quantity = 3, discount = 5,
        allocations = [
            SaleAllocation(lot_id = 'L1', quantity = 2, unit_price = 10, unit_cost = 5,
                           amount = 20),
            SaleAllocation(lot_id = 'L2', quantity = 1, unit_price = 12, unit_cost = 5,
                           amount = 12)
        ],
        subtotal = 32, total = 27, cost = 15
    )

    details = billing_invoicing._invoice_lines(line, {}) # pylint: disable=protected-access

    assert [(d.quantity, d.unit_price, d.discount, d.subtotal) for d in details] == [
        (2, 10, 5, 15), (1, 12, 0, 12)
    ]
    assert sum(d.subtotal for d in details) == line.total


def test_the_archive_travels_as_bytes_with_its_sha256(monkeypatch):
    '''
        zeep encodes `base64Binary` itself; the hash is of the archive sent.
    '''
    calls = []

    def _stub(
        service, # pylint: disable=unused-argument
        operation, # pylint: disable=unused-argument
        request
    ):
        calls.append(request)

    monkeypatch.setattr(siat_client, 'invoke', _stub)
    archive = gzip.compress(b'<factura/>')

    siat_client.send_invoice(siat_client.Emitter(nit = '1', branch = 0),
                             siat_client.InvoiceSubmission(cuis = 'C', cufd = 'D',
                                                           archive = archive,
                                                           sent_at = '2026-10-26T10:00:00.000'))

    assert calls[0]['archivo'] == archive
    assert calls[0]['hashArchivo'] == hashlib.sha256(archive).hexdigest()


def test_the_cuf_of_the_manuals_worked_example():
    '''
        The example the SIAT publishes, step by step, in `docs/siat/SIAT.md`.
    '''
    data = CufInput(nit = '123456789', issued_at = datetime(2019, 1, 13, 16, 37, 21, 231000),
                    invoice_number = 1, modality = 1)

    assert check_digit(cuf_chain(data)) == '1'
    assert build_cuf(data, 'A19E23EF34124CD') == \
        '8727F63A15F8976591FDDE5B387C5D015A29E06A1A19E23EF34124CD'


def test_the_cuf_the_pilot_expected():
    '''
        The pilot refused this invoice on 26-oct and said which CUF it wanted:
        the sum modulo 11 is 10, which writes a "1", where multiplying by ten
        first wrote a "0". The manual's example does not tell them apart.
    '''
    chain = '00047467200102026102623354435500002110100000000010000'

    assert check_digit(chain) == '1'
    assert format(int(chain + check_digit(chain)), 'X') + '408E5F67CB4BF74' == \
        '144C8A4ACC011DFD5EB552C47B7F0D8192F408606A1408E5F67CB4BF74'


@pytest.fixture(name = 'cancelled_at_sin')
def _cancelled_at_sin(monkeypatch: pytest.MonkeyPatch) -> list:
    '''
        The SIN's cancellation, standing in: it accepts and records each one.

        Returns:
            list: Each `InvoiceCancellation` received.
    '''
    received = []

    def _cancel(
        emitter, # pylint: disable=unused-argument
        cancellation
    ):
        received.append(cancellation)
        return SiatReceipt(accepted = True, state = '905')

    monkeypatch.setattr(siat_client, 'cancel_invoice', _cancel)
    return received


def test_an_invoice_is_cancelled_at_the_sin_with_its_reason(
    dynamodb,
    sent,
    cancelled_at_sin
):
    '''
        The units come back only once the SIN cancelled the invoice.
    '''
    _invoicing_shop(dynamodb)
    note = _sell(dynamodb)

    cancelled = billing_sales.cancel_sale(dynamodb, OWNER, note.sale_id, CASHIER, 1)

    assert (cancelled_at_sin[0].cuf, cancelled_at_sin[0].reason_code) == (note.invoice.cuf, 1)
    assert cancelled.invoice.state == InvoiceState.CANCELLED
    assert cancelled.invoice.cancellation_reason == 1
    assert _stock(dynamodb) == 10
    assert len(sent) == 1


def test_an_invoice_is_not_cancelled_without_a_reason(
    dynamodb,
    sent,
    cancelled_at_sin
):
    '''
        The SIN has no cancellation without a reason from its catalogue.
    '''
    _invoicing_shop(dynamodb)
    note = _sell(dynamodb)

    with pytest.raises(InvalidInputError) as refused:
        billing_sales.cancel_sale(dynamodb, OWNER, note.sale_id, CASHIER)

    assert refused.value.detail == BillingError.CANCELLATION_REASON_REQUIRED.value
    assert not cancelled_at_sin
    assert _stock(dynamodb) == 8
    assert len(sent) == 1


def test_a_cancellation_the_sin_refuses_leaves_the_note_as_it_was(
    dynamodb,
    sent,
    monkeypatch
):
    '''
        An invoice still in force at the SIN keeps its note issued and its
        units sold.
    '''
    _invoicing_shop(dynamodb)
    note = _sell(dynamodb)
    monkeypatch.setattr(siat_client, 'cancel_invoice', lambda *_: SiatReceipt(
        accepted = False, messages = ['1019: Factura fuera de plazo']
    ))

    with pytest.raises(InvalidInputError) as refused:
        billing_sales.cancel_sale(dynamodb, OWNER, note.sale_id, CASHIER, 1)

    assert refused.value.detail == BillingError.SIAT_REFUSED.value
    stored = billing_sales.get_sale(dynamodb, OWNER, note.sale_id)
    assert stored.status == SaleStatus.ISSUED
    assert stored.invoice.state == InvoiceState.ACCEPTED
    assert _stock(dynamodb) == 8
    assert len(sent) == 1


def test_the_cancel_controller_returns_the_note(
    dynamodb,
    sent
):
    '''
        The endpoint's path and optional body reach the service as one DTO;
        an internal note needs no reason.
    '''
    _invoicing_shop(dynamodb)
    settings = billing.get_settings(dynamodb, OWNER)
    billing.save_settings(dynamodb, OWNER, BillingSettings(**{
        **settings.model_dump(include = set(BillingSettings.model_fields)),
        'invoicing_enabled': False
    }))
    note = _sell(dynamodb, buyer = Buyer())

    with patch.object(utils, '_audit_payload', lambda *_: {}), \
            patch.object(utils, 'send_audit_event', AsyncMock()):
        cancelled = asyncio.run(controllers.cancel_sale_controller(
            dynamodb_resource = dynamodb, owner = OWNER,
            cancellation = SaleCancellation(sale_id = note.sale_id),
            request = None, current_user = CASHIER
        ))

    assert isinstance(cancelled, SaleNoteOut)
    assert cancelled.status == SaleStatus.CANCELLED
    assert not sent


def test_the_qr_carries_the_link_the_invoice_stored(
    dynamodb,
    sent
):
    '''
        Decoded, the QR is exactly the SIN's link of that invoice.
    '''
    _invoicing_shop(dynamodb)
    note = _sell(dynamodb)

    qr = billing_sales.sale_qr(dynamodb, OWNER, note.sale_id)

    assert qr.svg.startswith('<svg viewBox=')
    assert qr.svg == billing_invoicing.qr_svg(note.invoice.qr_url)
    assert qr.svg != billing_invoicing.qr_svg(note.invoice.qr_url.replace('numero=1', 'numero=2'))
    assert len(sent) == 1


def test_an_internal_note_has_no_qr(
    dynamodb,
    sent
):
    '''
        Only an invoice is checked at the SIN.
    '''
    _invoicing_shop(dynamodb)
    settings = billing.get_settings(dynamodb, OWNER)
    billing.save_settings(dynamodb, OWNER, BillingSettings(**{
        **settings.model_dump(include = set(BillingSettings.model_fields)),
        'invoicing_enabled': False
    }))
    note = _sell(dynamodb, buyer = Buyer())

    with pytest.raises(InvalidInputError) as refused:
        billing_sales.sale_qr(dynamodb, OWNER, note.sale_id)

    assert refused.value.detail == BillingError.SALE_NOT_INVOICED.value
    assert not sent


def test_an_invoice_remembers_its_buyer_and_an_internal_note_does_not(
    dynamodb,
    sent
):
    '''
        The customers are those the shop invoiced.
    '''
    _invoicing_shop(dynamodb)
    _sell(dynamodb, buyer = Buyer(name = 'Ana Quispe', document = '4567890',
                                  document_type = 1, email = 'ana@correo.bo'))
    settings = billing.get_settings(dynamodb, OWNER)
    billing.save_settings(dynamodb, OWNER, BillingSettings(**{
        **settings.model_dump(include = set(BillingSettings.model_fields)),
        'invoicing_enabled': False
    }))
    _sell(dynamodb, buyer = Buyer(document = '9999999'))

    customers = billing_customers.list_customers(dynamodb, OWNER).items
    assert [(c.document, c.email) for c in customers] == [('4567890', 'ana@correo.bo')]
    assert len(sent) == 1


@pytest.mark.parametrize(('issued_at', 'last_day'), [
    ('2026-10-27T09:36:00.761', '2026-11-09'),
    ('2026-12-31T23:59:59.999', '2027-01-09'),
    ('2027-01-01T00:00:00.000', '2027-02-09')
])
def test_an_invoice_can_be_cancelled_until_the_ninth_of_the_next_month(
    issued_at,
    last_day
):
    '''
        The norm's deadline, across a year's end.
    '''
    assert billing_invoicing.cancellation_deadline(issued_at).isoformat() == last_day


def test_past_the_deadline_the_sin_is_not_even_asked(
    dynamodb,
    sent,
    cancelled_at_sin,
    monkeypatch
):
    '''
        After the ninth of the following month the invoice stays valid and
        the note issued: a return then needs a credit note.
    '''
    _invoicing_shop(dynamodb)
    note = _sell(dynamodb)
    monkeypatch.setattr(billing_sales, 'cancellation_deadline',
                        lambda _: datetime(2020, 1, 9).date())

    with pytest.raises(InvalidInputError) as refused:
        billing_sales.cancel_sale(dynamodb, OWNER, note.sale_id, CASHIER, 1)

    assert refused.value.detail == BillingError.CANCELLATION_DEADLINE_PASSED.value
    assert not cancelled_at_sin
    assert billing_sales.get_sale(dynamodb, OWNER, note.sale_id).status == SaleStatus.ISSUED
    assert len(sent) == 1
