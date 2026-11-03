'''
    Tests for reverting the cancellation of an invoice or a note.

    What they protect: reverted, a sale takes its units off the shelf again
    and counts in its till, a note gives its units back and its refund leaves
    the till again; nothing moves when the SIN refuses or the reversal cannot
    be made; a document is reverted once and never cancelled again; a sale
    with returns in force is not cancelled; the buyer is told. The tax office
    is stubbed at the client's seam.
'''
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from controllers import billing_reversals as controllers
from schemas.billing import BillingError, SaleStatus, SiatReceipt
from schemas.billing_cash import CashCloseIn, ExpenseType
from schemas.billing_returns import CreditNoteOut, CreditNoteRef, ReturnError
from schemas.billing_reversals import ReversalError
from schemas.billing_siat import InvoiceState
from services import billing_cash, billing_reversals, billing_sales, utils
from services import billing_siat_client as siat_client
from services.exceptions import InvalidInputError
from tests.test_billing import CASHIER, OWNER, _dynamodb # pylint: disable=unused-import
from tests.test_billing_mail import _ses # pylint: disable=unused-import
from tests.test_billing_returns import ( # pylint: disable=unused-import
    _adjustments,
    _cancel,
    _cancellations,
    _mailed_sale,
    _refunds_in_till,
    _return,
    _sale
)
from tests.test_billing_sale_invoice import ( # pylint: disable=unused-import
    CODES,
    _cancelled_at_sin,
    _sell,
    _sent,
    _stock
)


@pytest.fixture(name = 'reversals')
def _reversals(monkeypatch: pytest.MonkeyPatch) -> list:
    '''
        The SIN reverting cancellations, standing in: it accepts and records
        each one.

        Returns:
            list: Each `DocumentReversal` received.
    '''
    received = []

    def _revert(
        emitter, # pylint: disable=unused-argument
        reversal
    ):
        received.append(reversal)
        return SiatReceipt(accepted = True, state = '907')

    monkeypatch.setattr(billing_reversals, 'current_codes', lambda *_: CODES)
    monkeypatch.setattr(siat_client, 'revert_cancellation', _revert)
    return received


def _cancelled_sale(dynamodb):
    '''Sells two units with an invoice and cancels it at the SIN.'''
    sale = _sell(dynamodb)
    return billing_sales.cancel_sale(dynamodb, OWNER, sale.sale_id, CASHIER, 1)


def test_a_reverted_invoice_is_a_sale_again_and_never_cancelled_again(
    dynamodb,
    sale, # pylint: disable=unused-argument
    cancelled_at_sin, # pylint: disable=unused-argument
    reversals
):
    '''The units leave the shelf again, the till counts it, the SIN got its CUF.'''
    cancelled = _cancelled_sale(dynamodb)
    assert _stock(dynamodb) == 8

    reverted = billing_reversals.revert_sale_cancellation(dynamodb, OWNER, cancelled.sale_id,
                                                          CASHIER)

    assert [(item.cuf, item.credit_note) for item in reversals] == [(cancelled.invoice.cuf,
                                                                     False)]
    assert reverted.status is SaleStatus.ISSUED
    assert (reverted.invoice.state, reverted.invoice.reverted_by) == (InvoiceState.ACCEPTED,
                                                                      CASHIER)
    assert _stock(dynamodb) == 6
    # Both sales count again: the fixture's and the reverted one.
    assert billing_cash.current_session(dynamodb, OWNER, CASHIER).income_total == 400.0
    with pytest.raises(InvalidInputError) as again:
        billing_sales.cancel_sale(dynamodb, OWNER, cancelled.sale_id, CASHIER, 1)
    assert again.value.detail == ReversalError.CANCELLATION_REVERTED.value


def test_a_reversal_the_sin_refuses_leaves_the_sale_cancelled(
    dynamodb,
    sale, # pylint: disable=unused-argument
    cancelled_at_sin, # pylint: disable=unused-argument
    reversals, # pylint: disable=unused-argument
    monkeypatch: pytest.MonkeyPatch
):
    '''Refused, the units taken for it go back to the shelf.'''
    cancelled = _cancelled_sale(dynamodb)
    monkeypatch.setattr(siat_client, 'revert_cancellation', lambda *_: SiatReceipt(
        accepted = False, messages = ['981: REVERSION NO DISPONIBLE']))

    with pytest.raises(InvalidInputError) as refused:
        billing_reversals.revert_sale_cancellation(dynamodb, OWNER, cancelled.sale_id, CASHIER)

    assert refused.value.detail == BillingError.SIAT_REFUSED.value
    assert _stock(dynamodb) == 8
    assert billing_sales.get_sale(dynamodb, OWNER, cancelled.sale_id).status is \
        SaleStatus.CANCELLED


def test_a_sale_is_not_reverted_late_or_once_its_till_closed(
    dynamodb,
    sale, # pylint: disable=unused-argument
    cancelled_at_sin, # pylint: disable=unused-argument
    reversals,
    monkeypatch: pytest.MonkeyPatch
):
    '''Past the ninth of next month, or with its till counted, the SIN is not asked.'''
    cancelled = _cancelled_sale(dynamodb)
    monkeypatch.setattr(billing_reversals, 'get_current_time_gmt', lambda: datetime(2099, 1, 1))
    with pytest.raises(InvalidInputError) as late:
        billing_reversals.revert_sale_cancellation(dynamodb, OWNER, cancelled.sale_id, CASHIER)
    assert late.value.detail == ReversalError.REVERSAL_DEADLINE_PASSED.value

    monkeypatch.setattr(billing_reversals, 'get_current_time_gmt', utils.get_current_time_gmt)
    till = billing_cash.current_session(dynamodb, OWNER, CASHIER)
    billing_cash.close_session(dynamodb, OWNER, billing_cash.Viewer(CASHIER, False),
                               till.session_id, CashCloseIn(counted_cash = till.expected_cash))
    with pytest.raises(InvalidInputError) as closed:
        billing_reversals.revert_sale_cancellation(dynamodb, OWNER, cancelled.sale_id, CASHIER)
    assert closed.value.detail == ReturnError.REFUND_TILL_CLOSED.value
    assert not reversals


def test_a_sale_with_returns_in_force_is_not_cancelled(
    dynamodb,
    sale,
    adjustments # pylint: disable=unused-argument
):
    '''Its lines would give back the unit the note already gave back.'''
    _return(dynamodb, sale.sale_id)

    with pytest.raises(InvalidInputError) as refused:
        billing_sales.cancel_sale(dynamodb, OWNER, sale.sale_id, CASHIER, 1)

    assert refused.value.detail == ReturnError.SALE_HAS_RETURNS.value
    assert _stock(dynamodb) == 9


def test_a_reverted_note_returns_again_and_is_never_cancelled_again(
    dynamodb,
    sale,
    adjustments, # pylint: disable=unused-argument
    cancellations, # pylint: disable=unused-argument
    reversals
):
    '''The unit comes back to the shelf and a new refund leaves the till.'''
    note = _cancel(dynamodb, _return(dynamodb, sale.sale_id))

    reverted = billing_reversals.revert_credit_note_cancellation(
        dynamodb, OWNER, CreditNoteRef(sale_id = sale.sale_id,
                                       credit_note_id = note.credit_note_id), CASHIER)

    assert [(item.cuf, item.credit_note) for item in reversals] == [(note.cuf, True)]
    assert (reverted.state, reverted.reverted_by) == (InvoiceState.ACCEPTED, CASHIER)
    assert _stock(dynamodb) == 9
    assert sorted(movement.status.value for movement in _refunds_in_till(dynamodb)) == \
        ['ACTIVE', 'CANCELLED']
    with pytest.raises(InvalidInputError) as again:
        _cancel(dynamodb, reverted)
    assert again.value.detail == ReversalError.CANCELLATION_REVERTED.value


def test_a_note_whose_units_came_back_again_is_not_reverted(
    dynamodb,
    sale,
    adjustments, # pylint: disable=unused-argument
    cancellations, # pylint: disable=unused-argument
    reversals
):
    '''Both units were returned by a later note: reverting would return three.'''
    note = _cancel(dynamodb, _return(dynamodb, sale.sale_id))
    _return(dynamodb, sale.sale_id, quantity = 2)

    with pytest.raises(InvalidInputError) as refused:
        billing_reversals.revert_credit_note_cancellation(
            dynamodb, OWNER, CreditNoteRef(sale_id = sale.sale_id,
                                           credit_note_id = note.credit_note_id), CASHIER)

    assert refused.value.detail == ReturnError.RETURN_EXCEEDS_SOLD.value
    assert not reversals


def test_the_buyer_is_told_of_the_reversal(
    dynamodb,
    sent, # pylint: disable=unused-argument
    cancelled_at_sin, # pylint: disable=unused-argument
    reversals, # pylint: disable=unused-argument
    ses
):
    '''The SIN requires every reversal to be notified to the buyer.'''
    sale = _mailed_sale(dynamodb)
    billing_sales.cancel_sale(dynamodb, OWNER, sale.sale_id, CASHIER, 1)

    billing_reversals.revert_sale_cancellation(dynamodb, OWNER, sale.sale_id, CASHIER)

    notice = ses.mails[-1]
    assert notice['To'] == 'ana@example.com'
    assert 'factura' in notice['Subject']
    assert sale.invoice.cuf in notice.get_content()


def test_the_reversal_goes_to_the_service_of_its_document(monkeypatch: pytest.MonkeyPatch):
    '''An invoice to the invoicing service, a note to the adjustment one.'''
    calls = []

    def _stub(
        service,
        operation,
        request
    ):
        calls.append((service, operation, request['codigoDocumentoSector'], request['cuf']))

    monkeypatch.setattr(siat_client, 'invoke', _stub)
    emitter = siat_client.Emitter(nit = '1', branch = 0)
    for credit_note in (False, True):
        siat_client.revert_cancellation(emitter, siat_client.DocumentReversal(
            cuis = 'C', cufd = 'D', cuf = 'F', credit_note = credit_note))

    assert calls == [('facturacion', 'reversionAnulacionFactura', 1, 'F'),
                     ('ajuste', 'reversionAnulacionDocumentoAjuste', 24, 'F')]


@pytest.mark.usefixtures('adjustments', 'cancellations', 'cancelled_at_sin', 'reversals')
def test_the_reversal_controllers_return_their_models(
    dynamodb,
    sale
):
    '''Reverting a sale and a note each answer their model.'''
    note = _cancel(dynamodb, _return(dynamodb, sale.sale_id))
    cancelled = _cancelled_sale(dynamodb)
    with patch.object(utils, '_audit_payload', lambda *_: {}), \
            patch.object(utils, 'send_audit_event', AsyncMock()):
        reverted_note = asyncio.run(controllers.revert_credit_note_cancellation_controller(
            dynamodb_resource = dynamodb, owner = OWNER,
            ref = CreditNoteRef(sale_id = sale.sale_id, credit_note_id = note.credit_note_id),
            request = None, current_user = CASHIER
        ))
        reverted_sale = asyncio.run(controllers.revert_sale_cancellation_controller(
            dynamodb_resource = dynamodb, owner = OWNER, sale_id = cancelled.sale_id,
            request = None, current_user = CASHIER
        ))

    assert isinstance(reverted_note, CreditNoteOut) and reverted_note.reverted_at
    assert reverted_sale.status is SaleStatus.ISSUED
    assert reverted_note.refund_movement_id in [
        movement.movement_id for movement in _refunds_in_till(dynamodb)
        if movement.expense_type is ExpenseType.REFUND]
