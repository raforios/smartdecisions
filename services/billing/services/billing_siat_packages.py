'''
    The SIAT web services of contingency: what is asked of the tax office when
    a shop could not reach it and has to catch up.

    Apart from `billing_siat_client.py` because they answer a different moment.
    That module serves every sale; this one serves the minutes after an outage:
    checking that the SIN answers again, registering the significant event and
    sending the invoices issued offline in packages.

    Two facts the documentation does not state and the pilot does (27-oct):
    the package is a TAR of the invoice XMLs, GZIPped; and the event cannot
    start before its CUFD was issued, or the SIN answers 984.

    References: `docs/siat/SIAT.md`, Registro Evento Significativo, and the
    SIN's pages on contingency, Recepción Paquete Factura, Validación Recepción
    Paquete Factura and Verifica Comunicación.
'''
import gzip
import hashlib
import io
import tarfile
from dataclasses import dataclass
from typing import Any, Final

from schemas.billing import (
    EMISSION_OFFLINE,
    EMISSION_ONLINE,
    INVOICE_WITH_TAX_CREDIT,
    SECTOR_DOCUMENT_PURCHASE_SALE,
    BillingError
)
from schemas.billing_siat import PackageReceipt
from services import billing_siat_client as siat_client
from services.billing_siat_client import Emitter
from services.exceptions import InvalidInputError, ServiceUnavailableError
from services.logger_config import custom_logger as logger

SERVICE_OPERATIONS = 'operaciones'

# What `verificarComunicacion` answers when the SIN is there.
COMMUNICATION_OK: Final[int] = 926

# A package carries at most this many invoices: the SIN's own limit.
MAX_PACKAGE_INVOICES: Final[int] = 500


@dataclass(frozen = True)
class EventRegistration:
    '''
        One significant event, as `registroEventoSignificativo` takes it.

        `cufd` is the code in force now, asked for after the outage;
        `cufd_event` is the one the offline invoices were issued with.
    '''
    cuis: str
    cufd: str
    cufd_event: str
    event_code: int
    description: str
    started_at: str
    ended_at: str


@dataclass(frozen = True)
class PackageSubmission:
    '''
        One package of offline invoices, as `recepcionPaqueteFactura` takes it.
    '''
    cuis: str
    cufd: str
    event_reception_code: int
    invoices: list[tuple[str, str]]
    sent_at: str
    # Only on transcribed paper invoices: one package, one CAFC.
    cafc: str | None = None


def verify_communication() -> bool:
    '''
        Whether the invoicing service of the SIN answers.

        The documentation promises the code 926; the pilot answers
        `transaccion` true and no message at all (27-oct). Either is an answer.

        Returns:
            bool: True when the SIN answered; an outage is False, not an error.
    '''
    try:
        answer = siat_client.invoke(siat_client.SERVICE_INVOICE, 'verificarComunicacion', None)
    except ServiceUnavailableError:
        return False
    codes = {getattr(item, 'codigo', None) for item in getattr(answer, 'mensajesList', None) or []}
    return bool(getattr(answer, 'transaccion', False)) or COMMUNICATION_OK in codes


def register_event(
    emitter: Emitter,
    event: EventRegistration
) -> int:
    '''
        Registers a significant event.

        Args:
            emitter (Emitter): Who issued during the event.
            event (EventRegistration): Its codes, reason and window.

        Returns:
            int: The reception code the packages of this event carry.

        Raises:
            InvalidInputError: SIAT_REFUSED, with the SIN's messages in the log.
            ServiceUnavailableError: The SIAT is unreachable.
    '''
    request = {**siat_client.base_request(emitter), 'cuis': event.cuis, 'cufd': event.cufd,
               'cufdEvento': event.cufd_event, 'codigoMotivoEvento': event.event_code,
               'descripcion': event.description,
               'fechaHoraInicioEvento': event.started_at,
               'fechaHoraFinEvento': event.ended_at,
               'codigoPuntoVenta': emitter.point_of_sale or 0}
    # The operations service does not take the modality.
    request.pop('codigoModalidad', None)
    answer = siat_client.invoke(SERVICE_OPERATIONS, 'registroEventoSignificativo', request)
    code = getattr(answer, 'codigoRecepcionEventoSignificativo', None)
    if not getattr(answer, 'transaccion', False) or code is None:
        error_msg = (f'SIAT refused the significant event of {emitter.nit}: '
                     f'{_messages(answer) or "no messages"}')
        logger.error(error_msg)
        raise InvalidInputError(detail = BillingError.SIAT_REFUSED.value)
    message = f'Significant event {event.event_code} registered for {emitter.nit}: {code}.'
    logger.info(message)
    return int(code)


def pack_invoices(invoices: list[tuple[str, str]]) -> bytes:
    '''
        The package archive: a TAR of the invoice XMLs, GZIPped.

        Args:
            invoices (list[tuple[str, str]]): (file name, XML) of each invoice.

        Returns:
            bytes: The archive.
    '''
    buffer = io.BytesIO()
    with tarfile.open(fileobj = buffer, mode = 'w') as tar:
        for name, xml in invoices:
            data = xml.encode('utf-8')
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return gzip.compress(buffer.getvalue())


def send_package(
    emitter: Emitter,
    package: PackageSubmission
) -> PackageReceipt:
    '''
        Hands one package of offline invoices to the SIN.

        Args:
            emitter (Emitter): Who issued them.
            package (PackageSubmission): The codes, the event and the invoices.

        Returns:
            PackageReceipt: 901 and the reception code when received.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable.
    '''
    archive = pack_invoices(package.invoices)
    answer = siat_client.invoke(siat_client.SERVICE_INVOICE, 'recepcionPaqueteFactura', {
        **_offline_request(emitter, package.cuis, package.cufd),
        'archivo': archive,
        'fechaEnvio': package.sent_at,
        'hashArchivo': hashlib.sha256(archive).hexdigest(),
        'cantidadFacturas': len(package.invoices),
        'codigoEvento': package.event_reception_code,
        **({'cafc': package.cafc} if package.cafc else {})
    })
    return _package_receipt(answer)


def validate_package(
    emitter: Emitter,
    codes: tuple[str, str],
    reception_code: str
) -> PackageReceipt:
    '''
        Asks how a package was validated.

        Args:
            emitter (Emitter): Who issued it.
            codes (tuple[str, str]): The CUIS and the CUFD in force.
            reception_code (str): What the SIN answered on receiving it.

        Returns:
            PackageReceipt: 901 still pending, 908 validated or 904 observed,
                with the invoices that failed.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable.
    '''
    answer = siat_client.invoke(siat_client.SERVICE_INVOICE, 'validacionRecepcionPaqueteFactura', {
        **_offline_request(emitter, *codes), 'codigoRecepcion': reception_code
    })
    return _package_receipt(answer)


def invoice_state(
    emitter: Emitter,
    codes: tuple[str, str],
    cuf: str
) -> str | None:
    '''
        The state the SIN holds for one invoice, to settle one whose sending
        was cut before any answer came.

        Args:
            emitter (Emitter): Who issued it.
            codes (tuple[str, str]): The CUIS and the CUFD in force.
            cuf (str): The invoice.

        Returns:
            str | None: The SIN's codigoEstado (908 valid, 905 cancelled), or
                None when the SIN does not know it.

        Raises:
            ServiceUnavailableError: The SIAT is unreachable.
    '''
    cuis, cufd = codes
    answer = siat_client.invoke(siat_client.SERVICE_INVOICE, 'verificacionEstadoFactura', {
        **siat_client.base_request(emitter), 'cuis': cuis, 'cufd': cufd, 'cuf': cuf,
        'codigoDocumentoSector': SECTOR_DOCUMENT_PURCHASE_SALE,
        'codigoEmision': EMISSION_ONLINE,
        'tipoFacturaDocumento': INVOICE_WITH_TAX_CREDIT
    })
    state = getattr(answer, 'codigoEstado', None)
    return None if state is None else str(state)


def _offline_request(
    emitter: Emitter,
    cuis: str,
    cufd: str
) -> dict[str, Any]:
    '''
        The fields every package request carries.

        Args:
            emitter (Emitter): Who issued.
            cuis (str): The CUIS in force.
            cufd (str): The CUFD in force.

        Returns:
            dict[str, Any]: The common parameters.
    '''
    return {**siat_client.base_request(emitter), 'cuis': cuis, 'cufd': cufd,
            'codigoDocumentoSector': SECTOR_DOCUMENT_PURCHASE_SALE,
            'codigoEmision': EMISSION_OFFLINE,
            'tipoFacturaDocumento': INVOICE_WITH_TAX_CREDIT}


def _package_receipt(answer: Any) -> PackageReceipt:
    '''
        A package answer as a DTO, with the invoices the SIN observed.

        The SIN numbers the files of the package from zero, in the order they
        went in the archive; that number is how an observation finds its
        invoice.

        Args:
            answer (Any): The response as zeep returns it.

        Returns:
            PackageReceipt: The receipt.
    '''
    observed: dict[int, list[str]] = {}
    for item in getattr(answer, 'mensajesList', None) or []:
        number = getattr(item, 'numeroArchivo', None)
        if number is not None:
            observed.setdefault(int(number), []).append(
                f'{getattr(item, "codigo", "")}: {getattr(item, "descripcion", "")}'
            )
    state = getattr(answer, 'codigoEstado', None)
    return PackageReceipt(
        accepted = bool(getattr(answer, 'transaccion', False)),
        reception_code = siat_client.text(getattr(answer, 'codigoRecepcion', None)),
        state = None if state is None else str(state),
        messages = _messages(answer),
        observed = observed
    )


def _messages(answer: Any) -> list[str]:
    '''
        The SIN's messages, verbatim.

        Args:
            answer (Any): The response as zeep returns it.

        Returns:
            list[str]: "code: description" each.
    '''
    return [f'{getattr(item, "codigo", "")}: {getattr(item, "descripcion", "")}'
            for item in getattr(answer, 'mensajesList', None) or []]
