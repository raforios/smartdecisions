'''
    The invoice's graphic representation as a PDF: the document the buyer
    receives by mail.

    It is the same roll the till prints (`portal/billing/js/pages/TicketPrinter.js`),
    80 mm wide and as long as the invoice, so what the buyer gets by mail and
    on paper read alike. Every word on it is a parameter of
    `billing_parameters` (Rafael, 28-oct-2026): only the spelling of numbers,
    which is a conversion and not a choice, lives here.

    The PDF's core font covers Latin-1 only. The SIN's catalogues write dashes
    and typographic quotes, so text is folded to its nearest Latin-1 form
    before it is drawn; nothing is dropped silently except a character with
    no such form, which becomes '?'.
'''
import io
import unicodedata
from typing import Final

import segno
from fpdf import FPDF

from core.utils import load_parameters
from schemas.billing import BillingSettings, Buyer, SaleLineOut, SaleNoteOut, SaleStatus
from schemas.billing_siat import SaleInvoice
from services.billing_invoicing import QR_ERROR_CORRECTION, invoice_lines

TEXTS = load_parameters({code: str for code in (
    'BILLING_PDF_TITLE', 'BILLING_PDF_SUBTITLE', 'BILLING_PDF_HEAD_OFFICE', 'BILLING_PDF_BRANCH',
    'BILLING_PDF_POINT_OF_SALE', 'BILLING_PDF_PHONE', 'BILLING_PDF_NIT', 'BILLING_PDF_NUMBER',
    'BILLING_PDF_CUF', 'BILLING_PDF_BUYER_NAME', 'BILLING_PDF_BUYER_DOCUMENT',
    'BILLING_PDF_BUYER_CODE', 'BILLING_PDF_ISSUED_AT', 'BILLING_PDF_ANONYMOUS',
    'BILLING_PDF_CANCELLED', 'BILLING_PDF_DETAIL', 'BILLING_PDF_SUBTOTAL', 'BILLING_PDF_DISCOUNT',
    'BILLING_PDF_TOTAL', 'BILLING_PDF_GIFT_CARD', 'BILLING_PDF_TO_PAY', 'BILLING_PDF_TAX_BASE',
    'BILLING_PDF_IN_WORDS', 'BILLING_PDF_LAW', 'BILLING_PDF_ONLINE_LEGEND',
    'BILLING_PDF_OFFLINE_LEGEND'
)})

OFFLINE_EMISSION: Final[int] = 2

# The roll, in millimetres: the 80 mm paper of the till, its printable width,
# and the font sizes of its body, its headings and its small print.
ROLL_WIDTH: Final[float] = 80
ROLL_MARGIN: Final[float] = 4
LINE_HEIGHT: Final[float] = 3.6
BODY_SIZE: Final[float] = 7.5
HEADING_SIZE: Final[float] = 10
SMALL_SIZE: Final[float] = 6
QR_WIDTH: Final[float] = 30
# Tall enough for any invoice: the first pass measures, the second prints.
MEASURING_HEIGHT: Final[float] = 5000
FONT: Final[str] = 'Helvetica'

# Characters the SIN writes that Latin-1 lacks, and what stands for them.
_LATIN1_FOLD: Final[dict[int, str]] = str.maketrans({
    '–': '-', '—': '-', '‘': "'", '’': "'", '“': '"', '”': '"', '…': '...', '•': '-'
})

_UNITS: Final[list[str]] = [
    '', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve',
    'diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis', 'diecisiete',
    'dieciocho', 'diecinueve', 'veinte', 'veintiuno', 'veintidós', 'veintitrés',
    'veinticuatro', 'veinticinco', 'veintiséis', 'veintisiete', 'veintiocho', 'veintinueve'
]
_TENS: Final[list[str]] = ['', '', '', 'treinta', 'cuarenta', 'cincuenta', 'sesenta',
                           'setenta', 'ochenta', 'noventa']
_HUNDREDS: Final[list[str]] = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos',
                               'quinientos', 'seiscientos', 'setecientos', 'ochocientos',
                               'novecientos']
_ONE_HUNDRED: Final[int] = 100
_FIRST_TEN: Final[int] = 30
_THOUSAND: Final[int] = 1000
_MILLION: Final[int] = 1_000_000


def invoice_pdf(
    sale: SaleNoteOut,
    settings: BillingSettings
) -> bytes:
    '''
        The PDF of an invoiced sale.

        Args:
            sale (SaleNoteOut): The sale, with its invoice.
            settings (BillingSettings): The shop that issued it.

        Returns:
            bytes: The PDF.
    '''
    measuring = Roll(MEASURING_HEIGHT)
    _draw(measuring, sale, settings)
    roll = Roll(measuring.get_y() + ROLL_MARGIN)
    _draw(roll, sale, settings)
    return bytes(roll.output())


def amount_in_words(amount: float) -> str:
    '''
        The total as the invoice writes it out: "Son: Trescientos 00/100
        Bolivianos".

        Args:
            amount (float): The total.

        Returns:
            str: The sentence.
    '''
    cents = round(amount * _ONE_HUNDRED)
    words = _in_words(cents // _ONE_HUNDRED)
    return TEXTS['BILLING_PDF_IN_WORDS'] % (words[0].upper() + words[1:],
                                            f'{cents % _ONE_HUNDRED:02d}')


def latin1(text: str) -> str:
    '''
        Text the PDF's core font can draw.

        Args:
            text (str): Any text.

        Returns:
            str: The same text in Latin-1.
    '''
    folded = text.translate(_LATIN1_FOLD)
    return ''.join(char if ord(char) < 256 else _base_letter(char) for char in folded)


class Roll(FPDF):
    '''
        One page of the till's roll.
    '''
    def __init__(
        self,
        height: float
    ) -> None:
        '''
            Args:
                height (float): The roll length, in millimetres.
        '''
        super().__init__(unit = 'mm', format = (ROLL_WIDTH, height))
        self.set_margins(ROLL_MARGIN, ROLL_MARGIN, ROLL_MARGIN)
        self.set_auto_page_break(False)
        self.add_page()

    def line_of(
        self,
        text: str,
        align: str = 'L',
        style: str = '',
        size: float = BODY_SIZE
    ) -> None:
        '''
            A paragraph across the roll, wrapped as needed.

            Args:
                text (str): What is printed.
                align (str): L, C or R.
                style (str): '' or 'B' for bold.
                size (float): Font size, in points.
        '''
        self.set_font(FONT, style, size)
        self.multi_cell(0, LINE_HEIGHT, latin1(text), align = align,
                        new_x = 'LMARGIN', new_y = 'NEXT')

    def pair(
        self,
        label: str,
        amount: str,
        style: str = ''
    ) -> None:
        '''
            A label on the left and its figure on the right, on one line.

            Args:
                label (str): The left-hand text.
                amount (str): The right-hand text.
                style (str): '' or 'B' for bold.
        '''
        self.set_font(FONT, style, BODY_SIZE)
        self.cell(0, LINE_HEIGHT, latin1(label))
        self.set_x(ROLL_MARGIN)
        self.cell(0, LINE_HEIGHT, latin1(amount), align = 'R', new_x = 'LMARGIN', new_y = 'NEXT')

    def rule(self) -> None:
        '''
            The dashed line between the parts of the invoice.
        '''
        y = self.get_y() + LINE_HEIGHT / 2
        self.set_dash_pattern(dash = 1, gap = 1)
        self.line(ROLL_MARGIN, y, ROLL_WIDTH - ROLL_MARGIN, y)
        self.set_dash_pattern()
        self.ln(LINE_HEIGHT)


def print_details(
    roll: Roll,
    lines: list[SaleLineOut]
) -> None:
    '''
        The lines on the roll, one per price, as the SIN reads them: shared by
        the invoice and the Nota de Crédito-Débito.

        Args:
            roll (Roll): The roll.
            lines (list[SaleLineOut]): Sold or returned lines.
    '''
    for line in lines:
        for detail in invoice_lines(line, {}):
            roll.line_of(f'{detail.sku} - {detail.description}')
            discount = f' - {money_text(detail.discount)}' if detail.discount else ''
            roll.pair(f'{money_text(detail.quantity)} x {money_text(detail.unit_price)}{discount}',
                      money_text(detail.subtotal))


def print_issuer(
    roll: Roll,
    invoice: SaleInvoice,
    settings: BillingSettings,
    number_line: str,
    cuf: str
) -> None:
    '''
        The shop, where it issues from, and the document's number and CUF:
        shared by the invoice and the Nota de Crédito-Débito.

        Args:
            roll (Roll): The roll.
            invoice (SaleInvoice): The invoice, for its branch, point of sale
                and address.
            settings (BillingSettings): The shop.
            number_line (str): The document's number, with its label.
            cuf (str): The document's CUF.
    '''
    roll.line_of(settings.trade_name, 'C', 'B', HEADING_SIZE)
    roll.line_of(TEXTS['BILLING_PDF_BRANCH'] % invoice.branch if invoice.branch
                 else TEXTS['BILLING_PDF_HEAD_OFFICE'], 'C')
    roll.line_of(TEXTS['BILLING_PDF_POINT_OF_SALE'] % invoice.point_of_sale, 'C')
    roll.line_of(invoice.address, 'C')
    if settings.phone:
        roll.line_of(TEXTS['BILLING_PDF_PHONE'] % settings.phone, 'C')
    if settings.municipality:
        roll.line_of(settings.municipality, 'C')
    roll.rule()
    roll.line_of(f'{TEXTS["BILLING_PDF_NIT"]} {settings.document}', 'C', 'B')
    roll.line_of(number_line, 'C', 'B')
    roll.line_of(TEXTS['BILLING_PDF_CUF'], 'C', 'B')
    roll.line_of(cuf, 'C', size = SMALL_SIZE)


def print_buyer(
    roll: Roll,
    buyer: Buyer
) -> None:
    '''
        Who the document is made out to: name, document and client code.

        Args:
            roll (Roll): The roll.
            buyer (Buyer): The buyer, anonymous when they gave no name.
    '''
    document = buyer.document or ''
    roll.line_of(f'{TEXTS["BILLING_PDF_BUYER_NAME"]} '
                 f'{buyer.name or TEXTS["BILLING_PDF_ANONYMOUS"]}')
    roll.line_of(f'{TEXTS["BILLING_PDF_BUYER_DOCUMENT"]} {document}')
    roll.line_of(f'{TEXTS["BILLING_PDF_BUYER_CODE"]} {document}')


def print_closing(
    roll: Roll,
    legend: str,
    emission_legend: str,
    qr_url: str
) -> None:
    '''
        What every fiscal document closes with: the law, the SIN's legend,
        how it was issued and the QR.

        Args:
            roll (Roll): The roll.
            legend (str): The SIN's legend the invoice drew.
            emission_legend (str): Online or offline representation.
            qr_url (str): The SIN's link the QR carries.
    '''
    roll.line_of(TEXTS['BILLING_PDF_LAW'], 'C', size = SMALL_SIZE)
    roll.rule()
    roll.line_of(legend, 'C', size = SMALL_SIZE)
    roll.rule()
    roll.line_of(emission_legend, 'C', size = SMALL_SIZE)
    roll.ln(LINE_HEIGHT / 2)
    roll.image(qr_png(qr_url), x = (ROLL_WIDTH - QR_WIDTH) / 2, w = QR_WIDTH)


def _draw(
    roll: Roll,
    sale: SaleNoteOut,
    settings: BillingSettings
) -> None:
    '''
        Lays the invoice on the roll, top to bottom, as the till prints it.

        Args:
            roll (Roll): The roll.
            sale (SaleNoteOut): The sale, with its invoice.
            settings (BillingSettings): The shop that issued it.
    '''
    invoice = sale.invoice
    roll.line_of(TEXTS['BILLING_PDF_TITLE'], 'C', 'B', HEADING_SIZE)
    roll.line_of(TEXTS['BILLING_PDF_SUBTITLE'], 'C')
    print_issuer(roll, invoice, settings,
                 f'{TEXTS["BILLING_PDF_NUMBER"]} {invoice.number}', invoice.cuf)
    roll.rule()
    _buyer(roll, sale)
    roll.rule()
    roll.line_of(TEXTS['BILLING_PDF_DETAIL'], 'C', 'B')
    print_details(roll, sale.lines)
    roll.rule()
    _totals(roll, sale.total)
    roll.rule()
    print_closing(roll, invoice.legend,
                  TEXTS['BILLING_PDF_OFFLINE_LEGEND'] if invoice.emission_type == OFFLINE_EMISSION
                  else TEXTS['BILLING_PDF_ONLINE_LEGEND'], invoice.qr_url)


def _buyer(
    roll: Roll,
    sale: SaleNoteOut
) -> None:
    '''
        Who the invoice is made out to, and when.

        Args:
            roll (Roll): The roll.
            sale (SaleNoteOut): The sale, with its buyer and invoice.
    '''
    print_buyer(roll, sale.buyer)
    roll.line_of(f'{TEXTS["BILLING_PDF_ISSUED_AT"]} {stamp_text(sale.invoice.issued_at)}')
    if sale.status == SaleStatus.CANCELLED:
        roll.line_of(TEXTS['BILLING_PDF_CANCELLED'], 'C', 'B', HEADING_SIZE)


def _totals(
    roll: Roll,
    total: float
) -> None:
    '''
        The totals block, as the till prints it: no gift card and the
        discount already inside each line.

        Args:
            roll (Roll): The roll.
            total (float): The amount charged.
    '''
    for code in ('BILLING_PDF_SUBTOTAL', 'BILLING_PDF_DISCOUNT', 'BILLING_PDF_TOTAL',
                 'BILLING_PDF_GIFT_CARD'):
        roll.pair(TEXTS[code], money_text(0 if code in ('BILLING_PDF_DISCOUNT',
                                                    'BILLING_PDF_GIFT_CARD') else total))
    roll.pair(TEXTS['BILLING_PDF_TO_PAY'], money_text(total), 'B')
    roll.pair(TEXTS['BILLING_PDF_TAX_BASE'], money_text(total))
    roll.line_of(amount_in_words(total))


def qr_png(url: str) -> io.BytesIO:
    '''
        The invoice's QR, as the picture the PDF embeds.

        Args:
            url (str): The SIN's link the QR carries.
    '''
    picture = io.BytesIO()
    segno.make(url, error = QR_ERROR_CORRECTION).save(picture, kind = 'png', scale = 8,
                                                       border = 2)
    picture.seek(0)
    return picture


def money_text(value: float) -> str:
    '''
        An amount as Bolivia writes it: 1.234,50.

        Args:
            value (float): An amount.
    '''
    return f'{value:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')


def stamp_text(iso: str) -> str:
    '''
        The issue moment as the till prints it: 28/10/2026 10:53.

        Args:
            iso (str): An ISO timestamp.
    '''
    date, _, rest = iso.partition('T')
    year, month, day = date.split('-')
    return f'{day}/{month}/{year} {rest[:5]}'


def _base_letter(char: str) -> str:
    '''
        A character outside Latin-1 as its base letter, or '?' without one.

        Args:
            char (str): One character.
    '''
    base = unicodedata.normalize('NFKD', char)[:1]
    return base if base and ord(base) < 256 else '?'


def _below_thousand(number: int) -> str:
    '''
        A number below a thousand, in words.

        Args:
            number (int): A number from 0 to 999.
    '''
    if number == _ONE_HUNDRED:
        return 'cien'
    rest = number % _ONE_HUNDRED
    tail = _UNITS[rest] if rest < _FIRST_TEN else \
        f'{_TENS[rest // 10]}{f" y {_UNITS[rest % 10]}" if rest % 10 else ""}'
    return ' '.join(part for part in (_HUNDREDS[number // _ONE_HUNDRED], tail) if part)


def _in_words(number: int) -> str:
    '''
        A whole number in words, up to the hundreds of millions.

        Args:
            number (int): A whole number.
    '''
    if number == 0:
        return 'cero'
    millions, thousands, rest = (number // _MILLION, number % _MILLION // _THOUSAND,
                                 number % _THOUSAND)
    parts = [
        'un millón' if millions == 1 else f'{_in_words(millions)} millones' if millions else '',
        'mil' if thousands == 1 else f'{_below_thousand(thousands)} mil' if thousands else '',
        _below_thousand(rest)
    ]
    words = ' '.join(part for part in parts if part)
    # "veintiuno mil" and "uno millones" are said "veintiún mil", "un millones".
    for before, after in (('veintiuno mil', 'veintiún mil'), ('veintiuno millones',
                                                             'veintiún millones'),
                          ('uno mil', 'un mil'), ('uno millones', 'un millones')):
        words = words.replace(before, after)
    return words
