'''
    The SIAT web services: the half of electronic invoicing that is not ours.

    Everything in `billing_siat.py` is arithmetic we can verify alone. This
    module is the opposite: it asks the tax office for codes only it can issue
    —the CUIS, the daily CUFD— and hands it the invoice. Nothing here can be
    proven right without the authorization, so what IS tested is the part that
    can be: which parameters go in each call, and how the answer maps to a DTO.

    Two decisions that shape the module:

    **The WSDL is read from disk, never fetched.** `zeep` downloads it when it
    builds a client, and in Lambda that is a network round trip on every cold
    start — and an outage of a service we do not control turning into an outage
    of ours. The WSDL files live in the service's `wsdl/` folder, so they
    travel inside the Lambda package and are versioned with the code: the
    contract cannot change under us without a commit.

    **Every call goes through one seam.** `invoke` is the only place that
    talks to `zeep`, which is what makes the parameter assembly testable
    without a WSDL and what stops nine operations from each inventing their
    own error handling.

    References, all in `docs/siat/SIAT.md`: Solicitud CUIS, Solicitud CUFD,
    Verifica NIT, Recepción de factura, Anulación.
'''
import hashlib
import os
from dataclasses import dataclass
from typing import Any, Final

import requests
from zeep import Client, Settings
from zeep.exceptions import Error as ZeepError
from zeep.transports import Transport

from schemas.billing import (
    EMISSION_ONLINE,
    INVOICE_WITH_TAX_CREDIT,
    SECTOR_DOCUMENT_PURCHASE_SALE,
    BillingError,
    CuisResponse,
    CufdResponse,
    SiatReceipt
)
from schemas.billing_siat import CatalogEntry, SiatCatalog
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError, ServiceUnavailableError
from services.logger_config import custom_logger as logger

# The delegation token and the system code are credentials: they live in the
# environment and never in the source. `SIAT_ENVIRONMENT` is the SIN's
# `codigoAmbiente` — the pilot and production are different numbers, and
# sending the wrong one issues codes that do not work in the other.
ENV_VARS = load_and_validate_env_vars({
    'SIAT_CODIGO_SISTEMA': str,
    'SIAT_TOKEN': str,
    'SIAT_ENVIRONMENT': int,
    'SIAT_WSDL_DIR': str,
    'SIAT_TIMEOUT_SECONDS': int,
})

CODIGO_SISTEMA: Final[str] = ENV_VARS['SIAT_CODIGO_SISTEMA']
ENVIRONMENT: Final[int] = ENV_VARS['SIAT_ENVIRONMENT']
WSDL_DIR: Final[str] = ENV_VARS['SIAT_WSDL_DIR']
TIMEOUT: Final[int] = ENV_VARS['SIAT_TIMEOUT_SECONDS']

# The modality this product issues under: computerized online. It is not a
# setting because it describes the SYSTEM and not the pharmacy — changing it
# would mean a different authorization.
MODALITY: Final[int] = 2

# One WSDL per service, as the SIN publishes them.
SERVICE_CODES = 'codigos'
SERVICE_INVOICE = 'facturacion'
SERVICE_SYNC = 'sincronizacion'

# Asked for a CUIS while one is in force, the SIN answers `transaccion` false
# with this message AND the CUIS in force (checked on the pilot, 26-oct): it is
# the code, not a refusal.
CUIS_IN_FORCE: Final[int] = 980

# Authorization scheme of the `apikey` header, fixed by the SIAT protocol.
TOKEN_SCHEME: Final[str] = 'TokenApi'

_clients: dict[str, Client] = {}


@dataclass(frozen = True)
class Emitter:
    '''
        Who is issuing, as every SIAT call needs it.

        Grouped because these four travel together in every request and
        passing them loose is how a CUFD of one branch ends up asked for
        another's.
    '''
    nit: str
    branch: int
    point_of_sale: int | None = None


def wsdl_path(service: str) -> str:
    '''
        Where the WSDL of one service lives.

        Args:
            service (str): Service name, as `SERVICE_*` spells it.

        Returns:
            str: Absolute path to the .wsdl file.
    '''
    # Absolute, because each WSDL imports its other half from the file next to
    # it, and zeep resolves that relative import only against an absolute path.
    return os.path.abspath(os.path.join(WSDL_DIR, f'{service}.wsdl'))


def _client(service: str) -> Client:
    '''
        The zeep client of one service, built once per process.

        Cached because building it parses the WSDL, which is slow enough to
        matter on a warm Lambda serving invoices one after another.

        Args:
            service (str): Service name, as `SERVICE_*` spells it.

        Returns:
            Client: The zeep client.

        Raises:
            ServiceUnavailableError: The WSDL is not on disk.
    '''
    if service in _clients:
        return _clients[service]

    path = wsdl_path(service)
    if not os.path.isfile(path):
        error_msg = f'WSDL for the SIAT "{service}" service is not at {path}.'
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = BillingError.SIAT_WSDL_MISSING.value)

    session = requests.Session()
    # The delegation token authorises every call. It is a header and not a
    # parameter, so it never appears in the SOAP body a log might capture.
    # The SIAT rejects the bare token: it expects the `TokenApi` scheme.
    session.headers.update({'apikey': f'{TOKEN_SCHEME} {ENV_VARS["SIAT_TOKEN"]}'})
    _clients[service] = Client(
        wsdl = path,
        transport = Transport(session = session, timeout = TIMEOUT),
        settings = Settings(strict = False, xml_huge_tree = True)
    )
    return _clients[service]


def invoke(
    service: str,
    operation: str,
    request: dict[str, Any] | None
) -> Any:
    '''
        The single seam that talks to the SIAT.

        Every operation goes through here, which is what makes the parameter
        assembly testable without a WSDL and what keeps one error path instead
        of nine.

        Args:
            service (str): Service name, as `SERVICE_*` spells it.
            operation (str): Operation name, as the WSDL spells it.
            request (dict[str, Any] | None): The request object's fields;
                None for an operation that takes none, like
                `verificarComunicacion`.

        Returns:
            Any: The response as zeep returns it.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable or refused.
    '''
    try:
        call = getattr(_client(service).service, operation)
        answer = call() if request is None else call(request)
    except (ZeepError, requests.exceptions.RequestException) as error:
        error_msg = f'SIAT operation {operation} failed: {error}'
        logger.error(error_msg)
        raise ServiceUnavailableError(
            detail = BillingError.SIAT_UNREACHABLE.value
        ) from error

    message = f'SIAT operation {operation} answered.'
    logger.info(message)
    return answer


def base_request(emitter: Emitter) -> dict[str, Any]:
    '''
        The fields every SIAT request carries.

        Args:
            emitter (Emitter): Who is issuing.

        Returns:
            dict[str, Any]: The common parameters.
    '''
    request: dict[str, Any] = {
        'codigoAmbiente': ENVIRONMENT,
        'codigoSistema': CODIGO_SISTEMA,
        'nit': emitter.nit,
        'codigoModalidad': MODALITY,
        'codigoSucursal': emitter.branch
    }
    if emitter.point_of_sale is not None:
        request['codigoPuntoVenta'] = emitter.point_of_sale
    return request


def _accepted(
    operation: str,
    answer: Any,
    tolerated: tuple[int, ...] = ()
) -> Any:
    '''
        The answer, once the tax office said it processed the request.

        A refused CUIS or CUFD comes back with empty codes; stored, it would
        poison every invoice of the day. The SIN's own messages go to the log,
        where a person can read why.

        Args:
            operation (str): Operation name, for the log.
            answer (Any): The response as zeep returns it.
            tolerated (tuple[int, ...]): SIN message codes that come with
                `transaccion` false and still carry a valid answer.

        Returns:
            Any: The same answer.

        Raises:
            InvalidInputError: The tax office refused the request.
    '''
    if getattr(answer, 'transaccion', False):
        return answer
    codes = {getattr(item, 'codigo', None)
             for item in (getattr(answer, 'mensajesList', None) or [])}
    # Tolerated only with the answer it promises: a 980 with no code is still
    # nothing to store.
    if codes & set(tolerated) and getattr(answer, 'codigo', None):
        return answer
    error_msg = (f'SIAT refused {operation}: '
                 f'{_receipt_from(answer).messages or "no messages"}')
    logger.error(error_msg)
    raise InvalidInputError(detail = BillingError.SIAT_REFUSED.value)


def request_cuis(emitter: Emitter) -> CuisResponse:
    '''
        Asks for the CUIS of a branch or point of sale.

        It is valid for a year, so it is asked for once and stored — not on
        every invoice.

        Args:
            emitter (Emitter): Who is issuing.

        Returns:
            CuisResponse: The code and the day it expires.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable or refused.
    '''
    answer = _accepted('cuis', invoke(SERVICE_CODES, 'cuis', base_request(emitter)),
                       tolerated = (CUIS_IN_FORCE,))
    return CuisResponse(
        cuis = str(answer.codigo),
        valid_until = str(answer.fechaVigencia)
    )


def request_cufd(
    emitter: Emitter,
    cuis: str
) -> CufdResponse:
    '''
        Asks for the CUFD, which lasts one day per point of sale.

        The control code it brings back is what closes the CUF, so a CUFD of
        the wrong day produces a CUF the tax office rejects.

        Args:
            emitter (Emitter): Who is issuing.
            cuis (str): The CUIS in force.

        Returns:
            CufdResponse: The code, its control code and where it is valid.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable or refused.
    '''
    answer = _accepted('cufd', invoke(SERVICE_CODES, 'cufd', {
        **base_request(emitter), 'cuis': cuis
    }))
    return CufdResponse(
        cufd = str(answer.codigo),
        control_code = str(answer.codigoControl),
        address = str(answer.direccion),
        valid_until = str(answer.fechaVigencia)
    )


def verify_document(
    emitter: Emitter,
    cuis: str,
    document: str
) -> bool:
    '''
        Whether a buyer's NIT is active in the tax register.

        Worth calling before issuing to a walk-in buyer: an invoice to a NIT
        that does not exist is rejected after the sale is already made.

        Args:
            emitter (Emitter): Who is issuing.
            cuis (str): The CUIS in force.
            document (str): The buyer's NIT.

        Returns:
            bool: True when the register knows it.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable or refused.
    '''
    answer = invoke(SERVICE_CODES, 'verificarNit', {
        **base_request(emitter), 'cuis': cuis, 'nitParaVerificacion': document
    })
    return bool(getattr(answer, 'transaccion', False))


@dataclass(frozen = True)
class InvoiceSubmission:
    '''
        One invoice as `recepcionFactura` takes it.

        `archive` is the GZIPped XML as bytes. The WSDL types it
        `base64Binary`, so zeep encodes it on the wire; encoding it here as
        well would send base64 of base64.
    '''
    cuis: str
    cufd: str
    archive: bytes
    sent_at: str


def send_invoice(
    emitter: Emitter,
    submission: InvoiceSubmission
) -> SiatReceipt:
    '''
        Hands one invoice to the tax office.

        It travels with the SHA-256 of the archive, so the SIAT can tell a
        truncated upload from a bad document.

        Args:
            emitter (Emitter): Who is issuing.
            submission (InvoiceSubmission): The codes in force and the document.

        Returns:
            SiatReceipt: What the tax office answered.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable.
    '''
    answer = invoke(SERVICE_INVOICE, 'recepcionFactura', {
        **base_request(emitter),
        'cuis': submission.cuis,
        'cufd': submission.cufd,
        'codigoDocumentoSector': SECTOR_DOCUMENT_PURCHASE_SALE,
        'codigoEmision': EMISSION_ONLINE,
        'tipoFacturaDocumento': INVOICE_WITH_TAX_CREDIT,
        'archivo': submission.archive,
        'fechaEnvio': submission.sent_at,
        'hashArchivo': hashlib.sha256(submission.archive).hexdigest()
    })
    return _receipt_from(answer)


@dataclass(frozen = True)
class InvoiceCancellation:
    '''
        One invoice as `anulacionFactura` takes it: the codes in force today,
        not those it was issued with, and the reason.
    '''
    cuis: str
    cufd: str
    cuf: str
    reason_code: int


def cancel_invoice(
    emitter: Emitter,
    cancellation: InvoiceCancellation
) -> SiatReceipt:
    '''
        Cancels an invoice already accepted.

        Args:
            emitter (Emitter): Who is issuing.
            cancellation (InvoiceCancellation): The codes, the CUF and the reason.

        Returns:
            SiatReceipt: What the tax office answered.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable.
    '''
    answer = invoke(SERVICE_INVOICE, 'anulacionFactura', {
        **base_request(emitter),
        'cuis': cancellation.cuis,
        'cufd': cancellation.cufd,
        'cuf': cancellation.cuf,
        'codigoDocumentoSector': SECTOR_DOCUMENT_PURCHASE_SALE,
        'codigoEmision': EMISSION_ONLINE,
        'tipoFacturaDocumento': INVOICE_WITH_TAX_CREDIT,
        'codigoMotivo': cancellation.reason_code
    })
    return _receipt_from(answer)


def _receipt_from(answer: Any) -> SiatReceipt:
    '''
        The tax office's answer as a DTO.

        Its messages are kept verbatim and never reworded: they are what a
        person reads to understand why a document was refused, and rewriting
        them would lose the SIN's own code.

        Args:
            answer (Any): The response as zeep returns it.

        Returns:
            SiatReceipt: The receipt.
    '''
    messages = [
        f'{getattr(item, "codigo", "")}: {getattr(item, "descripcion", "")}'.strip(': ')
        for item in (getattr(answer, 'mensajesList', None) or [])
    ]
    return SiatReceipt(
        accepted = bool(getattr(answer, 'transaccion', False)),
        reception_code = text(getattr(answer, 'codigoRecepcion', None)),
        state = text(getattr(answer, 'codigoEstado', None)),
        messages = messages
    )


def text(value: Any) -> str | None:
    '''
        One answer field as text, or nothing when it came back empty.

        Args:
            value (Any): The field.

        Returns:
            str | None: The text.
    '''
    return None if value is None else str(value)


# Where each shape of the synchronisation answer keeps its code and its
# description, in the order they are tried. Parametrics use
# codigoClasificador; activities, codigoCaeb; products, codigoProducto; and
# the activity of each sector document, codigoDocumentoSector. Legends have no
# code at all.
_CODE_FIELDS: Final[tuple[str, ...]] = (
    'codigoClasificador', 'codigoCaeb', 'codigoProducto', 'codigoDocumentoSector'
)
_DESCRIPTION_FIELDS: Final[tuple[str, ...]] = (
    'descripcion', 'descripcionProducto', 'descripcionLeyenda', 'tipoDocumentoSector'
)


# The SIN operation that brings each catalogue.
_SYNC_OPERATIONS: Final[dict[SiatCatalog, str]] = {
    SiatCatalog.ACTIVITIES: 'sincronizarActividades',
    SiatCatalog.SECTOR_DOCUMENT_ACTIVITIES: 'sincronizarListaActividadesDocumentoSector',
    SiatCatalog.LEGENDS: 'sincronizarListaLeyendasFactura',
    SiatCatalog.SERVICE_MESSAGES: 'sincronizarListaMensajesServicios',
    SiatCatalog.PRODUCTS_AND_SERVICES: 'sincronizarListaProductosServicios',
    SiatCatalog.SIGNIFICANT_EVENTS: 'sincronizarParametricaEventosSignificativos',
    SiatCatalog.CANCELLATION_REASONS: 'sincronizarParametricaMotivoAnulacion',
    SiatCatalog.COUNTRIES: 'sincronizarParametricaPaisOrigen',
    SiatCatalog.IDENTITY_DOCUMENT_TYPES: 'sincronizarParametricaTipoDocumentoIdentidad',
    SiatCatalog.SECTOR_DOCUMENT_TYPES: 'sincronizarParametricaTipoDocumentoSector',
    SiatCatalog.EMISSION_TYPES: 'sincronizarParametricaTipoEmision',
    SiatCatalog.ROOM_TYPES: 'sincronizarParametricaTipoHabitacion',
    SiatCatalog.PAYMENT_METHODS: 'sincronizarParametricaTipoMetodoPago',
    SiatCatalog.CURRENCIES: 'sincronizarParametricaTipoMoneda',
    SiatCatalog.POINT_OF_SALE_TYPES: 'sincronizarParametricaTipoPuntoVenta',
    SiatCatalog.INVOICE_TYPES: 'sincronizarParametricaTiposFactura',
    SiatCatalog.UNITS_OF_MEASURE: 'sincronizarParametricaUnidadMedida',
}


def sync_catalog(
    emitter: Emitter,
    cuis: str,
    catalog: SiatCatalog
) -> list[CatalogEntry]:
    '''
        Brings one catalogue from the tax office.

        The synchronisation request is the base one without the modality: the
        catalogues are the same whichever way the shop issues.

        Args:
            emitter (Emitter): Who is issuing.
            cuis (str): The CUIS in force.
            catalog (SiatCatalog): Which catalogue.

        Returns:
            list[CatalogEntry]: Its rows, as the SIN lists them.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable.
            InvalidInputError: The tax office refused the request.
    '''
    request = {**base_request(emitter), 'cuis': cuis}
    request.pop('codigoModalidad')
    operation = _SYNC_OPERATIONS[catalog]
    answer = _accepted(operation, invoke(SERVICE_SYNC, operation, request))
    return [_catalog_entry(row) for row in _catalog_rows(answer)]


def _catalog_rows(answer: Any) -> list[Any]:
    '''
        The list a synchronisation answer carries, whatever it is called.

        Every answer brings exactly one list besides its messages, named after
        the catalogue (listaCodigos, listaActividades, listaLeyendas...).

        Args:
            answer (Any): The response as zeep returns it.

        Returns:
            list[Any]: Its rows; empty when it brought none.
    '''
    for name, value in vars(answer).get('__values__', vars(answer)).items():
        if name != 'mensajesList' and isinstance(value, list):
            return value
    return []


def _catalog_entry(row: Any) -> CatalogEntry:
    '''
        One catalogue row as a DTO.

        Args:
            row (Any): The row as zeep returns it.

        Returns:
            CatalogEntry: Its code, description and activity.
    '''
    code = next((getattr(row, name) for name in _CODE_FIELDS
                 if getattr(row, name, None) is not None), '')
    description = next((getattr(row, name) for name in _DESCRIPTION_FIELDS
                        if getattr(row, name, None) is not None), '')
    return CatalogEntry(
        code = str(code),
        description = str(description),
        activity_code = text(getattr(row, 'codigoActividad', None))
    )
