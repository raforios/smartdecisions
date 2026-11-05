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
from xml.etree.ElementTree import Element, SubElement, tostring

from lxml import etree

from schemas.billing import (
    BillingError,
    InvoiceContext,
    InvoiceLine,
    SaleNoteOut
)
from services.billing_payments import paid_by_card
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger
from services.utils import load_parameters

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

# The XSD caps `detalle` (500 occurrences today). A sale with more lines
# cannot be sent as one invoice, and finding that out at the tax office
# instead of here would mean the paper is already printed.
MAX_DETAIL_LINES: int = load_parameters({'BILLING_MAX_DETAIL_LINES': int})[
    'BILLING_MAX_DETAIL_LINES']

# Every amount in the schema is `xs:decimal` with two fraction digits. Sending
# more is a validation error; sending a float's repr is how 0.1 + 0.2 reaches
# the tax office as 0.30000000000000004.
AMOUNT_QUANTUM = Decimal('0.01')


def xml_amount(value: float) -> str:
    '''
        One amount as the schema wants it: two fraction digits, always.

        Args:
            value (float): The amount.

        Returns:
            str: The amount, rounded half up.
    '''
    return str(Decimal(str(value)).quantize(AMOUNT_QUANTUM, rounding = ROUND_HALF_UP))


def put_element(
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


def _missing_homologation(lines: list[InvoiceLine]) -> list[str]:
    '''
        The SIN codes the sale's products have not been homologated with.

        Args:
            lines (list[InvoiceLine]): The lines as the invoice needs them.

        Returns:
            list[str]: One entry per line missing a code, naming the SKU.
    '''
    missing: list[str] = []
    for line in lines:
        absent = [name for name, code in (
            ('actividad', line.sin_activity_code),
            ('producto', line.sin_product_code),
            ('unidad', line.sin_unit_code)
        ) if not code]
        if absent:
            missing.append(f'{line.sku}: {", ".join(absent)}')
    return missing


def require_homologated(lines: list[InvoiceLine]) -> None:
    '''
        Refuses lines whose products are not homologated with the SIN.

        Public so a sale can be refused before any stock moves, not only when
        the document is built.

        Args:
            lines (list[InvoiceLine]): The lines as the invoice needs them.

        Raises:
            InvalidInputError: PRODUCT_NOT_HOMOLOGATED.
    '''
    missing = _missing_homologation(lines)
    if missing:
        error_msg = f'Lines cannot be invoiced; missing SIN codes: {missing}.'
        logger.warning(error_msg)
        raise InvalidInputError(detail = BillingError.PRODUCT_NOT_HOMOLOGATED.value)


def _card_for_xml(sale: SaleNoteOut) -> str | None:
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
    if not paid_by_card([payment.method for payment in sale.payments]
                        or [sale.payment_method]):
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
    put_element(header, 'nitEmisor', context.issuer_document)
    put_element(header, 'razonSocialEmisor', context.trade_name)
    put_element(header, 'municipio', context.municipality)
    put_element(header, 'telefono', context.phone)
    put_element(header, 'numeroFactura', context.invoice_number)
    put_element(header, 'cuf', context.cuf)
    put_element(header, 'cufd', context.cufd)
    put_element(header, 'codigoSucursal', context.branch)
    put_element(header, 'direccion', context.address)
    put_element(header, 'codigoPuntoVenta', context.point_of_sale)
    put_element(header, 'fechaEmision', context.issued_at)
    put_element(header, 'nombreRazonSocial', sale.buyer.name)
    put_element(header, 'codigoTipoDocumentoIdentidad', sale.buyer.document_type)
    put_element(header, 'numeroDocumento', sale.buyer.document)
    put_element(header, 'complemento', None)
    put_element(header, 'codigoCliente', sale.buyer.document)
    put_element(header, 'codigoMetodoPago', context.payment_method_code)
    put_element(header, 'numeroTarjeta', _card_for_xml(sale))
    put_element(header, 'montoTotal', xml_amount(sale.total))
    put_element(header, 'montoTotalSujetoIva', xml_amount(sale.total))
    put_element(header, 'codigoMoneda', context.currency_code)
    put_element(header, 'tipoCambio', xml_amount(context.exchange_rate))
    put_element(header, 'montoTotalMoneda', xml_amount(sale.total))
    put_element(header, 'montoGiftCard', None)
    put_element(header, 'descuentoAdicional', None)
    put_element(header, 'codigoExcepcion', context.exception_code)
    put_element(header, 'cafc', context.cafc)
    put_element(header, 'leyenda', context.legend)
    put_element(header, 'usuario', sale.created_by)
    put_element(header, 'codigoDocumentoSector', SECTOR_DOCUMENT)


def put_detail_figures(
    detail: Element,
    line: InvoiceLine
) -> None:
    '''
        Writes the figures every `detalle` of the SIN opens with, in the order
        its XSDs declare them: the invoice's and the credit note's share these
        nine and differ only in what follows.

        Args:
            detail (Element): The `detalle` element.
            line (InvoiceLine): The line, with its SIN codes.
    '''
    put_element(detail, 'actividadEconomica', line.sin_activity_code)
    put_element(detail, 'codigoProductoSin', line.sin_product_code)
    put_element(detail, 'codigoProducto', line.sku)
    put_element(detail, 'descripcion', line.description)
    put_element(detail, 'cantidad', xml_amount(line.quantity))
    put_element(detail, 'unidadMedida', line.sin_unit_code)
    put_element(detail, 'precioUnitario', xml_amount(line.unit_price))
    # Zero and not nil: a line with no discount has a discount OF zero, not
    # an unknown one. The SIN's own example XML sends it that way.
    put_element(detail, 'montoDescuento', xml_amount(line.discount))
    put_element(detail, 'subTotal', xml_amount(line.subtotal))


def _build_detail(
    root: Element,
    lines: list[InvoiceLine]
) -> None:
    '''
        Writes one `detalle` per line, in the order the XSD declares it.

        Args:
            root (Element): The document root.
            lines (list[InvoiceLine]): The lines as the invoice needs them.
    '''
    for line in lines:
        detail = SubElement(root, 'detalle')
        put_detail_figures(detail, line)
        put_element(detail, 'numeroSerie', None)
        put_element(detail, 'numeroImei', None)


def build_invoice_xml(
    sale: SaleNoteOut,
    context: InvoiceContext,
    lines: list[InvoiceLine]
) -> str:
    '''
        Builds the invoice XML of one sale.

        Args:
            sale (SaleNoteOut): The issued sale, as it was stored.
            context (InvoiceContext): Everything the sale does not carry — the
                issuer, the CUF and CUFD, the legend and the exchange rate.
            lines (list[InvoiceLine]): The sale's lines with the three SIN
                codes their products were homologated with.

        Returns:
            str: The XML document.

        Raises:
            InvalidInputError: A product is not homologated with the SIN, or
                the sale has more lines than one invoice may carry.
    '''
    require_homologated(lines)

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
) -> list[str]:
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
            list[str]: One message per violation; empty when it validates.
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
