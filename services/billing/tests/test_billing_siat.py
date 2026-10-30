'''
    Tests for the codes and catalogues a shop needs from the SIN.

    What they protect: a CUIS or CUFD is asked for only when missing or
    expired, a refusal is never stored as a code, every catalogue is stored
    for its own shop, and each shape the SIN returns is read into the same
    row. The tax office itself is stubbed at the client's functions; the
    pilot is exercised by hand, not by the suite.
'''
import asyncio
from datetime import timedelta
from unittest.mock import patch

import pytest

from controllers import billing_siat as controllers
from models.billing import SETTINGS_TABLE
from schemas.billing import BillingError, BillingSettings, CufdResponse, CuisResponse
from schemas.billing_siat import (
    CatalogEntry,
    CatalogOut,
    CatalogsSyncResponse,
    SiatCatalog,
    SiatCodesOut
)
from services import billing, billing_siat_codes, utils
from services import billing_siat_client as siat_client
from services.exceptions import InvalidInputError, RegisterNotFoundError
from tests.test_billing import OTHER_OWNER, OWNER, _dynamodb # pylint: disable=unused-import

LONG_AGO = '2020-01-01T00:00:00-04:00'
FAR_AHEAD = '2099-01-01T00:00:00-04:00'


class _Answer:
    '''A zeep response: attributes read off the wire.''' # pylint: disable=too-few-public-methods

    def __init__(
        self,
        **fields
    ):
        self.__dict__.update(fields)


@pytest.fixture(name = 'tax_office')
def _tax_office(monkeypatch: pytest.MonkeyPatch) -> dict:
    '''
        The SIN, standing in: every CUIS and CUFD it hands out is new and
        valid far ahead, and every catalogue brings two rows.

        Returns:
            dict: How many times each code was asked for.
    '''
    asked = {'cuis': 0, 'cufd': 0, 'catalogs': []}

    def _cuis(emitter): # pylint: disable=unused-argument
        asked['cuis'] += 1
        return CuisResponse(cuis = f'CUIS{asked["cuis"]}', valid_until = FAR_AHEAD)

    def _cufd(
        emitter, # pylint: disable=unused-argument
        cuis
    ):
        asked['cufd'] += 1
        return CufdResponse(cufd = f'CUFD{asked["cufd"]}-{cuis}', control_code = 'CC',
                            address = 'Calle 1', valid_until = FAR_AHEAD)

    def _sync(
        emitter, # pylint: disable=unused-argument
        cuis, # pylint: disable=unused-argument
        catalog
    ):
        asked['catalogs'].append(catalog)
        return [CatalogEntry(code = '1', description = 'Uno'),
                CatalogEntry(code = '2', description = 'Dos', activity_code = '477300')]

    monkeypatch.setattr(siat_client, 'request_cuis', _cuis)
    monkeypatch.setattr(siat_client, 'request_cufd', _cufd)
    monkeypatch.setattr(siat_client, 'sync_catalog', _sync)
    return asked


def _age_codes(
    resource,
    **valid_until
):
    '''
        Moves the stored validity of the demo shop's codes.

        Args:
            resource: The DynamoDB resource.
            **valid_until: cuis_valid_until and/or cufd_valid_until.
    '''
    table = resource.Table(SETTINGS_TABLE)
    key = {'owner': OWNER, 'setting_key': 'siat#codes#0#0'}
    item = table.get_item(Key = key)['Item']
    table.put_item(Item = {**item, **valid_until})


def test_the_codes_are_asked_for_once_and_then_read_from_the_store(
    dynamodb,
    tax_office
):
    '''A sale must not wait on the tax office for a code it already has.'''
    first = billing_siat_codes.current_codes(dynamodb, OWNER)
    second = billing_siat_codes.current_codes(dynamodb, OWNER)

    assert isinstance(first, SiatCodesOut)
    assert (first.cuis, first.cufd) == ('CUIS1', 'CUFD1-CUIS1')
    assert second == first
    assert (tax_office['cuis'], tax_office['cufd']) == (1, 1)


def test_an_expired_cufd_is_renewed_and_the_cuis_is_kept(
    dynamodb,
    tax_office
):
    '''The CUFD lasts a day and the CUIS a year: only the one that expired goes.'''
    billing_siat_codes.current_codes(dynamodb, OWNER)
    _age_codes(dynamodb, cufd_valid_until = LONG_AGO)

    renewed = billing_siat_codes.current_codes(dynamodb, OWNER)

    assert (renewed.cuis, renewed.cufd) == ('CUIS1', 'CUFD2-CUIS1')
    assert (tax_office['cuis'], tax_office['cufd']) == (1, 2)


def test_an_expired_cuis_brings_a_new_cufd_with_it(
    dynamodb,
    tax_office
):
    '''A CUFD is asked for with a CUIS; a new CUIS cannot keep the old CUFD.'''
    billing_siat_codes.current_codes(dynamodb, OWNER)
    _age_codes(dynamodb, cuis_valid_until = LONG_AGO)

    renewed = billing_siat_codes.current_codes(dynamodb, OWNER)

    assert (renewed.cuis, renewed.cufd) == ('CUIS2', 'CUFD2-CUIS2')
    assert (tax_office['cuis'], tax_office['cufd']) == (2, 2)


def test_a_shop_without_a_nit_cannot_ask_the_tax_office(
    dynamodb,
    tax_office
):
    '''Nothing is asked of the SIN without the NIT that identifies who asks.'''
    billing.save_settings(dynamodb, OWNER, BillingSettings(trade_name = 'Sin NIT'))

    with pytest.raises(InvalidInputError) as refused:
        billing_siat_codes.current_codes(dynamodb, OWNER)

    assert refused.value.detail == BillingError.SIAT_ISSUER_INCOMPLETE.value
    assert tax_office['cuis'] == 0


def test_every_catalogue_is_stored_for_its_own_shop(
    dynamodb,
    tax_office
):
    '''Activities and products depend on the NIT: one shop never reads another's.'''
    synced = billing_siat_codes.sync_catalogs(dynamodb, OWNER)

    assert [summary.catalog for summary in synced.catalogs] == list(SiatCatalog)
    assert tax_office['catalogs'] == list(SiatCatalog)
    legends = billing_siat_codes.get_catalog(dynamodb, OWNER, SiatCatalog.LEGENDS)
    assert [entry.code for entry in legends.entries] == ['1', '2']
    assert legends.entries[1].activity_code == '477300'

    with pytest.raises(RegisterNotFoundError) as missing:
        billing_siat_codes.get_catalog(dynamodb, OTHER_OWNER, SiatCatalog.LEGENDS)
    assert missing.value.detail == BillingError.CATALOG_NOT_SYNCED.value


# --- the client: what each call sends and how each shape is read ---------------

def _stub_invoke(
    monkeypatch: pytest.MonkeyPatch,
    answer: _Answer
) -> list:
    '''
        Stubs the client's single seam and records what it was called with.

        Returns:
            list: (service, operation, request) on each call.
    '''
    calls: list = []

    def _stub(
        service,
        operation,
        request
    ):
        calls.append((service, operation, request))
        return answer

    monkeypatch.setattr(siat_client, 'invoke', _stub)
    return calls


EMITTER = siat_client.Emitter(nit = '1234567', branch = 0, point_of_sale = 0)


def test_a_refused_cuis_is_an_error_and_never_a_code(monkeypatch):
    '''
        A refusal comes back with empty codes; stored, it would poison the day.
        Even a tolerated message is a refusal when it brings no code.
    '''
    _stub_invoke(monkeypatch, _Answer(transaccion = False, codigo = None,
                                      mensajesList = [_Answer(codigo = 980,
                                                              descripcion = 'NIT inexistente')]))

    with pytest.raises(InvalidInputError) as refused:
        siat_client.request_cuis(EMITTER)

    assert refused.value.detail == BillingError.SIAT_REFUSED.value


def test_a_cuis_already_in_force_is_the_code_and_not_a_refusal(monkeypatch):
    '''
        Asked again, the SIN answers `transaccion` false with message 980 and
        the CUIS in force (pilot, 26-oct). Refusing it would leave a shop
        unable to recover its own code.
    '''
    _stub_invoke(monkeypatch, _Answer(
        transaccion = False, codigo = 'E461F6E8', fechaVigencia = '2027-10-26',
        mensajesList = [_Answer(codigo = siat_client.CUIS_IN_FORCE,
                                descripcion = 'EXISTE UN CUIS VIGENTE')]))

    assert siat_client.request_cuis(EMITTER).cuis == 'E461F6E8'


def test_a_catalogue_is_asked_for_with_the_cuis_and_without_the_modality(monkeypatch):
    '''The catalogues are the same whichever way the shop issues.'''
    calls = _stub_invoke(monkeypatch, _Answer(transaccion = True, listaCodigos = []))

    siat_client.sync_catalog(EMITTER, 'CUIS9', SiatCatalog.PAYMENT_METHODS)

    service, operation, request = calls[0]
    assert (service, operation) == (siat_client.SERVICE_SYNC,
                                    'sincronizarParametricaTipoMetodoPago')
    assert request['cuis'] == 'CUIS9'
    assert 'codigoModalidad' not in request


@pytest.mark.parametrize(('answer', 'expected'), [
    (_Answer(transaccion = True, listaCodigos = [
        _Answer(codigoClasificador = 1, descripcion = 'FACTURA MAL EMITIDA')]),
     CatalogEntry(code = '1', description = 'FACTURA MAL EMITIDA')),
    (_Answer(transaccion = True, listaActividades = [
        _Answer(codigoCaeb = '477300', descripcion = 'VENTA DE PRODUCTOS FARMACEUTICOS',
                tipoActividad = 'P')]),
     CatalogEntry(code = '477300', description = 'VENTA DE PRODUCTOS FARMACEUTICOS')),
    (_Answer(transaccion = True, listaCodigos = [
        _Answer(codigoActividad = '477300', codigoProducto = 35270,
                descripcionProducto = 'MEDICAMENTOS', nandina = [])]),
     CatalogEntry(code = '35270', description = 'MEDICAMENTOS', activity_code = '477300')),
    (_Answer(transaccion = True, listaLeyendas = [
        _Answer(codigoActividad = '477300', descripcionLeyenda = 'Ley N° 453: ...')]),
     CatalogEntry(code = '', description = 'Ley N° 453: ...', activity_code = '477300')),
    (_Answer(transaccion = True, listaActividadesDocumentoSector = [
        _Answer(codigoActividad = '477300', codigoDocumentoSector = 1,
                tipoDocumentoSector = 'FAC_CV')]),
     CatalogEntry(code = '1', description = 'FAC_CV', activity_code = '477300')),
])
def test_each_shape_the_sin_returns_is_read_into_the_same_row(
    monkeypatch,
    answer,
    expected
):
    '''Five shapes, one row: code, description and the activity it hangs from.'''
    _stub_invoke(monkeypatch, answer)

    assert siat_client.sync_catalog(EMITTER, 'C', SiatCatalog.LEGENDS) == [expected]


def test_every_catalogue_has_its_sin_operation():
    '''A catalogue without its operation would fail only the day it is synced.'''
    assert set(siat_client._SYNC_OPERATIONS) == set(SiatCatalog) # pylint: disable=protected-access


# --- controllers ------------------------------------------------------------------

def test_every_siat_endpoint_returns_its_model_and_the_sync_is_audited(
    dynamodb,
    tax_office # pylint: disable=unused-argument
):
    '''Each controller returns its model assembled; rewriting the catalogues is audited.'''
    audited: list = []

    def _record(
        result, # pylint: disable=unused-argument
        kwargs, # pylint: disable=unused-argument
        spec
    ):
        audited.append((spec.entity_name, spec.action))
        return {}

    async def _no_send(
        audit_data, # pylint: disable=unused-argument
        authorization # pylint: disable=unused-argument
    ):
        return None

    def _call(
        controller,
        **arguments
    ):
        return asyncio.run(controller(dynamodb_resource = dynamodb, owner = OWNER,
                                      request = None, current_user = OWNER, **arguments))

    with patch.object(utils, '_audit_payload', _record), \
            patch.object(utils, 'send_audit_event', _no_send):
        assert isinstance(_call(controllers.current_codes_controller), SiatCodesOut)
        assert isinstance(_call(controllers.sync_catalogs_controller), CatalogsSyncResponse)
        assert isinstance(_call(controllers.get_catalog_controller,
                                catalog = SiatCatalog.CURRENCIES), CatalogOut)

    assert audited == [('SiatCatalog', 'SYNC')]


def test_the_cufd_in_force_at_a_past_moment_is_kept_after_it_is_replaced(
    dynamodb,
    tax_office # pylint: disable=unused-argument
):
    '''
        A manual contingency invoice is transcribed with the CUFD that was in
        force when the contingency began, though a new one came since.
    '''
    billing_siat_codes.current_codes(dynamodb, OWNER)
    an_hour_ago = (utils.get_current_time_gmt() - timedelta(hours = 1)).isoformat()
    _age_codes(dynamodb, cufd_obtained_at = (utils.get_current_time_gmt()
                                             - timedelta(hours = 3)).isoformat())

    billing_siat_codes.current_codes(dynamodb, OWNER, force_cufd = True)

    assert billing_siat_codes.codes_at(dynamodb, OWNER, an_hour_ago).cufd == 'CUFD1-CUIS1'
    now = utils.get_current_time_gmt().isoformat()
    assert billing_siat_codes.codes_at(dynamodb, OWNER, now).cufd == 'CUFD2-CUIS1'


def test_no_cufd_is_kept_for_a_moment_before_the_days_kept(
    dynamodb,
    tax_office # pylint: disable=unused-argument
):
    '''
        Older than the days the history keeps, or before any CUFD: there is
        nothing to transcribe with.
    '''
    billing_siat_codes.current_codes(dynamodb, OWNER)
    month_ago = utils.get_current_time_gmt() - timedelta(days = 30)
    _age_codes(dynamodb, cufd_obtained_at = month_ago.isoformat())

    billing_siat_codes.current_codes(dynamodb, OWNER, force_cufd = True)

    later = (month_ago + timedelta(hours = 1)).isoformat()
    assert billing_siat_codes.codes_at(dynamodb, OWNER, later) is None
    assert billing_siat_codes.codes_at(dynamodb, OWNER, LONG_AGO) is None
