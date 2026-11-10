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

from core.logger_config import custom_logger as logger
from schemas.billing import InvoiceLine, SaleLineOut
from schemas.billing_returns import (
    DETAIL_ORIGINAL,
    DETAIL_RETURNED,
    SECTOR_DOCUMENT_CREDIT_DEBIT,
    CreditNoteDocument,
    CreditNoteIssuer,
    CreditNoteLineOut
)
from services.billing import MONEY_DECIMALS
from services.billing_invoice_xml import (
    put_detail_figures,
    put_element,
    require_homologated,
    xml_amount
)

ROOT_ELEMENT = 'notaFiscalComputarizadaCreditoDebito'



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
    put_element(header, 'nitEmisor', issuer.nit)
    put_element(header, 'razonSocialEmisor', issuer.trade_name)
    put_element(header, 'municipio', issuer.municipality)
    put_element(header, 'telefono', issuer.phone)
    put_element(header, 'numeroNotaCreditoDebito', note.number)
    put_element(header, 'cuf', note.cuf)
    put_element(header, 'cufd', issuer.cufd)
    put_element(header, 'codigoSucursal', issuer.branch)
    put_element(header, 'direccion', issuer.address)
    put_element(header, 'codigoPuntoVenta', issuer.point_of_sale)
    put_element(header, 'fechaEmision', note.issued_at)
    put_element(header, 'nombreRazonSocial', note.buyer.name)
    put_element(header, 'codigoTipoDocumentoIdentidad', note.buyer.document_type)
    put_element(header, 'numeroDocumento', note.buyer.document)
    put_element(header, 'complemento', None)
    put_element(header, 'codigoCliente', note.buyer.document)
    put_element(header, 'numeroFactura', note.invoice.number)
    put_element(header, 'numeroAutorizacionCuf', note.invoice.cuf)
    put_element(header, 'fechaEmisionFactura', note.invoice.issued_at)
    put_element(header, 'montoTotalOriginal', xml_amount(note.original_total))
    put_element(header, 'montoTotalDevuelto', xml_amount(note.returned_total))
    # The invoices of this product carry no additional discount
    # (`descuentoAdicional` is nil), so there is none to prorate.
    put_element(header, 'montoDescuentoCreditoDebito', None)
    put_element(header, 'montoEfectivoCreditoDebito', xml_amount(note.tax_credit))
    put_element(header, 'codigoExcepcion', None)
    put_element(header, 'leyenda', note.legend)
    put_element(header, 'usuario', note.user)
    put_element(header, 'codigoDocumentoSector', SECTOR_DOCUMENT_CREDIT_DEBIT)


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
        put_element(detail, 'codigoDetalleTransaccion', transaction)


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
