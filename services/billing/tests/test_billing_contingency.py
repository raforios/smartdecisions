'''
    Tests for contingency: issuing while the SIN cannot be reached, and the
    recovery that catches up.

    What they protect: an invoice that cannot reach the SIN is issued offline
    and the till keeps selling; the offline CUF carries emission type 2; a cut
    sending the SIN did register is cancelled so only its offline twin stays;
    the recovery follows the SIN's order — new CUFD, event, packages — and
    marks each invoice with what the SIN said; and the scheduled run waits the
    parameter's minutes before trying again. The tax office is stubbed at the
    package module's functions.
'''
import asyncio
import gzip
import io
import tarfile
from unittest.mock import AsyncMock, patch

import pytest

from controllers import billing_siat as controllers
from models.billing import OWNER_KEY, SETTINGS_TABLE, SETTING_SORT_KEY
from schemas.billing import BillingError, Buyer, SiatReceipt
from schemas.billing_siat import (
    CatalogEntry,
    CatalogOut,
    ContingencyIn,
    ContingencyStatus,
    InvoiceState,
    PackageReceipt,
    RecoveryOut,
    SiatCatalog,
    SignificantEvent
)
from services import billing, billing_contingency, billing_invoicing, billing_sales, utils
from services import billing_siat_client as siat_client
from services import billing_siat_packages as packages
from services.exceptions import InvalidInputError, ServiceUnavailableError
from tests.test_billing import CASHIER, OWNER, _dynamodb # pylint: disable=unused-import
from tests.test_billing_sale_invoice import ( # pylint: disable=unused-import
    CODES,
    _invoicing_shop,
    _sell,
    _sent,
    _stock
)

NEW_CODES = CODES.model_copy(update = {'cufd': 'CUFD2', 'control_code': 'B2'})


def _unreachable(*_):
    '''The SIN, away.'''
    raise ServiceUnavailableError(detail = BillingError.SIAT_UNREACHABLE.value)


@pytest.fixture(name = 'offline')
def _offline(
    dynamodb,
    monkeypatch: pytest.MonkeyPatch
):
    '''
        A shop that invoices, with the SIN unreachable from the first sale.

        Returns:
            ServiceResource: The resource.
    '''
    _invoicing_shop(dynamodb)
    billing.write_item(dynamodb, SETTINGS_TABLE, {
        OWNER_KEY: OWNER, SETTING_SORT_KEY: f'siat#catalog#{SiatCatalog.SIGNIFICANT_EVENTS.name}',
        **CatalogOut(catalog = SiatCatalog.SIGNIFICANT_EVENTS, synced_at = '2026-10-27',
                     entries = [CatalogEntry(code = '2', description = 'INACCESIBILIDAD'),
                                CatalogEntry(code = '4', description = 'VENTA SIN INTERNET')]
                     ).model_dump(mode = 'json')
    })
    monkeypatch.setattr(billing_invoicing, 'current_codes', lambda *_, **__: CODES)
    monkeypatch.setattr(billing_contingency, 'current_codes', lambda *_, **__: NEW_CODES)
    monkeypatch.setattr(siat_client, 'send_invoice', _unreachable)
    return dynamodb


@pytest.fixture(name = 'tax_office')
def _tax_office(monkeypatch: pytest.MonkeyPatch) -> dict:
    '''
        The SIN back again: it answers, registers the event, receives every
        package and validates it.

        Returns:
            dict: What it was asked.
    '''
    asked = {'events': [], 'packages': [], 'states': [], 'cancelled': []}
    monkeypatch.setattr(packages, 'verify_communication', lambda: True)

    def _event(
        emitter, # pylint: disable=unused-argument
        event
    ):
        asked['events'].append(event)
        return 777

    def _package(
        emitter, # pylint: disable=unused-argument
        package
    ):
        asked['packages'].append(package)
        return PackageReceipt(accepted = True, reception_code = 'PKG1', state = '901')

    def _state(
        emitter, # pylint: disable=unused-argument
        codes, # pylint: disable=unused-argument
        cuf
    ):
        asked['states'].append(cuf)
        return '908'

    def _cancel(
        emitter, # pylint: disable=unused-argument
        cancellation
    ):
        asked['cancelled'].append(cancellation.cuf)
        return SiatReceipt(accepted = True, state = '905')

    monkeypatch.setattr(packages, 'register_event', _event)
    monkeypatch.setattr(packages, 'send_package', _package)
    monkeypatch.setattr(packages, 'validate_package', lambda *_: PackageReceipt(
        accepted = True, reception_code = 'PKG1', state = '908'))
    monkeypatch.setattr(packages, 'invoice_state', _state)
    monkeypatch.setattr(siat_client, 'cancel_invoice', _cancel)
    return asked


def _contingency(dynamodb):
    '''The stored contingency of the shop's point of sale, or None.'''
    return billing_contingency.active_contingency(
        dynamodb, OWNER, billing_contingency.emitter_for(dynamodb, OWNER))


def test_an_invoice_that_cannot_reach_the_sin_is_issued_offline(offline):
    '''
        The till keeps selling: the sale is issued, its stock leaves, and the
        point of sale enters contingency with the cut sending in doubt.
    '''
    note = _sell(offline)

    assert note.invoice.state == InvoiceState.OFFLINE
    assert note.invoice.emission_type == 2
    assert _stock(offline) == 8
    record = _contingency(offline)
    assert record['event'] == SignificantEvent.SIN_UNREACHABLE
    assert record['cufd'] == CODES.cufd
    assert len(record['uncertain_cufs']) == 1
    assert record['uncertain_cufs'][0] != note.invoice.cuf


def test_the_offline_cuf_carries_emission_type_two(offline):
    '''
        The emission type is a digit of the CUF: an offline invoice with the
        online digit is one the SIN rejects in its package.
    '''
    note = _sell(offline)

    numeric = int(note.invoice.cuf[:-len(CODES.control_code)], 16)
    chain = str(numeric).zfill(54)[:53]
    # nit 13 + date 17 + branch 4 + modality 1, then the emission type.
    assert chain[35] == '2'


def test_in_contingency_the_sin_is_not_tried(
    offline,
    monkeypatch
):
    '''
        Once offline, the next sale does not wait on the SIN again.
    '''
    _sell(offline)
    tried = []
    monkeypatch.setattr(siat_client, 'send_invoice', lambda *_: tried.append(1))

    second = _sell(offline)

    assert second.invoice.state == InvoiceState.OFFLINE
    assert not tried


def test_an_offline_nit_goes_with_exception_code_one(offline):
    '''
        The SIN could not validate a NIT invoiced offline; the norm asks to
        say so with the exception code.
    '''
    note = _sell(offline, buyer = Buyer(name = 'Empresa', document = '1020304050',
                                        document_type = 5))

    stored = offline.Table(billing_sales.SALES_TABLE).get_item(
        Key = {OWNER_KEY: OWNER, 'sale_id': note.sale_id})['Item']
    assert '<codigoExcepcion>1</codigoExcepcion>' in stored['invoice_xml']


def test_without_a_cufd_and_without_the_sin_the_last_cufd_is_stretched(
    offline,
    monkeypatch
):
    '''
        The CUFD is due and the SIN cannot give one: the last one serves, as
        the norm allows, and the sale is issued offline.
    '''
    monkeypatch.setattr(billing_invoicing, 'current_codes', _unreachable)
    monkeypatch.setattr(billing_invoicing, 'last_codes', lambda *_: CODES)

    note = _sell(offline)

    assert note.invoice.state == InvoiceState.OFFLINE
    assert _contingency(offline)['uncertain_cufs'] == []


def test_without_any_usable_cufd_the_sale_is_refused(
    offline,
    monkeypatch
):
    '''
        Past the 72 hours there is nothing to issue with.
    '''
    monkeypatch.setattr(billing_invoicing, 'current_codes', _unreachable)
    monkeypatch.setattr(billing_invoicing, 'last_codes', lambda *_: None)

    with pytest.raises(ServiceUnavailableError):
        _sell(offline)

    assert _stock(offline) == 10


def test_while_the_sin_does_not_answer_the_shop_stays_offline(
    offline,
    monkeypatch
):
    '''
        A recovery that finds the SIN away only notes when it looked.
    '''
    _sell(offline)
    monkeypatch.setattr(packages, 'verify_communication', lambda: False)

    outcome = billing_contingency.recover(offline, OWNER)

    assert outcome.recovered is False
    assert _contingency(offline) is not None


def test_the_recovery_follows_the_sins_order(
    offline,
    tax_office
):
    '''
        New CUFD, the event with the CUFD the invoices carried, the doubtful
        sending cancelled, every offline invoice in one package, and each
        invoice marked validated.
    '''
    first, second = _sell(offline), _sell(offline)
    record = _contingency(offline)

    outcome = billing_contingency.recover(offline, OWNER)

    event = tax_office['events'][0]
    assert (event.cufd, event.cufd_event, event.event_code) == ('CUFD2', CODES.cufd, 2)
    assert event.started_at == record['started_at']
    assert event.description == 'INACCESIBILIDAD'
    assert tax_office['cancelled'] == record['uncertain_cufs']
    package = tax_office['packages'][0]
    assert package.event_reception_code == 777
    assert [name for name, _ in package.invoices] == [f'{first.invoice.number}.xml',
                                                      f'{second.invoice.number}.xml']
    assert (outcome.recovered, outcome.invoices_sent, outcome.uncertain_cancelled) == \
        (True, 2, 1)
    for sale in (first, second):
        stored = billing_sales.get_sale(offline, OWNER, sale.sale_id)
        assert stored.invoice.state == InvoiceState.ACCEPTED
        assert stored.invoice.package_reception_code == 'PKG1'
    assert _contingency(offline) is None


def test_the_sins_observations_reach_their_own_invoice(
    offline,
    tax_office,
    monkeypatch
):
    '''
        The SIN numbers the files of a package from zero; that is how its
        observation finds the invoice.
    '''
    first, second = _sell(offline), _sell(offline)
    monkeypatch.setattr(packages, 'validate_package', lambda *_: PackageReceipt(
        accepted = True, reception_code = 'PKG1', state = '904',
        observed = {1: ['1037: NIT INVALIDO']}))

    outcome = billing_contingency.recover(offline, OWNER)

    assert outcome.invoices_observed == 1
    assert billing_sales.get_sale(offline, OWNER, first.sale_id).invoice.state == \
        InvoiceState.ACCEPTED
    observed = billing_sales.get_sale(offline, OWNER, second.sale_id).invoice
    assert (observed.state, observed.observations) == \
        (InvoiceState.OBSERVED, ['1037: NIT INVALIDO'])
    assert len(tax_office['packages']) == 1


def test_a_warning_in_a_validated_package_keeps_the_invoice_valid(
    offline,
    tax_office,
    monkeypatch
):
    '''
        The pilot validated a package (908) with a warning for an offline NIT
        it could not find (27-oct): the invoice is valid and the warning kept.
    '''
    note = _sell(offline)
    monkeypatch.setattr(packages, 'validate_package', lambda *_: PackageReceipt(
        accepted = True, reception_code = 'PKG1', state = '908',
        observed = {0: ['2005: ADVERTENCIA: EL NIT DEL CLIENTE NO ES VALIDO']}))

    billing_contingency.recover(offline, OWNER)

    invoice = billing_sales.get_sale(offline, OWNER, note.sale_id).invoice
    assert invoice.state == InvoiceState.ACCEPTED
    assert invoice.observations == ['2005: ADVERTENCIA: EL NIT DEL CLIENTE NO ES VALIDO']
    assert len(tax_office['packages']) == 1


def test_a_package_still_pending_is_settled_on_a_later_run(
    offline,
    tax_office,
    monkeypatch
):
    '''
        901 is not an answer yet: the package is kept and asked about again.
    '''
    note = _sell(offline)
    monkeypatch.setattr(packages, 'validate_package', lambda *_: PackageReceipt(
        accepted = True, reception_code = 'PKG1', state = '901'))
    billing_contingency.recover(offline, OWNER)
    assert billing_sales.get_sale(offline, OWNER, note.sale_id).invoice.state == \
        InvoiceState.OFFLINE

    monkeypatch.setattr(packages, 'validate_package', lambda *_: PackageReceipt(
        accepted = True, reception_code = 'PKG1', state = '908'))
    monkeypatch.setattr(billing_contingency, 'RETRY_MINUTES', 0)
    done = billing_contingency.run_scheduled(offline)

    assert any('validated' in line for line in done)
    assert billing_sales.get_sale(offline, OWNER, note.sale_id).invoice.state == \
        InvoiceState.ACCEPTED
    assert len(tax_office['packages']) == 1


def test_the_scheduled_run_waits_the_parameters_minutes(
    offline,
    tax_office
):
    '''
        A contingency checked a moment ago is left alone: the norm asks to
        stay offline a prudent while before trying again.
    '''
    _sell(offline)

    done = billing_contingency.run_scheduled(offline)

    assert not done
    assert not tax_office['events']
    assert billing_contingency.RETRY_MINUTES > 0


def test_an_event_registered_is_not_registered_again(
    offline,
    tax_office,
    monkeypatch
):
    '''
        A recovery cut after the event reuses its code the next time.
    '''
    _sell(offline)
    monkeypatch.setattr(packages, 'send_package', _unreachable)
    with pytest.raises(ServiceUnavailableError):
        billing_contingency.recover(offline, OWNER)

    monkeypatch.setattr(packages, 'send_package', lambda *_: PackageReceipt(
        accepted = True, reception_code = 'PKG1', state = '901'))
    billing_contingency.recover(offline, OWNER)

    assert len(tax_office['events']) == 1


def test_an_offline_invoice_cannot_be_cancelled_before_its_package(offline):
    '''
        There is nothing at the SIN to cancel yet.
    '''
    note = _sell(offline)

    with pytest.raises(InvalidInputError) as refused:
        billing_sales.cancel_sale(offline, OWNER, note.sale_id, CASHIER, 1)

    assert refused.value.detail == BillingError.INVOICE_NOT_YET_AT_SIN.value


def test_a_ci_with_letters_is_refused_before_stock_moves(offline):
    '''
        The norm: a CI or a NIT the SIN receives is a number.
    '''
    with pytest.raises(InvalidInputError) as refused:
        _sell(offline, buyer = Buyer(document = '45A7890', document_type = 1))

    assert refused.value.detail == BillingError.BUYER_DOCUMENT_NOT_NUMERIC.value
    assert _stock(offline) == 10


def test_a_package_is_a_tar_of_the_xmls_gzipped():
    '''
        The format the pilot accepted on 27-oct.
    '''
    archive = packages.pack_invoices([('1.xml', '<a/>'), ('2.xml', '<b/>')])

    with tarfile.open(fileobj = io.BytesIO(gzip.decompress(archive))) as tar:
        names = tar.getnames()
        first = tar.extractfile('1.xml').read()

    assert names == ['1.xml', '2.xml']
    assert first == b'<a/>'


def test_the_lambda_runs_the_contingency_task_and_not_mangum(monkeypatch):
    '''
        The scheduled event has no request: it must never reach Mangum.
    '''
    # pylint: disable=import-outside-toplevel
    import main
    calls = []
    monkeypatch.setattr(billing_contingency, 'run_scheduled',
                        lambda resource: calls.append(resource) or ['row'])
    monkeypatch.setattr(main, '_asgi_handler', lambda *_: pytest.fail('reached Mangum'))

    answer = main.handler({'task': 'siat_contingency'}, None)

    assert answer == {'touched': ['row']}
    assert len(calls) == 1


def test_the_contingency_controllers_return_their_models(
    offline,
    tax_office,
    monkeypatch
):
    '''
        Each endpoint returns its model assembled; entering and recovering
        are audited, reading is not.
    '''
    monkeypatch.setattr(billing_contingency, 'current_codes', lambda *_, **__: CODES)
    audited = []
    common = {'dynamodb_resource': offline, 'owner': OWNER, 'request': None,
              'current_user': CASHIER}
    with patch.object(utils, '_audit_payload',
                      lambda result, kwargs, spec: audited.append(spec.action) or {}), \
            patch.object(utils, 'send_audit_event', AsyncMock()):
        idle = asyncio.run(controllers.contingency_status_controller(**common))
        started = asyncio.run(controllers.start_contingency_controller(
            contingency = ContingencyIn(event = SignificantEvent.SALE_WITHOUT_INTERNET), **common))
        recovered = asyncio.run(controllers.recover_controller(**common))

    assert isinstance(idle, ContingencyStatus) and idle.offline is False
    assert started.offline and started.contingency.event == SignificantEvent.SALE_WITHOUT_INTERNET
    assert isinstance(recovered, RecoveryOut) and recovered.recovered
    assert audited == ['START', 'RECOVER']
    assert tax_office['events'][0].event_code == 4
