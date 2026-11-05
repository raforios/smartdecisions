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
    MEASURING_HEIGHT,
    ROLL_MARGIN,
    SMALL_SIZE,
    TEXTS as INVOICE_TEXTS,
    Roll,
    amount_in_words,
    money_text,
    print_buyer,
    print_closing,
    print_details,
    print_issuer,
    stamp_text
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
    measuring = Roll(MEASURING_HEIGHT)
    _draw(measuring, sale, note, settings)
    roll = Roll(measuring.get_y() + ROLL_MARGIN)
    _draw(roll, sale, note, settings)
    return bytes(roll.output())


def _issuer(
    roll: Roll,
    sale: SaleNoteOut,
    note: CreditNoteOut,
    settings: BillingSettings
) -> None:
    '''
        The title, the shop and the note's number and CUF.

        Args:
            roll (Roll): The roll.
            sale (SaleNoteOut): The sale, with the invoice the note adjusts.
            note (CreditNoteOut): The note.
            settings (BillingSettings): The shop that issued it.
    '''
    roll.line_of(TEXTS['BILLING_PDF_NOTE_TITLE'], 'C', 'B', HEADING_SIZE)
    print_issuer(roll, sale.invoice, settings,
                 f'{TEXTS["BILLING_PDF_NOTE_NUMBER"]} {note.number}', note.cuf)


def _buyer(
    roll: Roll,
    sale: SaleNoteOut,
    note: CreditNoteOut
) -> None:
    '''
        When, to whom, and which invoice the note adjusts.

        Args:
            roll (Roll): The roll.
            sale (SaleNoteOut): The sale, with its buyer and invoice.
            note (CreditNoteOut): The note.
    '''
    roll.line_of(f'{INVOICE_TEXTS["BILLING_PDF_ISSUED_AT"]} {stamp_text(note.issued_at)}')
    print_buyer(roll, sale.buyer)
    roll.line_of(f'{TEXTS["BILLING_PDF_NOTE_INVOICE_NUMBER"]} {sale.invoice.number}')
    roll.line_of(f'{TEXTS["BILLING_PDF_NOTE_INVOICE_DATE"]} {stamp_text(sale.invoice.issued_at)}')
    roll.line_of(TEXTS['BILLING_PDF_NOTE_INVOICE_CUF'])
    roll.line_of(sale.invoice.cuf, size = SMALL_SIZE)
    if note.state == InvoiceState.CANCELLED:
        roll.line_of(INVOICE_TEXTS['BILLING_PDF_CANCELLED'], 'C', 'B', HEADING_SIZE)


def _details(
    roll: Roll,
    heading: str,
    lines: list[SaleLineOut]
) -> None:
    '''
        One block of details, one per price, as the invoice prints them.

        Args:
            roll (Roll): The roll.
            heading (str): The block's title.
            lines (list[SaleLineOut]): Sold or returned lines.
    '''
    roll.line_of(heading, 'C', 'B')
    print_details(roll, lines)


def _draw(
    roll: Roll,
    sale: SaleNoteOut,
    note: CreditNoteOut,
    settings: BillingSettings
) -> None:
    '''
        Lays the note on the roll, top to bottom, as the SIN's format does.

        Args:
            roll (Roll): The roll.
            sale (SaleNoteOut): The sale, with the invoice the note adjusts.
            note (CreditNoteOut): The note.
            settings (BillingSettings): The shop that issued it.
    '''
    _issuer(roll, sale, note, settings)
    roll.rule()
    _buyer(roll, sale, note)
    roll.rule()
    _details(roll, TEXTS['BILLING_PDF_NOTE_ORIGINAL'], sale.lines)
    roll.pair(TEXTS['BILLING_PDF_NOTE_ORIGINAL_TOTAL'], money_text(sale.total), 'B')
    roll.rule()
    _details(roll, TEXTS['BILLING_PDF_NOTE_RETURNED'],
             [as_sold_line(line) for line in note.lines])
    roll.pair(TEXTS['BILLING_PDF_NOTE_RETURNED_TOTAL'], money_text(note.amount_returned), 'B')
    roll.line_of(amount_in_words(note.amount_returned))
    roll.pair(TEXTS['BILLING_PDF_NOTE_TAX_CREDIT'], money_text(note.tax_credit), 'B')
    roll.rule()
    # A note is only issued online.
    print_closing(roll, sale.invoice.legend, INVOICE_TEXTS['BILLING_PDF_ONLINE_LEGEND'],
                  note.qr_url)
