'''
    Tests for returning an invoiced sale with a Nota de Crédito-Débito.

    What they protect: the note's XML validates against the SIN's XSD and
    carries both the original sale and what came back; once the SIN accepts,
    the units go back to their batches and the cash leaves the till; nothing
    moves when the SIN refuses or the sale cannot be returned; no more units
    come back than were sold; and the till's refund is written only by a
    return. The tax office is stubbed at the client's seam.
'''
import asyncio
import gzip
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from core import utils
from core.exceptions import InvalidInputError, RegisterNotFoundError
from controllers import billing_returns as controllers
from models.billing import OWNER_KEY, SETTINGS_TABLE, SETTING_SORT_KEY
from schemas.billing import BillingError, Buyer, SiatReceipt
from schemas.billing_cash import CashCloseIn, ExpenseIn, ExpenseType
from schemas.billing_siat import CatalogEntry, CatalogOut, InvoiceState, SiatCatalog
from schemas.billing_returns import (
    CreditNoteCancellation,
    CreditNoteOut,
    CreditNoteRef,
    CreditNotesResponse,
    ReturnError,
    ReturnLineIn,
    SaleReturn,
    SaleReturnIn
)
from services import billing, billing_cash, billing_invoicing, billing_reports, billing_returns
from services import billing_sales
from services import billing_siat_client as siat_client
from services.billing_invoice_xml import validate_against_schema
from tests.test_billing import CASHIER, OWNER, _dynamodb # pylint: disable=unused-import
from tests.test_billing_mail import MAILED_BUYER, _ses # pylint: disable=unused-import
from tests.test_billing_sale_invoice import ( # pylint: disable=unused-import
    CODES,
    _invoicing_shop,
    _sell,
    _sent,
    _stock,
    _stop_invoicing
)

XSD_PATH = str(Path(__file__).resolve().parents[3] / 'docs' / 'siat' /
               'notaComputarizadaCreditoDebito.xsd')


@pytest.fixture(name = 'adjustments')
def _adjustments(monkeypatch: pytest.MonkeyPatch) -> list:
    '''
        The SIN's adjustment service, standing in: it accepts every note and
        records the XML it received.

        Returns:
            list: Each note's XML, as it arrived.
    '''
    received = []

    def _send(
        emitter, # pylint: disable=unused-argument
        submission
    ):
        received.append(gzip.decompress(submission.archive).decode('utf-8'))
        return SiatReceipt(accepted = True, reception_code = 'NCD1', state = '908')

    monkeypatch.setattr(billing_returns, 'current_codes', lambda *_: CODES)
    monkeypatch.setattr(siat_client, 'send_credit_note', _send)
    return received


@pytest.fixture(name = 'cancellations')
def _cancellations(monkeypatch: pytest.MonkeyPatch) -> list:
    '''
        The SIN cancelling notes, standing in: it accepts and records each CUF.

        Returns:
            list: The CUFs it cancelled.
    '''
    received = []

    def _cancel(
        emitter, # pylint: disable=unused-argument
        cancellation
    ):
        received.append(cancellation.cuf)
        return SiatReceipt(accepted = True, state = '905')

    monkeypatch.setattr(siat_client, 'cancel_credit_note', _cancel)
    return received


@pytest.fixture(name = 'sale')
def _sale(
    dynamodb,
    sent # pylint: disable=unused-argument
):
    '''
        An accepted invoice of two units at Bs 100, paid in cash.

        Returns:
            SaleNoteOut: The sale.
    '''
    _invoicing_shop(dynamodb)
    return _sell(dynamodb)


def _return(
    dynamodb,
    sale_id: str,
    quantity: float = 1,
    sku: str = 'CONS1'
):
    '''Returns `quantity` units of `sku` of the sale, as the cashier.'''
    return billing_returns.return_sale(dynamodb, OWNER, SaleReturn(
        sale_id = sale_id, body = SaleReturnIn(lines = [ReturnLineIn(sku = sku,
                                                                     quantity = quantity)])
    ), CASHIER)


def _cancel(
    dynamodb,
    note
):
    '''Cancels a note as the cashier, for reason 1.'''
    return billing_returns.cancel_credit_note(dynamodb, OWNER, CreditNoteCancellation(
        sale_id = note.sale_id, credit_note_id = note.credit_note_id, reason_code = 1), CASHIER)


def _mailed_sale(dynamodb):
    '''
        An invoiced sale to a buyer who gave an address, in a shop that knows
        the SIN's cancellation reasons, as every notice names one.
    '''
    _invoicing_shop(dynamodb)
    billing.write_item(dynamodb, SETTINGS_TABLE, {
        OWNER_KEY: OWNER,
        SETTING_SORT_KEY: f'siat#catalog#{SiatCatalog.CANCELLATION_REASONS.name}',
        **CatalogOut(catalog = SiatCatalog.CANCELLATION_REASONS, synced_at = '2026-11-03',
                     entries = [CatalogEntry(code = '1', description = 'FACTURA MAL EMITIDA')]
                     ).model_dump(mode = 'json')
    })
    return _sell(dynamodb, MAILED_BUYER)


def _refunds_in_till(dynamodb) -> list:
    '''The refunds the cashier's till holds.'''
    till = billing_cash.current_session(dynamodb, OWNER, CASHIER)
    return [movement for movement in till.movements
            if movement.expense_type is ExpenseType.REFUND]


def test_a_partial_return_issues_a_note_the_xsd_accepts(
    dynamodb,
    sale,
    adjustments
):
    '''
        One of two units comes back: the note carries the original sale and
        the returned unit, validates, and undoes that unit.
    '''
    note = _return(dynamodb, sale.sale_id)

    assert validate_against_schema(adjustments[0], XSD_PATH) == []
    assert '<codigoDetalleTransaccion>1</codigoDetalleTransaccion>' in adjustments[0]
    assert '<codigoDetalleTransaccion>2</codigoDetalleTransaccion>' in adjustments[0]
    assert f'<numeroAutorizacionCuf>{sale.invoice.cuf}</numeroAutorizacionCuf>' in adjustments[0]
    assert (note.amount_returned, note.tax_credit, note.number) == (100.0, 13.0, 1)
    assert _stock(dynamodb) == 9
    assert [refund.amount for refund in _refunds_in_till(dynamodb)] == [100.0]
    listed = billing_returns.list_credit_notes(dynamodb, OWNER, sale.sale_id)
    assert [item.credit_note_id for item in listed.items] == [note.credit_note_id]


def test_no_more_units_come_back_than_were_sold(
    dynamodb,
    sale,
    adjustments
):
    '''After one of two units, two more are refused; the second unit is not.'''
    _return(dynamodb, sale.sale_id)

    with pytest.raises(InvalidInputError) as refused:
        _return(dynamodb, sale.sale_id, quantity = 2)
    assert refused.value.detail == ReturnError.RETURN_EXCEEDS_SOLD.value

    with pytest.raises(InvalidInputError) as foreign:
        _return(dynamodb, sale.sale_id, sku = 'OTRO')
    assert foreign.value.detail == ReturnError.SKU_NOT_IN_SALE.value

    with pytest.raises(InvalidInputError) as repeated:
        billing_returns.return_sale(dynamodb, OWNER, SaleReturn(
            sale_id = sale.sale_id, body = SaleReturnIn(lines = [
                ReturnLineIn(sku = 'CONS1', quantity = 1),
                ReturnLineIn(sku = 'CONS1', quantity = 1)])), CASHIER)
    assert repeated.value.detail == ReturnError.RETURN_EXCEEDS_SOLD.value

    second = _return(dynamodb, sale.sale_id)
    assert second.number == 2
    assert _stock(dynamodb) == 10
    assert len(adjustments) == 2


def test_a_note_the_sin_refuses_moves_nothing(
    dynamodb,
    sale,
    monkeypatch: pytest.MonkeyPatch
):
    '''Refused, the units stay sold, the cash stays in the till, no note is kept.'''
    monkeypatch.setattr(billing_returns, 'current_codes', lambda *_: CODES)
    monkeypatch.setattr(siat_client, 'send_credit_note', lambda *_: SiatReceipt(
        accepted = False, messages = ['1037: NOTA RECHAZADA']))

    with pytest.raises(InvalidInputError) as refused:
        _return(dynamodb, sale.sale_id)

    assert refused.value.detail == BillingError.SIAT_REFUSED.value
    assert _stock(dynamodb) == 8
    assert not _refunds_in_till(dynamodb)
    assert billing_returns.list_credit_notes(dynamodb, OWNER, sale.sale_id).total == 0


def test_a_sale_without_an_accepted_invoice_is_not_returned(
    dynamodb,
    sent, # pylint: disable=unused-argument
    adjustments
):
    '''An internal note, a cancelled sale and one past eighteen months, each with its code.'''
    _invoicing_shop(dynamodb)
    _stop_invoicing(dynamodb)
    internal = _sell(dynamodb, buyer = Buyer())
    with pytest.raises(InvalidInputError) as not_invoiced:
        _return(dynamodb, internal.sale_id)
    assert not_invoiced.value.detail == BillingError.SALE_NOT_INVOICED.value

    billing_sales.cancel_sale(dynamodb, OWNER, internal.sale_id, CASHIER)
    with pytest.raises(InvalidInputError) as cancelled:
        _return(dynamodb, internal.sale_id)
    assert cancelled.value.detail == ReturnError.SALE_CANCELLED.value
    assert not adjustments


def test_eighteen_months_after_the_invoice_it_is_too_late(
    dynamodb,
    sale,
    adjustments,
    monkeypatch: pytest.MonkeyPatch
):
    '''The deadline is the same day eighteen months later, the shorter month's last day.'''
    assert billing_returns.return_deadline('2026-08-31T10:00:00.000') == date(2028, 2, 29)
    assert billing_returns.return_deadline('2026-01-15T10:00:00.000') == date(2027, 7, 15)
    monkeypatch.setattr(billing_returns, 'get_current_time_gmt',
                        lambda: datetime(2099, 1, 1))

    with pytest.raises(InvalidInputError) as refused:
        _return(dynamodb, sale.sale_id)

    assert refused.value.detail == ReturnError.RETURN_DEADLINE_PASSED.value
    assert not adjustments


def test_a_combined_payment_is_refunded_by_each_means():
    '''Each means gets back its share; the last takes the rounding.'''
    stored = {'total': 300.0, 'payments': [{'method': 'CASH', 'amount': 100.0},
                                           {'method': 'BANK_TRANSFER', 'amount': 200.0}]}

    refunds = billing_returns._refunds(stored, 100.0) # pylint: disable=protected-access

    assert [(refund.method.value, refund.amount) for refund in refunds] == [
        ('CASH', 33.33), ('BANK_TRANSFER', 66.67)]


def test_a_refund_is_written_only_by_a_return(
    dynamodb,
    sale,
    adjustments # pylint: disable=unused-argument
):
    '''Nobody types a refund into the till, nor cancels the one a return wrote.'''
    session_id = billing_cash.current_session(dynamodb, OWNER, CASHIER).session_id
    with pytest.raises(InvalidInputError) as typed:
        billing_cash.add_expense(dynamodb, OWNER, CASHIER, session_id, ExpenseIn(
            expense_type = ExpenseType.REFUND, amount = 10, concept = 'A-000001'))
    assert typed.value.detail == ReturnError.REFUND_ONLY_BY_RETURN.value

    _return(dynamodb, sale.sale_id)
    refund = _refunds_in_till(dynamodb)[0]
    with pytest.raises(InvalidInputError) as cancelled:
        billing_cash.cancel_expense(dynamodb, OWNER, CASHIER, session_id, refund.movement_id)
    assert cancelled.value.detail == ReturnError.REFUND_ONLY_BY_RETURN.value


def test_the_return_controllers_return_their_models(
    dynamodb,
    sale,
    adjustments, # pylint: disable=unused-argument
    cancellations # pylint: disable=unused-argument
):
    '''Issuing, listing and cancelling a note each answer their model.'''
    with patch.object(utils, '_audit_payload', lambda *_: {}), \
            patch.object(utils, 'send_audit_event', AsyncMock()):
        note = asyncio.run(controllers.return_sale_controller(
            dynamodb_resource = dynamodb, owner = OWNER,
            sale_return = SaleReturn(sale_id = sale.sale_id, body = SaleReturnIn(
                lines = [ReturnLineIn(sku = 'CONS1', quantity = 2)])),
            request = None, current_user = CASHIER
        ))
        listed = asyncio.run(controllers.list_credit_notes_controller(
            dynamodb_resource = dynamodb, owner = OWNER, sale_id = sale.sale_id,
            request = None, current_user = CASHIER
        ))

        qr = asyncio.run(controllers.credit_note_qr_controller(
            dynamodb_resource = dynamodb, owner = OWNER,
            ref = CreditNoteRef(sale_id = sale.sale_id, credit_note_id = note.credit_note_id),
            request = None, current_user = CASHIER
        ))
        cancelled = asyncio.run(controllers.cancel_credit_note_controller(
            dynamodb_resource = dynamodb, owner = OWNER,
            cancellation = CreditNoteCancellation(sale_id = sale.sale_id,
                                                  credit_note_id = note.credit_note_id,
                                                  reason_code = 1),
            request = None, current_user = CASHIER
        ))

    assert isinstance(note, CreditNoteOut) and note.amount_returned == 200.0
    assert isinstance(listed, CreditNotesResponse) and listed.total == 1
    assert qr.svg.startswith('<svg')
    assert cancelled.state is InvoiceState.CANCELLED


def test_cancelling_a_note_undoes_the_return(
    dynamodb,
    sale,
    adjustments, # pylint: disable=unused-argument
    cancellations
):
    '''The unit leaves the shelf again, the refund stops counting, the note says why.'''
    note = _return(dynamodb, sale.sale_id)

    cancelled = _cancel(dynamodb, note)

    assert cancellations == [note.cuf]
    assert (cancelled.state, cancelled.cancellation_reason) == (InvoiceState.CANCELLED, 1)
    assert _stock(dynamodb) == 8
    assert not [movement for movement in _refunds_in_till(dynamodb)
                if movement.status.value == 'ACTIVE']
    with pytest.raises(InvalidInputError) as again:
        _cancel(dynamodb, note)
    assert again.value.detail == ReturnError.CREDIT_NOTE_CANCELLED.value
    # Cancelled, the note no longer counts: both units can come back.
    assert _return(dynamodb, sale.sale_id, quantity = 2).amount_returned == 200.0


def test_a_cancellation_the_sin_refuses_leaves_the_return_as_it_was(
    dynamodb,
    sale,
    adjustments, # pylint: disable=unused-argument
    monkeypatch: pytest.MonkeyPatch
):
    '''Refused, the unit stays back on the shelf and the refund keeps counting.'''
    note = _return(dynamodb, sale.sale_id)
    monkeypatch.setattr(siat_client, 'cancel_credit_note', lambda *_: SiatReceipt(
        accepted = False, messages = ['1050: NO SE PUEDE ANULAR']))

    with pytest.raises(InvalidInputError) as refused:
        _cancel(dynamodb, note)

    assert refused.value.detail == BillingError.SIAT_REFUSED.value
    assert _stock(dynamodb) == 9
    assert [movement.status.value for movement in _refunds_in_till(dynamodb)] == ['ACTIVE']


def test_a_note_is_not_cancelled_once_its_till_closed_or_its_deadline_passed(
    dynamodb,
    sale,
    adjustments, # pylint: disable=unused-argument
    cancellations,
    monkeypatch: pytest.MonkeyPatch
):
    '''A closed till keeps what it counted; past the ninth of next month the SIN says no.'''
    note = _return(dynamodb, sale.sale_id)
    monkeypatch.setattr(billing_returns, 'get_current_time_gmt',
                        lambda: datetime(2099, 1, 1))
    with pytest.raises(InvalidInputError) as late:
        _cancel(dynamodb, note)
    assert late.value.detail == BillingError.CANCELLATION_DEADLINE_PASSED.value

    monkeypatch.undo()
    till = billing_cash.current_session(dynamodb, OWNER, CASHIER)
    billing_cash.close_session(dynamodb, OWNER, billing_cash.Viewer(CASHIER, False),
                               till.session_id, CashCloseIn(counted_cash = till.expected_cash))
    with pytest.raises(InvalidInputError) as closed:
        _cancel(dynamodb, note)
    assert closed.value.detail == ReturnError.REFUND_TILL_CLOSED.value
    assert not cancellations


def test_a_buyer_with_an_address_gets_the_note_as_they_got_the_invoice(
    dynamodb,
    sent, # pylint: disable=unused-argument
    adjustments,
    cancellations, # pylint: disable=unused-argument
    ses
):
    '''
        The note goes with its PDF and the very XML the SIN received, the note
        keeps when; its cancellation is notified with the SIN's reason.
    '''
    sale = _mailed_sale(dynamodb)

    note = _return(dynamodb, sale.sale_id)

    mail = ses.mails[1]
    assert mail['To'] == 'ana@example.com'
    assert str(note.number) in mail['Subject']
    files = {part.get_filename(): part.get_payload(decode = True)
             for part in mail.iter_attachments()}
    assert files['nota-credito-debito-1.pdf'].startswith(b'%PDF')
    assert files['nota-credito-debito-1.xml'].decode('utf-8') == adjustments[0]
    assert note.emailed_at
    assert billing_returns.list_credit_notes(dynamodb, OWNER, sale.sale_id).items[0].emailed_at

    _cancel(dynamodb, note)
    notice = ses.mails[2]
    assert note.cuf in notice.get_content()
    assert 'FACTURA MAL EMITIDA' in notice.get_content()


def test_the_note_prints_the_qr_of_its_own_link(
    dynamodb,
    sale,
    adjustments # pylint: disable=unused-argument
):
    '''Decoded, the QR is the SIN's link of the note, not of the invoice.'''
    note = _return(dynamodb, sale.sale_id)

    qr = billing_returns.credit_note_qr(dynamodb, OWNER, CreditNoteRef(
        sale_id = sale.sale_id, credit_note_id = note.credit_note_id))

    assert note.cuf in note.qr_url and sale.invoice.cuf not in note.qr_url
    assert qr.svg == billing_invoicing.qr_svg(note.qr_url)
    with pytest.raises(RegisterNotFoundError) as unknown:
        billing_returns.credit_note_qr(dynamodb, OWNER, CreditNoteRef(
            sale_id = sale.sale_id, credit_note_id = 'nada'))
    assert unknown.value.detail == ReturnError.CREDIT_NOTE_NOT_FOUND.value


def test_the_dashboard_counts_what_the_buyer_kept(
    dynamodb,
    sale, # pylint: disable=unused-argument
    adjustments # pylint: disable=unused-argument
):
    '''
        One of two units back: the day sold one, by cash, and left its margin.
        Both back: the sale is as if it never happened.
    '''
    before = billing_reports.dashboard(dynamodb, OWNER)
    _return(dynamodb, sale.sale_id)

    after = billing_reports.dashboard(dynamodb, OWNER)

    assert (before.sales_amount, after.sales_amount) == (200.0, 100.0)
    assert after.sales_cost == before.sales_cost / 2
    assert [(row.sku, row.quantity) for row in after.top_products] == [('CONS1', 1)]
    assert [(row.payment_method.value, row.total) for row in after.sales_by_method] == [
        ('CASH', 100.0)]

    _return(dynamodb, sale.sale_id)
    emptied = billing_reports.dashboard(dynamodb, OWNER)
    assert (emptied.sales_count, emptied.sales_amount, emptied.cancelled_count) == (0, 0, 0)
