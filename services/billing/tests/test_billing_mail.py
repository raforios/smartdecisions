'''
    Tests for the invoice mail and its PDF.

    What they protect: the total is written out as the invoice says it; text
    the PDF's font lacks is folded, not lost; a buyer with an address gets
    the invoice with its PDF and its XML, and the sale remembers when; a
    failed send never undoes the sale and can be sent again; and a cancelled
    invoice is notified with the SIN's name of the reason.
'''
import asyncio
import re
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from unittest.mock import AsyncMock, patch

import pytest
from botocore.exceptions import ClientError

from controllers import billing as controllers
from models.billing import OWNER_KEY, SETTINGS_TABLE, SETTING_SORT_KEY
from schemas.billing import BillingError, BillingSettings, Buyer, SaleNoteOut
from schemas.billing_siat import CatalogEntry, CatalogOut, SiatCatalog
from services import billing, billing_invoice_pdf, billing_mail, billing_sales, utils
from services.exceptions import InvalidInputError, ServiceUnavailableError
from tests.test_billing import CASHIER, OWNER, _dynamodb # pylint: disable=unused-import
from tests.test_billing_sale_invoice import ( # pylint: disable=unused-import
    BUYER,
    _cancelled_at_sin,
    _invoicing_shop,
    _sell,
    _sent
)

MAILED_BUYER = BUYER.model_copy(update = {'email': 'ana@example.com'})


@dataclass
class _Ses:
    '''
        SES, standing in: it records each raw mail, or refuses them all.
    '''
    mails: list = field(default_factory = list)
    refuse: bool = False

    def send_email(
        self,
        **request
    ) -> dict:
        '''
            Takes a mail, as `sesv2.send_email` does.
        '''
        if self.refuse:
            raise ClientError({'Error': {'Code': 'MessageRejected'}}, 'SendEmail')
        self.mails.append(message_from_bytes(request['Content']['Raw']['Data'],
                                             policy = policy.default))
        return {'MessageId': str(len(self.mails))}


@pytest.fixture(name = 'ses')
def _ses(monkeypatch: pytest.MonkeyPatch) -> _Ses:
    '''
        The SES client the mail module creates, replaced.
    '''
    ses = _Ses()
    monkeypatch.setattr(billing_mail.boto3, 'client', lambda *_, **__: ses)
    return ses


@pytest.mark.parametrize(('amount', 'words'), [
    (300, 'Son: Trescientos 00/100 Bolivianos'),
    (100, 'Son: Cien 00/100 Bolivianos'),
    (131.31, 'Son: Ciento treinta y uno 31/100 Bolivianos'),
    (21_000.5, 'Son: Veintiún mil 50/100 Bolivianos'),
    (1_001_001, 'Son: Un millón mil uno 00/100 Bolivianos'),
    (31_000_000, 'Son: Treinta y un millones 00/100 Bolivianos'),
    (0.99, 'Son: Cero 99/100 Bolivianos')
])
def test_the_total_is_written_out_as_the_invoice_says_it(
    amount,
    words
):
    '''
        The same words the till prints.
    '''
    assert billing_invoice_pdf.amount_in_words(amount) == words


def test_text_the_font_lacks_is_folded():
    '''
        The SIN's dashes and quotes become their plain forms; an accent
        stays; a character with no plain form is marked, not dropped.
    '''
    assert billing_invoice_pdf.latin1('EFECTIVO – “QR” Crédito ☃') == \
        'EFECTIVO - "QR" Crédito ?'


def test_the_roll_is_as_long_as_the_invoice(
    dynamodb,
    sent # pylint: disable=unused-argument
):
    '''
        One page, 80 mm wide, that grows with the lines.
    '''
    _invoicing_shop(dynamodb)
    settings = billing.get_settings(dynamodb, OWNER)
    note = _sell(dynamodb)
    longer = note.model_copy(update = {'lines': note.lines * 6})

    short_pdf = billing_invoice_pdf.invoice_pdf(note, settings)
    long_pdf = billing_invoice_pdf.invoice_pdf(longer, settings)

    def height(pdf):
        return float(re.search(rb'/MediaBox \[0 0 [\d.]+ ([\d.]+)\]', pdf).group(1))

    assert short_pdf.startswith(b'%PDF')
    assert short_pdf.count(b'/Type /Page\n') == 1
    assert height(long_pdf) > height(short_pdf)


def test_a_buyer_with_an_address_gets_the_invoice(
    dynamodb,
    sent, # pylint: disable=unused-argument
    ses
):
    '''
        From BearSoft, with the PDF and the very XML the SIN received; the
        sale keeps when it went out.
    '''
    _invoicing_shop(dynamodb)

    note = _sell(dynamodb, MAILED_BUYER)

    mail = ses.mails[0]
    assert mail['To'] == 'ana@example.com'
    assert 'facturas@bearsoft.com.bo' in mail['From']
    assert str(note.invoice.number) in mail['Subject']
    files = {part.get_filename(): part.get_payload(decode = True)
             for part in mail.iter_attachments()}
    number = note.invoice.number
    assert files[f'factura-{number}.pdf'].startswith(b'%PDF')
    stored = billing_sales._read_sale(dynamodb, OWNER, note.sale_id) # pylint: disable=protected-access
    assert files[f'factura-{number}.xml'].decode('utf-8') == stored['invoice_xml']
    assert stored['invoice']['emailed_at']


def test_no_address_no_mail(
    dynamodb,
    sent, # pylint: disable=unused-argument
    ses
):
    '''
        A buyer who gave no address is not written to.
    '''
    _invoicing_shop(dynamodb)

    note = _sell(dynamodb)

    assert not ses.mails
    assert note.invoice.emailed_at is None


def test_a_failed_send_keeps_the_sale_and_can_be_sent_again(
    dynamodb,
    sent, # pylint: disable=unused-argument
    ses
):
    '''
        The invoice is valid without the mail; the shop sends it again once
        SES takes it.
    '''
    _invoicing_shop(dynamodb)
    ses.refuse = True

    note = _sell(dynamodb, MAILED_BUYER)

    assert note.invoice.state.value == 'ACCEPTED'
    assert note.invoice.emailed_at is None
    with pytest.raises(ServiceUnavailableError) as refused:
        billing_sales.resend_invoice(dynamodb, OWNER, note.sale_id)
    assert refused.value.detail == BillingError.MAIL_NOT_SENT.value

    ses.refuse = False
    resent = billing_sales.resend_invoice(dynamodb, OWNER, note.sale_id)
    assert resent.invoice.emailed_at
    assert len(ses.mails) == 1


@pytest.mark.parametrize(('buyer', 'code'), [
    (Buyer(name = 'Ana', document = '4567890', document_type = 1),
     BillingError.BUYER_WITHOUT_EMAIL),
    (None, BillingError.SALE_NOT_INVOICED)
])
def test_a_resend_needs_an_invoice_and_an_address(
    dynamodb,
    sent, # pylint: disable=unused-argument
    ses, # pylint: disable=unused-argument
    buyer,
    code
):
    '''
        Nothing to send, or nowhere to send it.
    '''
    _invoicing_shop(dynamodb)
    if buyer is None:
        billing.save_settings(dynamodb, OWNER, BillingSettings(
            trade_name = 'Consultora Demo', document = '4746720010', invoicing_enabled = False))
    note = _sell(dynamodb, buyer or BUYER)

    with pytest.raises(InvalidInputError) as refused:
        billing_sales.resend_invoice(dynamodb, OWNER, note.sale_id)

    assert refused.value.detail == code.value


def test_a_cancelled_invoice_is_notified_with_its_reason(
    dynamodb,
    sent, # pylint: disable=unused-argument
    cancelled_at_sin, # pylint: disable=unused-argument
    ses
):
    '''
        The notice carries the number, the CUF and the reason as the SIN's
        catalogue names it.
    '''
    _invoicing_shop(dynamodb)
    billing.write_item(dynamodb, SETTINGS_TABLE, {
        OWNER_KEY: OWNER,
        SETTING_SORT_KEY: f'siat#catalog#{SiatCatalog.CANCELLATION_REASONS.name}',
        **CatalogOut(catalog = SiatCatalog.CANCELLATION_REASONS, synced_at = '2026-10-28',
                     entries = [CatalogEntry(code = '1', description = 'FACTURA MAL EMITIDA')]
                     ).model_dump(mode = 'json')
    })
    note = _sell(dynamodb, MAILED_BUYER)

    billing_sales.cancel_sale(dynamodb, OWNER, note.sale_id, CASHIER, 1)

    notice = ses.mails[1]
    body = notice.get_content()
    assert str(note.invoice.number) in notice['Subject']
    assert note.invoice.cuf in body
    assert 'FACTURA MAL EMITIDA' in body


def test_the_resend_controller_returns_the_sale(
    dynamodb,
    sent, # pylint: disable=unused-argument
    ses
):
    '''
        The endpoint's controller hands back the sale, audited.
    '''
    _invoicing_shop(dynamodb)
    note = _sell(dynamodb, MAILED_BUYER)

    with patch.object(utils, '_audit_payload', lambda *_: {}), \
            patch.object(utils, 'send_audit_event', AsyncMock()) as audited:
        resent = asyncio.run(controllers.resend_invoice_controller(
            dynamodb_resource = dynamodb, owner = OWNER, sale_id = note.sale_id,
            request = None, current_user = CASHIER
        ))

    assert isinstance(resent, SaleNoteOut)
    assert len(ses.mails) == 2
    assert audited.called
