'''
    Tests for manual contingency invoices.

    What they protect: a contingency is opened with the CUFD in force when it
    began, not the one in force now; a paper invoice is transcribed with its
    own number, moment, price and CAFC, takes its units off the shelf and no
    till; a number outside the CAFC, repeated, or a moment outside the event
    is refused; the sending registers the event with the old CUFD and sends
    the packages with the CAFC; and the automatic contingency never takes a
    paper invoice. The tax office is stubbed at the package module.
'''
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from controllers import billing_manual as controllers
from models.billing import OWNER_KEY, SALES_TABLE, SALE_SORT_KEY, SETTINGS_TABLE, SETTING_SORT_KEY
from schemas.billing import Buyer, SaleNoteOut
from schemas.billing_manual import (
    CafcIn,
    ManualContingencyIn,
    ManualError,
    ManualInvoiceIn,
    ManualLineIn,
    ManualTranscription
)
from schemas.billing_siat import CatalogEntry, CatalogOut, InvoiceState, SiatCatalog
from services import billing, billing_contingency, billing_manual, utils
from services import billing_siat_packages as packages
from services.exceptions import InvalidInputError, RegisterNotFoundError
from tests.test_billing import CASHIER, OWNER, _dynamodb # pylint: disable=unused-import
from tests.test_billing_contingency import NEW_CODES, _tax_office # pylint: disable=unused-import
from tests.test_billing_sale_invoice import ( # pylint: disable=unused-import
    CODES,
    _invoicing_shop,
    _sent,
    _stock
)

CAFC = 'CAFC-PILOTO-1'
BUYER = Buyer(name = 'Ana Quispe', document = '4567890', document_type = 1)
STARTED = datetime.fromisoformat('2026-10-27T10:00:00-04:00')
ENDED = datetime.fromisoformat('2026-10-27T14:00:00-04:00')
ON_PAPER = datetime.fromisoformat('2026-10-27T11:30:00-04:00')


@pytest.fixture(name = 'paper_shop')
def _paper_shop(
    dynamodb,
    monkeypatch: pytest.MonkeyPatch
):
    '''
        A shop that invoices, holds a CAFC from 1 to 50, and whose CUFD was
        replaced after its contingency began.

        Returns:
            ServiceResource: The resource.
    '''
    _invoicing_shop(dynamodb)
    billing.write_item(dynamodb, SETTINGS_TABLE, {
        OWNER_KEY: OWNER, SETTING_SORT_KEY: 'siat#codes#0#0',
        **CODES.model_dump(exclude = {'branch', 'point_of_sale'}),
        'cufd': 'CUFD-NOW', 'cufd_obtained_at': '2026-10-28T08:00:00-04:00',
        'cufd_history': [{'cufd': 'CUFD-OLD', 'control_code': CODES.control_code,
                          'cufd_valid_until': '2026-10-28T08:00:00-04:00',
                          'address': 'Calle 1',
                          'cufd_obtained_at': '2026-10-27T08:00:00-04:00'}]
    })
    billing.write_item(dynamodb, SETTINGS_TABLE, {
        OWNER_KEY: OWNER, SETTING_SORT_KEY: f'siat#catalog#{SiatCatalog.SIGNIFICANT_EVENTS.name}',
        **CatalogOut(catalog = SiatCatalog.SIGNIFICANT_EVENTS, synced_at = '2026-10-27',
                     entries = [CatalogEntry(code = '7', description = 'CORTE DE ENERGIA')]
                     ).model_dump(mode = 'json')
    })
    monkeypatch.setattr(billing_contingency, 'current_codes', lambda *_, **__: NEW_CODES)
    billing_manual.register_cafc(dynamodb, OWNER, CafcIn(cafc = CAFC, first_number = 1,
                                                         last_number = 50))
    return dynamodb


def _open(dynamodb):
    '''A power cut from 10:00 to 14:00, with the CAFC.'''
    return billing_manual.open_manual_contingency(dynamodb, OWNER, ManualContingencyIn(
        cafc = CAFC, event = 7, started_at = STARTED, ended_at = ENDED), CASHIER)


def _paper(
    number = 7,
    issued_at = ON_PAPER
):
    '''Two units of the consulting product at Bs 120, as the paper says.'''
    return ManualInvoiceIn(number = number, issued_at = issued_at, buyer = BUYER,
                           lines = [ManualLineIn(sku = 'CONS1', quantity = 2, unit_price = 120)])


def _stored_sale(
    dynamodb,
    sale_id
):
    '''The sale as the table holds it.'''
    return dynamodb.Table(SALES_TABLE).get_item(
        Key = {OWNER_KEY: OWNER, SALE_SORT_KEY: sale_id})['Item']


def test_a_contingency_carries_the_cufd_in_force_when_it_began(paper_shop):
    '''
        The CUFD in force now is not the one the paper invoices belong to.
    '''
    contingency = _open(paper_shop)

    assert contingency.cufd == 'CUFD-OLD'
    assert contingency.started_at == '2026-10-27T10:00:00.000'


def test_with_no_cufd_kept_for_its_start_a_contingency_is_refused(paper_shop):
    '''
        Before any CUFD kept, there is nothing to transcribe with.
    '''
    with pytest.raises(InvalidInputError) as refused:
        billing_manual.open_manual_contingency(paper_shop, OWNER, ManualContingencyIn(
            cafc = CAFC, event = 7, started_at = datetime.fromisoformat('2026-10-20T10:00-04:00'),
            ended_at = ENDED), CASHIER)

    assert refused.value.detail == ManualError.CUFD_NOT_KEPT.value


def test_a_contingency_needs_a_registered_cafc(paper_shop):
    '''
        The CAFC is the SIN's authorization: an unknown one is refused.
    '''
    with pytest.raises(RegisterNotFoundError):
        billing_manual.open_manual_contingency(paper_shop, OWNER, ManualContingencyIn(
            cafc = 'OTRO', event = 7, started_at = STARTED, ended_at = ENDED), CASHIER)


def test_a_paper_invoice_is_transcribed_as_the_paper_says(
    paper_shop,
    sent
):
    '''
        Its number, moment, price and CAFC, the old CUFD, offline, its units
        off the shelf, no till, and nothing sent to the SIN yet.
    '''
    contingency = _open(paper_shop)

    sale = billing_manual.transcribe_invoice(paper_shop, OWNER, contingency.contingency_id,
                                             _paper(), CASHIER)

    invoice = sale.invoice
    assert (invoice.number, invoice.cafc, invoice.cufd) == (7, CAFC, 'CUFD-OLD')
    assert (invoice.state, invoice.emission_type) == (InvoiceState.OFFLINE, 2)
    assert invoice.issued_at == '2026-10-27T11:30:00.000'
    assert sale.total == 240
    assert _stock(paper_shop) == 8
    stored = _stored_sale(paper_shop, sale.sale_id)
    assert stored.get('cash_session_id') is None
    assert f'<cafc>{CAFC}</cafc>' in stored['invoice_xml']
    assert '<numeroFactura>7</numeroFactura>' in stored['invoice_xml']
    assert not sent


@pytest.mark.parametrize(('paper', 'code'), [
    (_paper(number = 51), ManualError.NUMBER_OUTSIDE_CAFC),
    (_paper(issued_at = datetime.fromisoformat('2026-10-27T15:00:00-04:00')),
     ManualError.ISSUED_OUTSIDE_EVENT)
])
def test_a_paper_invoice_outside_its_cafc_or_its_event_is_refused(
    paper_shop,
    paper,
    code
):
    '''
        The SIN refuses both (1047, 1041): they are refused here first.
    '''
    contingency = _open(paper_shop)

    with pytest.raises(InvalidInputError) as refused:
        billing_manual.transcribe_invoice(paper_shop, OWNER, contingency.contingency_id,
                                          paper, CASHIER)

    assert refused.value.detail == code.value
    assert _stock(paper_shop) == 10


def test_a_paper_invoice_is_transcribed_once(paper_shop):
    '''
        The same number under the same CAFC is the same invoice.
    '''
    contingency = _open(paper_shop)
    billing_manual.transcribe_invoice(paper_shop, OWNER, contingency.contingency_id,
                                      _paper(), CASHIER)

    with pytest.raises(InvalidInputError) as refused:
        billing_manual.transcribe_invoice(paper_shop, OWNER, contingency.contingency_id,
                                          _paper(), CASHIER)

    assert refused.value.detail == ManualError.NUMBER_ALREADY_TRANSCRIBED.value
    assert billing_manual.list_cafcs(paper_shop, OWNER).items[0].used_numbers == [7]


def test_the_sending_registers_the_event_with_the_old_cufd_and_the_cafc(
    paper_shop,
    tax_office
):
    '''
        The SIN's order for paper invoices: event with the CUFD of the
        contingency, packages with the CAFC, in number order.
    '''
    contingency = _open(paper_shop)
    for number in (9, 7):
        billing_manual.transcribe_invoice(paper_shop, OWNER, contingency.contingency_id,
                                          _paper(number = number), CASHIER)

    outcome = billing_manual.send_manual_contingency(paper_shop, OWNER,
                                                     contingency.contingency_id)

    event = tax_office['events'][0]
    assert (event.cufd_event, event.cufd, event.event_code) == ('CUFD-OLD', NEW_CODES.cufd, 7)
    assert (event.started_at, event.ended_at) == ('2026-10-27T10:00:00.000',
                                                  '2026-10-27T14:00:00.000')
    package = tax_office['packages'][0]
    assert package.cafc == CAFC
    assert [name for name, _ in package.invoices] == ['7.xml', '9.xml']
    assert (outcome.invoices_sent, outcome.event_reception_code) == (2, 777)
    listed = billing_manual.list_manual_contingencies(paper_shop, OWNER).items[0]
    assert listed.status.value == 'SENT'
    states = {_stored_sale(paper_shop, sale_id)['invoice']['state'] for sale_id in listed.sale_ids}
    assert states == {InvoiceState.ACCEPTED.value}

    with pytest.raises(InvalidInputError) as refused:
        billing_manual.send_manual_contingency(paper_shop, OWNER, contingency.contingency_id)
    assert refused.value.detail == ManualError.MANUAL_CONTINGENCY_SENT.value


def test_an_empty_contingency_has_nothing_to_send(
    paper_shop,
    tax_office # pylint: disable=unused-argument
):
    '''
        No event is registered for no invoices.
    '''
    contingency = _open(paper_shop)

    with pytest.raises(InvalidInputError) as refused:
        billing_manual.send_manual_contingency(paper_shop, OWNER, contingency.contingency_id)

    assert refused.value.detail == ManualError.NOTHING_TO_SEND.value


def test_the_automatic_contingency_never_takes_a_paper_invoice(paper_shop):
    '''
        Same CUFD or not, a transcribed invoice goes with its own CAFC.
    '''
    contingency = _open(paper_shop)
    billing_manual.transcribe_invoice(paper_shop, OWNER, contingency.contingency_id,
                                      _paper(), CASHIER)

    offline = billing_contingency._offline_sales( # pylint: disable=protected-access
        paper_shop, OWNER, {'started_at': '2026-10-27T00:00:00.000', 'cufd': 'CUFD-OLD'})

    assert not offline


def test_the_transcription_controller_returns_the_sale(paper_shop):
    '''
        The endpoint's path and body reach the service as one DTO.
    '''
    contingency = _open(paper_shop)

    with patch.object(utils, '_audit_payload', lambda *_: {}), \
            patch.object(utils, 'send_audit_event', AsyncMock()):
        sale = asyncio.run(controllers.transcribe_invoice_controller(
            dynamodb_resource = paper_shop, owner = OWNER,
            transcription = ManualTranscription(contingency_id = contingency.contingency_id,
                                                invoice = _paper()),
            request = None, current_user = CASHIER
        ))

    assert isinstance(sale, SaleNoteOut)


def test_the_package_request_carries_the_cafc_only_when_it_has_one(monkeypatch):
    '''
        `recepcionPaqueteFactura` takes the CAFC of paper invoices; an
        automatic contingency's package goes without it.
    '''
    sent_requests = []
    monkeypatch.setattr(packages.siat_client, 'invoke',
                        lambda service, operation, request: sent_requests.append(request))
    monkeypatch.setattr(packages, '_package_receipt', lambda answer: None)
    emitter = packages.siat_client.Emitter(nit = '4746720010', branch = 0)
    for cafc in (CAFC, None):
        packages.send_package(emitter, packages.PackageSubmission(
            cuis = 'CUIS1', cufd = 'CUFD1', event_reception_code = 777,
            invoices = [('7.xml', '<factura/>')], sent_at = '2026-10-28T10:00:00.000',
            cafc = cafc))

    assert sent_requests[0]['cafc'] == CAFC
    assert 'cafc' not in sent_requests[1]
