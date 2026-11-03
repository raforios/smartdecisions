'''
    The mail the buyer receives: the invoice, with its PDF and its XML, and
    the notice when it is cancelled; and the same for a Nota de
    Crédito-Débito, which reaches the buyer by the same means as the invoice
    it adjusts (Rafael, 3-nov-2026). A reverted cancellation is told too: the
    SIN requires every reversal to be notified to the buyer.

    It goes out through Amazon SES from BearSoft's own domain, because
    SmartBilling is BearSoft's service and not the shop's mail (Rafael,
    27-oct-2026). A failure to send never undoes the sale: the invoice is
    valid whether or not the mail arrived, so the failure is logged and the
    sale says it was not sent, to be sent again.

    Bounces and complaints are left to SES's account-level suppression list
    for now (Rafael, 28-oct-2026).
'''
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from schemas.billing import BillingSettings, SaleNoteOut
from schemas.billing_returns import CreditNoteOut
from services.billing_credit_note_pdf import credit_note_pdf
from services.billing_invoice_pdf import invoice_pdf
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger
from services.utils import load_parameters

ENV_VARS = load_and_validate_env_vars({'MAIL_SENDER': str, 'MAIL_REGION': str})

TEXTS = load_parameters({code: str for code in (
    'BILLING_MAIL_SENDER_NAME', 'BILLING_MAIL_INVOICE_SUBJECT', 'BILLING_MAIL_INVOICE_BODY',
    'BILLING_MAIL_CANCEL_SUBJECT', 'BILLING_MAIL_CANCEL_BODY', 'BILLING_MAIL_ANONYMOUS',
    'BILLING_MAIL_NOTE_SUBJECT', 'BILLING_MAIL_NOTE_BODY', 'BILLING_MAIL_NOTE_CANCEL_SUBJECT',
    'BILLING_MAIL_NOTE_CANCEL_BODY', 'BILLING_MAIL_REVERSAL_SUBJECT', 'BILLING_MAIL_REVERSAL_BODY',
    'BILLING_MAIL_KIND_INVOICE', 'BILLING_MAIL_KIND_NOTE'
)})


@dataclass(frozen = True)
class Cancellation:
    '''
        What the cancellation notice says: the reason as the SIN's catalogue
        names it.
    '''
    sale: SaleNoteOut
    reason: str


def send_invoice(
    sale: SaleNoteOut,
    xml: str,
    settings: BillingSettings
) -> bool:
    '''
        Mails an invoice to its buyer.

        Args:
            sale (SaleNoteOut): The invoiced sale; its buyer has an email.
            xml (str): The invoice's XML, the legal document.
            settings (BillingSettings): The shop that issued it.

        Returns:
            bool: Whether SES took the mail.
    '''
    invoice = sale.invoice
    mail = _message(sale, TEXTS['BILLING_MAIL_INVOICE_SUBJECT'] % (invoice.number,
                                                                    settings.trade_name))
    mail.set_content(TEXTS['BILLING_MAIL_INVOICE_BODY'] % (
        _greeting(sale), invoice.number, settings.trade_name, invoice.cuf, invoice.qr_url
    ))
    name = f'factura-{invoice.number}'
    mail.add_attachment(invoice_pdf(sale, settings), maintype = 'application',
                        subtype = 'pdf', filename = f'{name}.pdf')
    mail.add_attachment(xml.encode('utf-8'), maintype = 'application', subtype = 'xml',
                        filename = f'{name}.xml')
    return _send(mail, sale)


def send_cancellation(
    cancellation: Cancellation,
    settings: BillingSettings
) -> bool:
    '''
        Tells the buyer an invoice was cancelled: the norm asks for its CUF,
        its number and the reason.

        Args:
            cancellation (Cancellation): The cancelled sale and why.
            settings (BillingSettings): The shop that cancelled it.

        Returns:
            bool: Whether SES took the mail.
    '''
    sale = cancellation.sale
    invoice = sale.invoice
    mail = _message(sale, TEXTS['BILLING_MAIL_CANCEL_SUBJECT'] % (invoice.number,
                                                                   settings.trade_name))
    mail.set_content(TEXTS['BILLING_MAIL_CANCEL_BODY'] % (
        _greeting(sale), settings.trade_name, invoice.number, invoice.cuf, cancellation.reason
    ))
    return _send(mail, sale)


@dataclass(frozen = True)
class CreditNoteMail:
    '''
        A note and the sale whose invoice it adjusts: the mail names both.
    '''
    sale: SaleNoteOut
    note: CreditNoteOut


def send_credit_note(
    mail_of: CreditNoteMail,
    xml: str,
    settings: BillingSettings
) -> bool:
    '''
        Mails a Nota de Crédito-Débito to the buyer, with its PDF and its XML.

        Args:
            mail_of (CreditNoteMail): The note and its sale; the buyer has an email.
            xml (str): The note's XML, the legal document.
            settings (BillingSettings): The shop that issued it.

        Returns:
            bool: Whether SES took the mail.
    '''
    sale, note = mail_of.sale, mail_of.note
    mail = _message(sale, TEXTS['BILLING_MAIL_NOTE_SUBJECT'] % (note.number,
                                                                 settings.trade_name))
    mail.set_content(TEXTS['BILLING_MAIL_NOTE_BODY'] % (
        _greeting(sale), note.number, settings.trade_name, sale.invoice.number, note.cuf,
        note.qr_url
    ))
    name = f'nota-credito-debito-{note.number}'
    mail.add_attachment(credit_note_pdf(sale, note, settings), maintype = 'application',
                        subtype = 'pdf', filename = f'{name}.pdf')
    mail.add_attachment(xml.encode('utf-8'), maintype = 'application', subtype = 'xml',
                        filename = f'{name}.xml')
    return _send(mail, sale)


def send_credit_note_cancellation(
    mail_of: CreditNoteMail,
    reason: str,
    settings: BillingSettings
) -> bool:
    '''
        Tells the buyer a note was cancelled, with its number, CUF and reason.

        Args:
            mail_of (CreditNoteMail): The cancelled note and its sale.
            reason (str): The reason, as the SIN's catalogue names it.
            settings (BillingSettings): The shop that cancelled it.

        Returns:
            bool: Whether SES took the mail.
    '''
    sale, note = mail_of.sale, mail_of.note
    mail = _message(sale, TEXTS['BILLING_MAIL_NOTE_CANCEL_SUBJECT'] % (note.number,
                                                                        settings.trade_name))
    mail.set_content(TEXTS['BILLING_MAIL_NOTE_CANCEL_BODY'] % (
        _greeting(sale), settings.trade_name, note.number, note.cuf, reason
    ))
    return _send(mail, sale)


@dataclass(frozen = True)
class ReversalMail:
    '''
        The document whose cancellation was reverted, and its sale: an
        invoice, or a note when `credit_note` is True.
    '''
    sale: SaleNoteOut
    number: int
    cuf: str
    credit_note: bool = False


def send_reversal(
    mail_of: ReversalMail,
    settings: BillingSettings
) -> bool:
    '''
        Tells the buyer a cancelled invoice or note is valid again.

        Args:
            mail_of (ReversalMail): The document and its sale.
            settings (BillingSettings): The shop that reverted it.

        Returns:
            bool: Whether SES took the mail.
    '''
    kind = TEXTS['BILLING_MAIL_KIND_NOTE' if mail_of.credit_note else 'BILLING_MAIL_KIND_INVOICE']
    mail = _message(mail_of.sale, TEXTS['BILLING_MAIL_REVERSAL_SUBJECT'] % (
        kind, mail_of.number, settings.trade_name))
    mail.set_content(TEXTS['BILLING_MAIL_REVERSAL_BODY'] % (
        _greeting(mail_of.sale), settings.trade_name, kind, mail_of.number, mail_of.cuf
    ))
    return _send(mail, mail_of.sale)


def _message(
    sale: SaleNoteOut,
    subject: str
) -> EmailMessage:
    '''
        A mail from BearSoft to the sale's buyer.
    '''
    mail = EmailMessage()
    mail['From'] = formataddr((TEXTS['BILLING_MAIL_SENDER_NAME'], ENV_VARS['MAIL_SENDER']))
    mail['To'] = sale.buyer.email
    mail['Subject'] = subject
    return mail


def _greeting(sale: SaleNoteOut) -> str:
    '''
        The buyer's name, or how the mail greets one who gave none.
    '''
    return sale.buyer.name or TEXTS['BILLING_MAIL_ANONYMOUS']


def _send(
    mail: EmailMessage,
    sale: SaleNoteOut
) -> bool:
    '''
        Hands a mail to SES.
    '''
    try:
        boto3.client('sesv2', region_name = ENV_VARS['MAIL_REGION']).send_email(
            FromEmailAddress = ENV_VARS['MAIL_SENDER'],
            Destination = {'ToAddresses': [sale.buyer.email]},
            Content = {'Raw': {'Data': mail.as_bytes()}}
        )
    except (BotoCoreError, ClientError) as error:
        error_msg = f'Mail of sale {sale.number} to {sale.buyer.email} not sent: {error}'
        logger.warning(error_msg)
        return False
    message = f'Mail of sale {sale.number} sent to {sale.buyer.email}.'
    logger.info(message)
    return True
