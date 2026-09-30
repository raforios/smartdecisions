'''
    The invoice XML the SIN receives.

    It lives apart from `billing_siat.py` because it answers a different
    question. That module holds the algorithms —the CUF, the modulus 11, the
    GZIP— which are pure arithmetic. This one builds a document against a
    schema somebody else wrote, and the schema is the authority: every element
    name, its order and its nillability come from
    `docs/siat/facturaComputarizadaCompraVenta.xsd`.

    Two decisions worth stating, because they are what make this safe to trust:

    **The order of the elements is not a style choice.** The XSD declares an
    `xs:sequence`, so an element out of place makes the document invalid even
    when every value in it is right. The order here is the order in the file,
    read top to bottom, and the test validates against the real XSD rather
    than against our idea of it.

    **Nothing is invented.** A field the pharmacy has not homologated —the
    economic activity, the SIN product code, the unit— is not filled with a
    plausible number: it is reported as missing. An invoice sent with a made-up
    product code is rejected by the tax office, and worse, it is rejected
    *after* the sale is already in the client's hands.
'''
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional
from xml.etree.ElementTree import Element, SubElement, tostring

from lxml import etree

from schemas.billing import (
    SIN_PAYMENT_CODES,
    BillingError,
    InvoiceContext,
    InvoiceLine,
    PaymentMethod,
    SaleNoteOut
)
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger

ROOT_ELEMENT = 'facturaComputarizadaCompraVenta'

# An absent value is NOT an empty element. The XSD types every optional field
# —`numeroTarjeta` as an integer, `montoDescuento` as a decimal— and declares
# it `nillable`, which means the element must SAY it is nil rather than carry
# an empty string. An empty `<numeroTarjeta />` fails validation as "not a
# valid value of the local atomic type", which is exactly the error the schema
# reported the first time this was written.
XSI_NAMESPACE = 'http://www.w3.org/2001/XMLSchema-instance'
NIL_ATTRIBUTE = '{%s}nil' % XSI_NAMESPACE

# Fixed by the XSD itself (`fixed="1"`): this product issues purchase-sale
# documents and nothing else.
SECTOR_DOCUMENT = 1

# The XSD caps `detalle` at 500 occurrences. A sale with more lines cannot be
# sent as one invoice, and finding that out at the tax office instead of here
# would mean the paper is already printed.
MAX_DETAIL_LINES = 500

# Every amount in the schema is `xs:decimal` with two fraction digits. Sending
# more is a validation error; sending a float's repr is how 0.1 + 0.2 reaches
# the tax office as 0.30000000000000004.
AMOUNT_QUANTUM = Decimal('0.01')


def _amount(value: float) -> str:
    '''
        One amount as the schema wants it: two fraction digits, always.

        Args:
            value (float): The amount.

        Returns:
            str: The amount, rounded half up.
    '''
    return str(Decimal(str(value)).quantize(AMOUNT_QUANTUM, rounding = ROUND_HALF_UP))


def _put(
    parent: Element,
    name: str,
    value: object
) -> None:
    '''
        Writes one element, marking it nil when there is no value.

        The element is always written: the XSD declares an `xs:sequence`, so a
        missing element breaks the order of everything after it. What changes
        is how absence is expressed — `xsi:nil="true"` and not an empty
        string, because these fields are typed and an empty string is not a
        valid integer or decimal.

        Args:
            parent (Element): Element to write into.
            name (str): Element name, as the XSD spells it.
            value (object): The value, or None.
    '''
    child = SubElement(parent, name)
    if value is None:
        child.set(NIL_ATTRIBUTE, 'true')
    else:
        child.text = str(value)


def _missing_homologation(lines: List[InvoiceLine]) -> List[str]:
    '''
        The SIN codes the sale's products have not been homologated with.

        Args:
            lines (List[InvoiceLine]): The lines as the invoice needs them.

        Returns:
            List[str]: One entry per line missing a code, naming the SKU.
    '''
    missing: List[str] = []
    for line in lines:
        absent = [name for name, code in (
            ('actividad', line.sin_activity_code),
            ('producto', line.sin_product_code),
            ('unidad', line.sin_unit_code)
        ) if not code]
        if absent:
            missing.append(f'{line.sku}: {", ".join(absent)}')
    return missing


def _card_for_xml(sale: SaleNoteOut) -> Optional[str]:
    '''
        The masked card number, as the schema types it.

        The XSD declares `numeroTarjeta` as an integer, so the masked number
        travels with no separators. It is only ever present on a card sale;
        the tax office reports it as an error otherwise.

        Args:
            sale (SaleNoteOut): The issued sale.

        Returns:
            str | None: The digits, or None.
    '''
    if sale.payment_method is not PaymentMethod.TARJETA:
        return None
    return sale.card_number or None


def _build_header(
    root: Element,
    sale: SaleNoteOut,
    context: InvoiceContext
) -> None:
    '''
        Writes `cabecera`, in the order the XSD declares it.

        Args:
            root (Element): The document root.
            sale (SaleNoteOut): The issued sale.
            context (InvoiceContext): What the sale itself does not carry.
    '''
    header = SubElement(root, 'cabecera')
    _put(header, 'nitEmisor', context.issuer_document)
    _put(header, 'razonSocialEmisor', context.trade_name)
    _put(header, 'municipio', context.municipality)
    _put(header, 'telefono', context.phone)
    _put(header, 'numeroFactura', context.invoice_number)
    _put(header, 'cuf', context.cuf)
    _put(header, 'cufd', context.cufd)
    _put(header, 'codigoSucursal', context.branch)
    _put(header, 'direccion', context.address)
    _put(header, 'codigoPuntoVenta', context.point_of_sale)
    _put(header, 'fechaEmision', context.issued_at)
    _put(header, 'nombreRazonSocial', sale.buyer.name)
    _put(header, 'codigoTipoDocumentoIdentidad', sale.buyer.document_type)
    _put(header, 'numeroDocumento', sale.buyer.document)
    _put(header, 'complemento', None)
    _put(header, 'codigoCliente', sale.buyer.document)
    _put(header, 'codigoMetodoPago', SIN_PAYMENT_CODES[sale.payment_method])
    _put(header, 'numeroTarjeta', _card_for_xml(sale))
    _put(header, 'montoTotal', _amount(sale.total))
    _put(header, 'montoTotalSujetoIva', _amount(sale.total))
    _put(header, 'codigoMoneda', context.currency_code)
    _put(header, 'tipoCambio', _amount(context.exchange_rate))
    _put(header, 'montoTotalMoneda', _amount(sale.total))
    _put(header, 'montoGiftCard', None)
    _put(header, 'descuentoAdicional', None)
    _put(header, 'codigoExcepcion', None)
    _put(header, 'cafc', context.cafc)
    _put(header, 'leyenda', context.legend)
    _put(header, 'usuario', sale.created_by)
    _put(header, 'codigoDocumentoSector', SECTOR_DOCUMENT)


def _build_detail(
    root: Element,
    lines: List[InvoiceLine]
) -> None:
    '''
        Writes one `detalle` per line, in the order the XSD declares it.

        Args:
            root (Element): The document root.
            lines (List[InvoiceLine]): The lines as the invoice needs them.
    '''
    for line in lines:
        detail = SubElement(root, 'detalle')
        _put(detail, 'actividadEconomica', line.sin_activity_code)
        _put(detail, 'codigoProductoSin', line.sin_product_code)
        _put(detail, 'codigoProducto', line.sku)
        _put(detail, 'descripcion', line.description)
        _put(detail, 'cantidad', _amount(line.quantity))
        _put(detail, 'unidadMedida', line.sin_unit_code)
        _put(detail, 'precioUnitario', _amount(line.unit_price))
        # Zero and not nil: a line with no discount has a discount OF zero, not
        # an unknown one. The SIN's own example XML sends it that way.
        _put(detail, 'montoDescuento', _amount(line.discount))
        _put(detail, 'subTotal', _amount(line.subtotal))
        _put(detail, 'numeroSerie', None)
        _put(detail, 'numeroImei', None)


def build_invoice_xml(
    sale: SaleNoteOut,
    context: InvoiceContext,
    lines: List[InvoiceLine]
) -> str:
    '''
        Builds the invoice XML of one sale.

        Args:
            sale (SaleNoteOut): The issued sale, as it was stored.
            context (InvoiceContext): Everything the sale does not carry — the
                issuer, the CUF and CUFD, the legend and the exchange rate.
            lines (List[InvoiceLine]): The sale's lines with the three SIN
                codes their products were homologated with.

        Returns:
            str: The XML document.

        Raises:
            InvalidInputError: A product is not homologated with the SIN, or
                the sale has more lines than one invoice may carry.
    '''
    missing = _missing_homologation(lines)
    if missing:
        error_msg = f'Sale {sale.number} cannot be invoiced; missing SIN codes: {missing}.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = BillingError.PRODUCT_NOT_HOMOLOGATED.value)

    if len(lines) > MAX_DETAIL_LINES:
        error_msg = (f'Sale {sale.number} has {len(lines)} lines; one invoice '
                     f'carries at most {MAX_DETAIL_LINES}.')
        logger.warning(error_msg)
        raise InvalidInputError(detail = BillingError.TOO_MANY_LINES.value)

    root = Element(ROOT_ELEMENT)
    _build_header(root, sale, context)
    _build_detail(root, lines)

    message = f'Invoice XML built for sale {sale.number}: {len(lines)} line(s).'
    logger.info(message)
    return tostring(root, encoding = 'unicode')


def validate_against_schema(
    xml: str,
    schema_path: str
) -> List[str]:
    '''
        Validates a document against the XSD the SIN publishes.

        It returns the problems instead of raising, because the caller decides
        what to do with them: during development they are printed, and in
        production a document that does not validate must never be sent — the
        tax office would reject it after the sale is already made.

        Args:
            xml (str): The document.
            schema_path (str): Path to the .xsd.

        Returns:
            List[str]: One message per violation; empty when it validates.
    '''
    with open(schema_path, 'rb') as handle:
        schema = etree.XMLSchema(etree.parse(handle))
    try:
        # assertValid and not validate: the exception carries the whole error
        # log as text, so the problems come back without iterating a C-extension
        # object that static analysis cannot see into.
        schema.assertValid(etree.fromstring(xml.encode('utf-8')))
        return []
    except etree.DocumentInvalid as invalid:
        return [line for line in str(invalid.error_log).splitlines() if line.strip()]
