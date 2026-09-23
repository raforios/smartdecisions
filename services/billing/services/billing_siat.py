'''
    Facturación electrónica boliviana: los algoritmos del SIAT.

    Todo lo de este archivo es determinista y no habla con nadie: el CUF lo
    genera **nuestro** sistema, no Impuestos, así que se puede implementar y
    probar entero antes de tener la autorización. Lo que sí depende del SIN
    —los servicios SOAP, el CUIS, el CUFD y el código de control— vive fuera
    de acá y todavía no existe.

    Cada función está verificada contra el ejemplo resuelto que publica el
    propio SIAT en `docs/siat/SIAT.md`; ese ejemplo es el test.

    Referencias, todas en `docs/siat/SIAT.md`:
        - Generación del CUF
        - Algoritmo módulo 11
        - Algoritmo base 16
        - Compresión GZIP
'''
import base64
import gzip
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# El SIAT numera sus catálogos; acá sólo van los que BILLING emite hoy. El
# resto se agrega cuando se venda a un rubro que los necesite.
MODALIDAD_COMPUTARIZADA_EN_LINEA = 2
MODALIDAD_ELECTRONICA_EN_LINEA = 1

EMISION_ONLINE = 1
EMISION_OFFLINE = 2

FACTURA_CON_CREDITO_FISCAL = 1
FACTURA_SIN_CREDITO_FISCAL = 2

DOCUMENTO_SECTOR_COMPRA_VENTA = 1

# Longitud de cada campo del CUF, en el orden en que se concatenan. La suma da
# 53; el dígito autoverificador lo lleva a 54.
CUF_WIDTHS = (
    ('nit', 13),
    ('issued_at', 17),
    ('branch', 4),
    ('modality', 1),
    ('emission_type', 1),
    ('invoice_type', 1),
    ('sector_document', 2),
    ('invoice_number', 10),
    ('point_of_sale', 4)
)


@dataclass(frozen = True)
class CufInput:
    '''
        Lo que identifica a una factura de forma única ante el SIN.

        Args:
            nit (str): NIT del emisor.
            issued_at (datetime): Momento exacto de la emisión, con milisegundos.
            invoice_number (int): Correlativo de la factura.
            branch (int): Sucursal; 0 es casa matriz.
            point_of_sale (int): Punto de venta; 0 cuando no corresponde.
            modality (int): 1 electrónica en línea, 2 computarizada en línea.
            emission_type (int): 1 en línea, 2 fuera de línea.
            invoice_type (int): 1 con crédito fiscal, 2 sin él.
            sector_document (int): Tipo de documento sector; 1 compra-venta.
    '''
    nit: str
    issued_at: datetime
    invoice_number: int
    branch: int = 0
    point_of_sale: int = 0
    modality: int = MODALIDAD_COMPUTARIZADA_EN_LINEA
    emission_type: int = EMISION_ONLINE
    invoice_type: int = FACTURA_CON_CREDITO_FISCAL
    sector_document: int = DOCUMENTO_SECTOR_COMPRA_VENTA


def check_digit(
    chain: str,
    limit: int = 9
) -> str:
    '''
        El dígito autoverificador de una cadena, por módulo 11.

        El SIAT lo publica en Java y en C#; esto es esa misma cuenta. Se suma
        cada dígito por un multiplicador que sube de 2 al límite y vuelve a
        empezar, y el resto decide: 10 escribe "1", 11 escribe "0".

        Args:
            chain (str): Cadena de dígitos a verificar.
            limit (int): Multiplicador máximo antes de reiniciar en 2.

        Returns:
            str: Un dígito.

        Raises:
            ValueError: La cadena trae algo que no es un dígito.
    '''
    if not chain.isdigit():
        raise ValueError('El módulo 11 sólo acepta dígitos.')

    total, multiplier = 0, 2
    for char in reversed(chain):
        total += multiplier * int(char)
        multiplier += 1
        if multiplier > limit:
            multiplier = 2

    digit = ((total * 10) % 11) % 10
    if digit == 10:
        return '1'
    if digit == 11:
        return '0'
    return str(digit)


def cuf_chain(data: CufInput) -> str:
    '''
        Los 53 dígitos que identifican la factura, antes del verificador.

        Args:
            data (CufInput): Datos de la factura.

        Returns:
            str: Cadena de 53 dígitos, cada campo rellenado con ceros a la
                izquierda hasta su longitud.
    '''
    values = {
        'nit': data.nit,
        'issued_at': data.issued_at.strftime('%Y%m%d%H%M%S') +
                     f'{data.issued_at.microsecond // 1000:03d}',
        'branch': str(data.branch),
        'modality': str(data.modality),
        'emission_type': str(data.emission_type),
        'invoice_type': str(data.invoice_type),
        'sector_document': str(data.sector_document),
        'invoice_number': str(data.invoice_number),
        'point_of_sale': str(data.point_of_sale)
    }
    return ''.join(values[field].zfill(width) for field, width in CUF_WIDTHS)


def build_cuf(
    data: CufInput,
    control_code: Optional[str] = None
) -> str:
    '''
        El Código Único de Factura.

        La cadena de 53 dígitos recibe su verificador, el número resultante se
        escribe en base 16, y al final se concatena el código de control que
        devolvió el servicio de CUFD.

        Args:
            data (CufInput): Datos de la factura.
            control_code (str | None): Código de control del CUFD del día.
                Sin él, el CUF queda incompleto y sirve sólo para pruebas.

        Returns:
            str: El CUF.
    '''
    chain = cuf_chain(data)
    numeric = chain + check_digit(chain)
    # Base 16 del número completo, no de cada dígito: el ejemplo de la norma
    # convierte 54 dígitos decimales en 41 caracteres hexadecimales.
    base16 = format(int(numeric), 'X')
    return f'{base16}{control_code}' if control_code else base16


def pack(xml: str) -> str:
    '''
        El XML como lo espera el sobre SOAP: comprimido y en base64.

        Args:
            xml (str): Documento XML de la factura.

        Returns:
            str: El mismo documento, gzip + base64.
    '''
    return base64.b64encode(gzip.compress(xml.encode('utf-8'))).decode('ascii')


def unpack(payload: str) -> str:
    '''
        El inverso de `pack`, para leer lo que se envió.

        Args:
            payload (str): Cadena gzip + base64.

        Returns:
            str: El XML original.
    '''
    return gzip.decompress(base64.b64decode(payload)).decode('utf-8')


def mask_card(number: str) -> str:
    '''
        Un número de tarjeta con el centro en ceros.

        La Fase II de la autorización lo exige: se conservan los cuatro
        primeros y los cuatro últimos, el resto se reemplaza por ceros.

        Args:
            number (str): Número tal como lo dio el comprador.

        Returns:
            str: El número enmascarado.

        Raises:
            ValueError: El número tiene menos de ocho dígitos.
    '''
    digits = ''.join(char for char in number if char.isdigit())
    if len(digits) < 8:
        raise ValueError('Un número de tarjeta no puede tener menos de 8 dígitos.')
    return f'{digits[:4]}{"0" * (len(digits) - 8)}{digits[-4:]}'
