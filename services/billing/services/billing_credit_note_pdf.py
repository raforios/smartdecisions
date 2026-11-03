'''
    The Nota de Crédito-Débito's graphic representation as a PDF: what the
    buyer receives by mail, as they received the invoice.

    It follows the SIN's own format for the note
    (`docs/siat/notaCreditoDebito_formato_grafico.pdf`): the issuer and the
    note, the buyer and the invoice it adjusts, the original sale, what came
    back, and the 13 % of it. It is drawn on the same 80 mm roll as the
    invoice (`billing_invoice_pdf.py`), whose pieces it uses, and every word on
    it is a parameter of `billing_parameters`.
'''
from schemas.billing import BillingSettings, SaleLineOut, SaleNoteOut
from schemas.billing_returns import CreditNoteOut
from schemas.billing_siat import InvoiceState
from services.billing_credit_note_xml import as_sold_line
from services.billing_invoice_pdf import (
    HEADING_SIZE,
    LINE_HEIGHT,
    MEASURING_HEIGHT,
    QR_WIDTH,
    ROLL_MARGIN,
    ROLL_WIDTH,
    SMALL_SIZE,
    TEXTS as INVOICE_TEXTS,
    _money,
    _qr_png,
    _Roll,
    _stamp,
    amount_in_words,
    print_details
)
from services.utils import load_parameters

TEXTS = load_parameters({code: str for code in (
    'BILLING_PDF_NOTE_TITLE', 'BILLING_PDF_NOTE_NUMBER', 'BILLING_PDF_NOTE_INVOICE_NUMBER',
    'BILLING_PDF_NOTE_INVOICE_DATE', 'BILLING_PDF_NOTE_INVOICE_CUF', 'BILLING_PDF_NOTE_ORIGINAL',
    'BILLING_PDF_NOTE_ORIGINAL_TOTAL', 'BILLING_PDF_NOTE_RETURNED',
    'BILLING_PDF_NOTE_RETURNED_TOTAL', 'BILLING_PDF_NOTE_TAX_CREDIT'
)})


def credit_note_pdf(
    sale: SaleNoteOut,
    note: CreditNoteOut,
    settings: BillingSettings
) -> bytes:
    '''
        The PDF of a Nota de Crédito-Débito.

        Args:
            sale (SaleNoteOut): The sale, with the invoice the note adjusts.
            note (CreditNoteOut): The note.
            settings (BillingSettings): The shop that issued it.

        Returns:
            bytes: The PDF.
    '''
    measuring = _Roll(MEASURING_HEIGHT)
    _draw(measuring, sale, note, settings)
    roll = _Roll(measuring.get_y() + ROLL_MARGIN)
    _draw(roll, sale, note, settings)
    return bytes(roll.output())


def _issuer(
    roll: _Roll,
    sale: SaleNoteOut,
    note: CreditNoteOut,
    settings: BillingSettings
) -> None:
    '''
        The title, the shop and the note's number and CUF.
    '''
    invoice = sale.invoice
    roll.line_of(TEXTS['BILLING_PDF_NOTE_TITLE'], 'C', 'B', HEADING_SIZE)
    roll.line_of(settings.trade_name, 'C', 'B', HEADING_SIZE)
    roll.line_of(INVOICE_TEXTS['BILLING_PDF_BRANCH'] % invoice.branch if invoice.branch
                 else INVOICE_TEXTS['BILLING_PDF_HEAD_OFFICE'], 'C')
    roll.line_of(INVOICE_TEXTS['BILLING_PDF_POINT_OF_SALE'] % invoice.point_of_sale, 'C')
    roll.line_of(invoice.address, 'C')
    if settings.phone:
        roll.line_of(INVOICE_TEXTS['BILLING_PDF_PHONE'] % settings.phone, 'C')
    if settings.municipality:
        roll.line_of(settings.municipality, 'C')
    roll.rule()
    roll.line_of(f'{INVOICE_TEXTS["BILLING_PDF_NIT"]} {settings.document}', 'C', 'B')
    roll.line_of(f'{TEXTS["BILLING_PDF_NOTE_NUMBER"]} {note.number}', 'C', 'B')
    roll.line_of(INVOICE_TEXTS['BILLING_PDF_CUF'], 'C', 'B')
    roll.line_of(note.cuf, 'C', size = SMALL_SIZE)


def _buyer(
    roll: _Roll,
    sale: SaleNoteOut,
    note: CreditNoteOut
) -> None:
    '''
        When, to whom, and which invoice the note adjusts.
    '''
    buyer = sale.buyer
    document = buyer.document or ''
    roll.line_of(f'{INVOICE_TEXTS["BILLING_PDF_ISSUED_AT"]} {_stamp(note.issued_at)}')
    roll.line_of(f'{INVOICE_TEXTS["BILLING_PDF_BUYER_NAME"]} '
                 f'{buyer.name or INVOICE_TEXTS["BILLING_PDF_ANONYMOUS"]}')
    roll.line_of(f'{INVOICE_TEXTS["BILLING_PDF_BUYER_DOCUMENT"]} {document}')
    roll.line_of(f'{INVOICE_TEXTS["BILLING_PDF_BUYER_CODE"]} {document}')
    roll.line_of(f'{TEXTS["BILLING_PDF_NOTE_INVOICE_NUMBER"]} {sale.invoice.number}')
    roll.line_of(f'{TEXTS["BILLING_PDF_NOTE_INVOICE_DATE"]} {_stamp(sale.invoice.issued_at)}')
    roll.line_of(TEXTS['BILLING_PDF_NOTE_INVOICE_CUF'])
    roll.line_of(sale.invoice.cuf, size = SMALL_SIZE)
    if note.state == InvoiceState.CANCELLED:
        roll.line_of(INVOICE_TEXTS['BILLING_PDF_CANCELLED'], 'C', 'B', HEADING_SIZE)


def _details(
    roll: _Roll,
    heading: str,
    lines: list[SaleLineOut]
) -> None:
    '''
        One block of details, one per price, as the invoice prints them.
    '''
    roll.line_of(heading, 'C', 'B')
    print_details(roll, lines)


def _draw(
    roll: _Roll,
    sale: SaleNoteOut,
    note: CreditNoteOut,
    settings: BillingSettings
) -> None:
    '''
        Lays the note on the roll, top to bottom, as the SIN's format does.
    '''
    _issuer(roll, sale, note, settings)
    roll.rule()
    _buyer(roll, sale, note)
    roll.rule()
    _details(roll, TEXTS['BILLING_PDF_NOTE_ORIGINAL'], sale.lines)
    roll.pair(TEXTS['BILLING_PDF_NOTE_ORIGINAL_TOTAL'], _money(sale.total), 'B')
    roll.rule()
    _details(roll, TEXTS['BILLING_PDF_NOTE_RETURNED'],
             [as_sold_line(line) for line in note.lines])
    roll.pair(TEXTS['BILLING_PDF_NOTE_RETURNED_TOTAL'], _money(note.amount_returned), 'B')
    roll.line_of(amount_in_words(note.amount_returned))
    roll.pair(TEXTS['BILLING_PDF_NOTE_TAX_CREDIT'], _money(note.tax_credit), 'B')
    roll.rule()
    roll.line_of(INVOICE_TEXTS['BILLING_PDF_LAW'], 'C', size = SMALL_SIZE)
    roll.rule()
    roll.line_of(sale.invoice.legend, 'C', size = SMALL_SIZE)
    roll.rule()
    roll.line_of(INVOICE_TEXTS['BILLING_PDF_ONLINE_LEGEND'], 'C', size = SMALL_SIZE)
    roll.ln(LINE_HEIGHT / 2)
    roll.image(_qr_png(note.qr_url), x = (ROLL_WIDTH - QR_WIDTH) / 2, w = QR_WIDTH)
