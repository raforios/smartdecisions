'''
    Tests for the cash tills, one per case of
    `docs/cambios/billing-caja/spec.md`.

    The shared fixture opens a till for CASHIER at zero, so these tests open
    their own tills for other users, or close that one first.
'''
from datetime import datetime, time as time_type, timedelta
from zoneinfo import ZoneInfo

import pytest

from schemas.billing import (
    BillingError,
    BillingSettings,
    Buyer,
    PaymentMethod,
    PurchaseLineIn,
    SaleLineIn,
    SaleNoteIn
)
from schemas.billing_cash import (
    CashCloseIn,
    CashOpenIn,
    CashSessionStatus,
    ExpenseIn,
    ExpenseType,
    MovementStatus
)
from services import billing, billing_cash, billing_reports, billing_sales
from services.billing_cash import Viewer
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from tests.test_billing import ( # pylint: disable=unused-import
    CASHIER,
    LATER,
    OTHER_OWNER,
    OWNER,
    _dynamodb,
    _receive,
    _register
)

SELLER = 'vendedor@farmacia.bo'
OTHER_SELLER = 'otro.vendedor@farmacia.bo'
MANAGER = 'gerente@farmacia.bo'
ZONE = ZoneInfo('America/La_Paz')


def _stock(resource):
    '''
        One SKU with a hundred units at Bs 10 each.

        Args:
            resource: The DynamoDB resource.
    '''
    _register(resource)
    _receive(resource, [PurchaseLineIn(sku = 'PARA500', quantity = 100, unit_cost = 6,
                                       sale_price = 10, expiry_date = LATER)])


def _sell_as(
    resource,
    user,
    quantity,
    method = PaymentMethod.EFECTIVO
):
    '''
        Sells units of the stocked SKU as the given user.

        Args:
            resource: The DynamoDB resource.
            user (str): Who sells.
            quantity (float): Units, Bs 10 each.
            method (PaymentMethod): How it was paid.

        Returns:
            SaleNoteOut: The issued note.
    '''
    return billing_sales.issue_sale(resource, OWNER, SaleNoteIn(
        lines = [SaleLineIn(sku = 'PARA500', quantity = quantity)],
        payment_method = method, buyer = Buyer()
    ), user)


def _open(
    resource,
    user = SELLER,
    cash = 200.0
):
    '''
        Opens a till for a user.

        Args:
            resource: The DynamoDB resource.
            user (str): Who opens it.
            cash (float): Counted opening cash.

        Returns:
            CashSessionOut: The open till.
    '''
    return billing_cash.open_session(resource, OWNER, user, CashOpenIn(opening_cash = cash))


def _expense(
    resource,
    session_id,
    amount,
    user = SELLER
):
    '''
        Registers a supplier payment out of a till.

        Args:
            resource: The DynamoDB resource.
            session_id (str): The till.
            amount (float): Cash that leaves.
            user (str): Who pays it.

        Returns:
            CashSessionOut: The till after the expense.
    '''
    return billing_cash.add_expense(resource, OWNER, user, session_id, ExpenseIn(
        expense_type = ExpenseType.SUPPLIER_PAYMENT, amount = amount,
        concept = 'Droguería Demo'
    ))


def _tomorrow(monkeypatch):
    '''
        Moves the service clock one day ahead.

        Args:
            monkeypatch: The pytest fixture.
    '''
    later = datetime.now(ZONE) + timedelta(days = 1)
    monkeypatch.setattr(billing_cash, 'now', lambda: later)


# --- opening ---------------------------------------------------------------

def test_opening_records_the_counted_cash_and_the_time(dynamodb):
    '''Case 1.'''
    till = _open(dynamodb)
    assert till.status is CashSessionStatus.OPEN
    assert till.opening_cash == 200.0
    assert till.expected_cash == 200.0
    assert till.opened_at and not till.expired


def test_a_second_open_till_is_refused(dynamodb):
    '''Case 2.'''
    _open(dynamodb)
    with pytest.raises(RegisterAlreadyExistsError) as error:
        _open(dynamodb)
    assert error.value.detail == BillingError.CASH_SESSION_ALREADY_OPEN.value


def test_a_closed_till_lets_the_user_open_another_the_same_day(dynamodb):
    '''Case 3.'''
    first = _open(dynamodb)
    billing_cash.close_session(dynamodb, OWNER, Viewer(SELLER, False), first.session_id,
                               CashCloseIn(counted_cash = 200))
    second = _open(dynamodb, cash = 50)
    assert second.session_id != first.session_id
    assert second.business_day == first.business_day


# --- sales -----------------------------------------------------------------

def test_no_sale_without_an_open_till_and_stock_untouched(dynamodb):
    '''Case 4.'''
    _stock(dynamodb)
    with pytest.raises(InvalidInputError) as error:
        _sell_as(dynamodb, SELLER, 3)
    assert error.value.detail == BillingError.CASH_SESSION_REQUIRED.value
    assert billing.get_product(dynamodb, OWNER, 'PARA500').available_quantity == 100
    assert not billing_sales.list_sales(dynamodb, OWNER).items


def test_a_sale_belongs_to_the_open_till(dynamodb):
    '''Case 5.'''
    _stock(dynamodb)
    till = _open(dynamodb)
    note = _sell_as(dynamodb, SELLER, 2)
    assert note.cash_session_id == till.session_id


def test_the_summary_splits_every_payment_method(dynamodb):
    '''Case 6: 100 cash, 50 QR, 30 debit, 20 credit.'''
    _stock(dynamodb)
    till = _open(dynamodb)
    for quantity, method in ((10, PaymentMethod.EFECTIVO), (5, PaymentMethod.QR),
                             (3, PaymentMethod.TARJETA_DEBITO),
                             (2, PaymentMethod.TARJETA_CREDITO)):
        _sell_as(dynamodb, SELLER, quantity, method)

    summary = billing_cash.get_session(dynamodb, OWNER, Viewer(SELLER, False),
                                       till.session_id)
    income = {row.payment_method: row.total for row in summary.income}

    assert income == {PaymentMethod.EFECTIVO: 100, PaymentMethod.QR: 50,
                      PaymentMethod.TARJETA_DEBITO: 30, PaymentMethod.TARJETA_CREDITO: 20}
    assert summary.income_total == 200
    assert summary.expected_cash == 300


# --- expenses --------------------------------------------------------------

def test_a_supplier_payment_lowers_the_expected_cash(dynamodb):
    '''Case 7.'''
    till = _open(dynamodb)
    after = _expense(dynamodb, till.session_id, 80)
    assert after.expected_cash == 120
    assert after.expenses_total == 80
    assert after.movements[0].expense_type is ExpenseType.SUPPLIER_PAYMENT


def test_an_expense_cannot_exceed_the_cash_in_the_till(dynamodb):
    '''Case 8.'''
    till = _open(dynamodb)
    with pytest.raises(InvalidInputError) as error:
        _expense(dynamodb, till.session_id, 200.01)
    assert error.value.detail == BillingError.EXPENSE_EXCEEDS_CASH.value


def test_a_cancelled_expense_stops_counting_and_keeps_who(dynamodb):
    '''Case 9.'''
    till = _open(dynamodb)
    movement = _expense(dynamodb, till.session_id, 80).movements[0]
    after = billing_cash.cancel_expense(dynamodb, OWNER, SELLER, till.session_id,
                                        movement.movement_id)
    cancelled = after.movements[0]
    assert cancelled.status is MovementStatus.CANCELLED
    assert cancelled.cancelled_by == SELLER and cancelled.cancelled_at
    assert after.expected_cash == 200
    assert after.expenses_total == 0


def test_a_cancelled_cash_sale_stops_counting(dynamodb):
    '''Case 10.'''
    _stock(dynamodb)
    till = _open(dynamodb)
    note = _sell_as(dynamodb, SELLER, 5)
    billing_sales.cancel_sale(dynamodb, OWNER, note.sale_id, SELLER)
    summary = billing_cash.get_session(dynamodb, OWNER, Viewer(SELLER, False),
                                       till.session_id)
    assert summary.expected_cash == 200
    assert summary.income_total == 0


# --- closing ---------------------------------------------------------------

def test_closing_stores_counted_expected_difference_and_note(dynamodb):
    '''Case 11: 200 + 100 - 80 = 220 expected, 215 counted.'''
    _stock(dynamodb)
    till = _open(dynamodb)
    _sell_as(dynamodb, SELLER, 10)
    _expense(dynamodb, till.session_id, 80)

    closed = billing_cash.close_session(
        dynamodb, OWNER, Viewer(SELLER, False), till.session_id,
        CashCloseIn(counted_cash = 215, note = 'Faltan Bs 5,00. Cambio mal dado.')
    )
    assert closed.status is CashSessionStatus.CLOSED
    assert closed.expected_cash == 220
    assert closed.difference == -5
    assert closed.note == 'Faltan Bs 5,00. Cambio mal dado.'
    assert closed.closed_by == SELLER and closed.closed_at


def test_a_closed_till_takes_no_more_movements(dynamodb):
    '''Case 12, and no sale either.'''
    _stock(dynamodb)
    till = _open(dynamodb)
    billing_cash.close_session(dynamodb, OWNER, Viewer(SELLER, False), till.session_id,
                               CashCloseIn(counted_cash = 200))
    with pytest.raises(InvalidInputError) as error:
        _expense(dynamodb, till.session_id, 10)
    assert error.value.detail == BillingError.CASH_SESSION_CLOSED.value
    with pytest.raises(InvalidInputError):
        _sell_as(dynamodb, SELLER, 1)


# --- who sees what ---------------------------------------------------------

def test_a_seller_cannot_see_another_sellers_till(dynamodb):
    '''Case 13.'''
    till = _open(dynamodb)
    with pytest.raises(RegisterNotFoundError) as error:
        billing_cash.get_session(dynamodb, OWNER, Viewer(OTHER_SELLER, False),
                                 till.session_id)
    assert error.value.detail == BillingError.CASH_SESSION_NOT_FOUND.value


def test_a_manager_lists_every_till_of_the_shop(dynamodb):
    '''Case 14: the fixture's till, plus two.'''
    _open(dynamodb)
    _open(dynamodb, OTHER_SELLER)
    users = {till.user_email for till in billing_cash.list_sessions(
        dynamodb, OWNER, Viewer(MANAGER, True)).items}
    assert users == {CASHIER, SELLER, OTHER_SELLER}

    own = billing_cash.list_sessions(dynamodb, OWNER, Viewer(SELLER, False)).items
    assert {till.user_email for till in own} == {SELLER}


def test_another_shop_sees_no_till(dynamodb):
    '''Case 15.'''
    till = _open(dynamodb)
    with pytest.raises(RegisterNotFoundError):
        billing_cash.get_session(dynamodb, OTHER_OWNER, Viewer(MANAGER, True),
                                 till.session_id)


def test_a_manager_closing_a_foreign_till_must_explain(dynamodb):
    '''Case 17.'''
    till = _open(dynamodb)
    with pytest.raises(InvalidInputError) as error:
        billing_cash.close_session(dynamodb, OWNER, Viewer(MANAGER, True), till.session_id,
                                   CashCloseIn(counted_cash = 200))
    assert error.value.detail == BillingError.CLOSING_NOTE_REQUIRED.value


def test_a_manager_closing_records_who_closed(dynamodb):
    '''Case 18.'''
    till = _open(dynamodb)
    closed = billing_cash.close_session(
        dynamodb, OWNER, Viewer(MANAGER, True), till.session_id,
        CashCloseIn(counted_cash = 200, note = 'El cajero se retiró sin cerrar.')
    )
    assert closed.closed_by == MANAGER
    assert closed.user_email == SELLER


# --- one till per day --------------------------------------------------------

def test_yesterdays_till_takes_no_sales_today(
    dynamodb,
    monkeypatch
):
    '''Case 19.'''
    _stock(dynamodb)
    _open(dynamodb)
    _tomorrow(monkeypatch)
    with pytest.raises(InvalidInputError) as error:
        _sell_as(dynamodb, SELLER, 1)
    assert error.value.detail == BillingError.CASH_SESSION_EXPIRED.value


def test_yesterdays_open_till_blocks_opening_today(
    dynamodb,
    monkeypatch
):
    '''Case 20, and closing it lets the day start.'''
    till = _open(dynamodb)
    _tomorrow(monkeypatch)
    with pytest.raises(InvalidInputError) as error:
        _open(dynamodb)
    assert error.value.detail == BillingError.CASH_SESSION_EXPIRED.value

    billing_cash.close_session(dynamodb, OWNER, Viewer(SELLER, False), till.session_id,
                               CashCloseIn(counted_cash = 200))
    assert _open(dynamodb).status is CashSessionStatus.OPEN


def test_the_alert_lists_open_tills_after_the_hour(
    dynamodb,
    monkeypatch
):
    '''Case 21: from the shop's alert time on, and not before.'''
    settings = billing.get_settings(dynamodb, OWNER)
    billing.save_settings(dynamodb, OWNER, BillingSettings(**{
        **settings.model_dump(exclude = {'next_sale_number', 'next_purchase_number'}),
        'cash_alert_time': time_type(20, 0)
    }))
    _open(dynamodb)
    today = datetime.now(ZONE)

    monkeypatch.setattr(billing_cash, 'now', lambda: today.replace(hour = 20, minute = 30))
    for_manager = billing_cash.cash_alerts(dynamodb, OWNER, Viewer(MANAGER, True))
    for_seller = billing_cash.cash_alerts(dynamodb, OWNER, Viewer(SELLER, False))
    assert {alert.user_email for alert in for_manager.items} == {CASHIER, SELLER}
    assert {alert.user_email for alert in for_seller.items} == {SELLER}

    monkeypatch.setattr(billing_cash, 'now', lambda: today.replace(hour = 19, minute = 59))
    assert not billing_cash.cash_alerts(dynamodb, OWNER, Viewer(MANAGER, True)).items


def test_the_daily_report_splits_methods_and_old_cards(dynamodb):
    '''Case 22: two cash, one QR, one debit and an old "card" note.'''
    _stock(dynamodb)
    for method in (PaymentMethod.EFECTIVO, PaymentMethod.EFECTIVO, PaymentMethod.QR,
                   PaymentMethod.TARJETA_DEBITO, PaymentMethod.TARJETA):
        _sell_as(dynamodb, CASHIER, 1, method)

    report = billing_reports.dashboard(dynamodb, OWNER)
    counts = {row.payment_method: row.count for row in report.sales_by_method}
    assert counts == {PaymentMethod.EFECTIVO: 2, PaymentMethod.QR: 1,
                      PaymentMethod.TARJETA_DEBITO: 1, PaymentMethod.TARJETA: 1}
