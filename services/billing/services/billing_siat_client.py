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

    **Every call goes through one seam.** `_invoke` is the only place that
    talks to `zeep`, which is what makes the parameter assembly testable
    without a WSDL and what stops nine operations from each inventing their
    own error handling.

    References, all in `docs/siat/SIAT.md`: Solicitud CUIS, Solicitud CUFD,
    Verifica NIT, Recepción de factura, Anulación.
'''
import os
from dataclasses import dataclass
from typing import Any, Final

import requests
from zeep import Client, Settings
from zeep.exceptions import Error as ZeepError
from zeep.transports import Transport

from schemas.billing import BillingError, CuisResponse, CufdResponse, SiatReceipt
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
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
    return os.path.join(WSDL_DIR, f'{service}.wsdl')


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


def _invoke(
    service: str,
    operation: str,
    request: dict[str, Any]
) -> Any:
    '''
        The single seam that talks to the SIAT.

        Every operation goes through here, which is what makes the parameter
        assembly testable without a WSDL and what keeps one error path instead
        of nine.

        Args:
            service (str): Service name, as `SERVICE_*` spells it.
            operation (str): Operation name, as the WSDL spells it.
            request (dict[str, Any]): The request object's fields.

        Returns:
            Any: The response as zeep returns it.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable or refused.
    '''
    try:
        answer = getattr(_client(service).service, operation)(request)
    except (ZeepError, requests.exceptions.RequestException) as error:
        error_msg = f'SIAT operation {operation} failed: {error}'
        logger.error(error_msg)
        raise ServiceUnavailableError(
            detail = BillingError.SIAT_UNREACHABLE.value
        ) from error

    message = f'SIAT operation {operation} answered.'
    logger.info(message)
    return answer


def _base_request(emitter: Emitter) -> dict[str, Any]:
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
    answer = _invoke(SERVICE_CODES, 'cuis', _base_request(emitter))
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
    answer = _invoke(SERVICE_CODES, 'cufd', {**_base_request(emitter), 'cuis': cuis})
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
    answer = _invoke(SERVICE_CODES, 'verificarNit', {
        **_base_request(emitter), 'cuis': cuis, 'nitParaVerificacion': document
    })
    return bool(getattr(answer, 'transaccion', False))


def send_invoice(
    emitter: Emitter,
    codes: dict[str, str],
    packed_xml: str
) -> SiatReceipt:
    '''
        Hands one invoice to the tax office.

        The document travels GZIPped and base64-encoded, which is what
        `billing_siat.pack` produces, with its hash so the SIAT can tell a
        truncated upload from a bad document.

        Args:
            emitter (Emitter): Who is issuing.
            codes (dict[str, str]): The `cuis`, `cufd` and `cuf` in force.
            packed_xml (str): The invoice, packed and encoded.

        Returns:
            SiatReceipt: What the tax office answered.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable or refused.
    '''
    answer = _invoke(SERVICE_INVOICE, 'recepcionFactura', {
        **_base_request(emitter),
        'cuis': codes['cuis'],
        'cufd': codes['cufd'],
        'codigoDocumentoSector': 1,
        'codigoEmision': 1,
        'tipoFacturaDocumento': 1,
        'archivo': packed_xml,
        'fechaEnvio': codes.get('sent_at'),
        'hashArchivo': codes.get('hash')
    })
    return _receipt_from(answer)


def cancel_invoice(
    emitter: Emitter,
    codes: dict[str, str],
    reason_code: int
) -> SiatReceipt:
    '''
        Cancels an invoice already accepted.

        Args:
            emitter (Emitter): Who is issuing.
            codes (dict[str, str]): The `cuis`, `cufd` and `cuf` of the invoice.
            reason_code (int): Reason, from the SIN's parametric.

        Returns:
            SiatReceipt: What the tax office answered.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable or refused.
    '''
    answer = _invoke(SERVICE_INVOICE, 'anulacionFactura', {
        **_base_request(emitter),
        'cuis': codes['cuis'],
        'cufd': codes['cufd'],
        'cuf': codes['cuf'],
        'codigoDocumentoSector': 1,
        'codigoMotivo': reason_code
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
        reception_code = _text(getattr(answer, 'codigoRecepcion', None)),
        state = _text(getattr(answer, 'codigoEstado', None)),
        messages = messages
    )


def _text(value: Any) -> str | None:
    '''
        One answer field as text, or nothing when it came back empty.

        Args:
            value (Any): The field.

        Returns:
            str | None: The text.
    '''
    return None if value is None else str(value)
