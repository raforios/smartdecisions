'''
    The XML of a Nota de Crédito-Débito.

    Same rules as the invoice XML (`billing_invoice_xml.py`), whose helpers it
    uses: the schema is the authority, so every element name and its order
    come from `docs/siat/notaComputarizadaCreditoDebito.xsd`, and an absent
    value is written nil, never empty.

    What is particular to this document: its details carry the original sale
    AND what is returned, each detail marked by `codigoDetalleTransaccion`
    (1 original, 2 returned), and its header names the invoice it adjusts.
'''
from xml.etree.ElementTree import Element, SubElement, tostring

from schemas.billing import InvoiceLine, SaleLineOut
from schemas.billing_returns import (
    DETAIL_ORIGINAL,
    DETAIL_RETURNED,
    SECTOR_DOCUMENT_CREDIT_DEBIT,
    CreditNoteDocument,
    CreditNoteIssuer,
    CreditNoteLineOut
)
from services.billing_invoice_xml import _amount, _put, put_detail_figures, require_homologated
from services.logger_config import custom_logger as logger

ROOT_ELEMENT = 'notaFiscalComputarizadaCreditoDebito'

MONEY_DECIMALS = 2


def as_sold_line(line: CreditNoteLineOut) -> SaleLineOut:
    '''
        A returned line in the shape of a sold one, so it becomes details the
        way the invoice's lines did.

        Args:
            line (CreditNoteLineOut): The returned line.

        Returns:
            SaleLineOut: The same units, prices and discount.
    '''
    return SaleLineOut(
        sku = line.sku, description = line.description, quantity = line.quantity,
        discount = line.discount, allocations = line.allocations, total = line.total,
        subtotal = round(line.total + line.discount, MONEY_DECIMALS),
        cost = round(sum(allocation.quantity * allocation.unit_cost
                         for allocation in line.allocations), MONEY_DECIMALS)
    )


def _build_header(
    root: Element,
    issuer: CreditNoteIssuer,
    note: CreditNoteDocument
) -> None:
    '''
        Writes `cabecera`, in the order the XSD declares it.

        Args:
            root (Element): The document root.
            issuer (CreditNoteIssuer): Who issues it.
            note (CreditNoteDocument): The note.
    '''
    header = SubElement(root, 'cabecera')
    _put(header, 'nitEmisor', issuer.nit)
    _put(header, 'razonSocialEmisor', issuer.trade_name)
    _put(header, 'municipio', issuer.municipality)
    _put(header, 'telefono', issuer.phone)
    _put(header, 'numeroNotaCreditoDebito', note.number)
    _put(header, 'cuf', note.cuf)
    _put(header, 'cufd', issuer.cufd)
    _put(header, 'codigoSucursal', issuer.branch)
    _put(header, 'direccion', issuer.address)
    _put(header, 'codigoPuntoVenta', issuer.point_of_sale)
    _put(header, 'fechaEmision', note.issued_at)
    _put(header, 'nombreRazonSocial', note.buyer.name)
    _put(header, 'codigoTipoDocumentoIdentidad', note.buyer.document_type)
    _put(header, 'numeroDocumento', note.buyer.document)
    _put(header, 'complemento', None)
    _put(header, 'codigoCliente', note.buyer.document)
    _put(header, 'numeroFactura', note.invoice.number)
    _put(header, 'numeroAutorizacionCuf', note.invoice.cuf)
    _put(header, 'fechaEmisionFactura', note.invoice.issued_at)
    _put(header, 'montoTotalOriginal', _amount(note.original_total))
    _put(header, 'montoTotalDevuelto', _amount(note.returned_total))
    # The invoices of this product carry no additional discount
    # (`descuentoAdicional` is nil), so there is none to prorate.
    _put(header, 'montoDescuentoCreditoDebito', None)
    _put(header, 'montoEfectivoCreditoDebito', _amount(note.tax_credit))
    _put(header, 'codigoExcepcion', None)
    _put(header, 'leyenda', note.legend)
    _put(header, 'usuario', note.user)
    _put(header, 'codigoDocumentoSector', SECTOR_DOCUMENT_CREDIT_DEBIT)


def _build_details(
    root: Element,
    lines: list[InvoiceLine],
    transaction: int
) -> None:
    '''
        Writes one `detalle` per line, in the order the XSD declares it.

        Args:
            root (Element): The document root.
            lines (list[InvoiceLine]): The lines, with their SIN codes.
            transaction (int): DETAIL_ORIGINAL or DETAIL_RETURNED.
    '''
    for line in lines:
        detail = SubElement(root, 'detalle')
        put_detail_figures(detail, line)
        _put(detail, 'codigoDetalleTransaccion', transaction)


def build_credit_note_xml(
    issuer: CreditNoteIssuer,
    note: CreditNoteDocument
) -> str:
    '''
        Builds the XML of one Nota de Crédito-Débito.

        Args:
            issuer (CreditNoteIssuer): Who issues it, with the CUFD in force.
            note (CreditNoteDocument): The note and its two sets of details.

        Returns:
            str: The XML document.

        Raises:
            InvalidInputError: A product is not homologated with the SIN.
    '''
    require_homologated(note.original + note.returned)
    root = Element(ROOT_ELEMENT)
    _build_header(root, issuer, note)
    _build_details(root, note.original, DETAIL_ORIGINAL)
    _build_details(root, note.returned, DETAIL_RETURNED)

    message = (f'Credit note XML built for invoice {note.invoice.number}: '
               f'{len(note.returned)} returned line(s).')
    logger.info(message)
    return tostring(root, encoding = 'unicode')
