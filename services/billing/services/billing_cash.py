'''
    Cash tills: opening, expenses, the count and the closing.

    A till is one user's shift for one day. The day matters: reconciliations
    are daily and cashiers are often temporary, so a till left open overnight
    takes nothing more until somebody closes it.

    The expected cash is never stored while the till is open: it is computed
    from the sales and the expenses every time, so a cancelled sale or expense
    cannot leave a stale figure behind. Closing freezes it next to the count.
'''
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from boto3.resources.base import ServiceResource

from models.billing import (
    CASH_MOVEMENT_SORT_KEY,
    CASH_MOVEMENTS_TABLE,
    CASH_SESSION_SORT_KEY,
    CASH_SESSIONS_TABLE,
    OWNER_KEY,
    SALE_SORT_KEY,
    SALES_TABLE,
    CashMovementItem,
    CashSessionItem,
    movement_key
)
from schemas.billing import BillingError, MethodTotal, PaymentMethod, SaleStatus
from schemas.billing_cash import (
    CashAlert,
    CashAlertsResponse,
    CashCloseIn,
    CashOpenIn,
    CashSessionOut,
    CashSessionsResponse,
    CashSessionStatus,
    ExpenseIn,
    ExpenseOut,
    ExpenseTotal,
    MovementStatus
)
from services.billing import (
    SortBounds,
    date_window,
    from_dynamo,
    get_settings,
    new_id,
    read_partition,
    write_item
)
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt

MONEY_DECIMALS = 2


@dataclass(frozen = True)
class Viewer:
    '''
        Who is asking, and whether they see every till of the shop.
    '''
    email: str
    is_manager: bool


@dataclass(frozen = True)
class TillFilter:
    '''
        Which tills a list returns.
    '''
    user_email: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


def now() -> datetime:
    '''
        The current moment in the service timezone. A function of its own so
        the tests can move the clock to the next day.

        Returns:
            datetime: Aware datetime.
    '''
    return get_current_time_gmt()


def _stamp() -> str:
    '''
        The current moment as stored.

        Returns:
            str: ISO 8601 to the second.
    '''
    return now().isoformat(timespec = 'seconds')


def _money(value: float) -> float:
    '''
        An amount rounded as money.

        Args:
            value (float): The amount.

        Returns:
            float: Rounded to two decimals.
    '''
    return round(value, MONEY_DECIMALS)


# --- reading -----------------------------------------------------------------

def _read_session(
    dynamodb_resource: ServiceResource,
    owner: str,
    session_id: str
) -> Optional[Dict[str, Any]]:
    '''
        One till of the shop, or None.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            session_id (str): The till.

        Returns:
            Dict[str, Any] | None: The stored till.
    '''
    response = dynamodb_resource.Table(CASH_SESSIONS_TABLE).get_item(
        Key = {OWNER_KEY: owner, CASH_SESSION_SORT_KEY: session_id}
    )
    return from_dynamo(response.get('Item'))


def _visible_session(
    dynamodb_resource: ServiceResource,
    owner: str,
    viewer: Viewer,
    session_id: str
) -> Dict[str, Any]:
    '''
        A till the viewer may see. Somebody else's, for a seller, answers like
        one that does not exist.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            viewer (Viewer): Who asks.
            session_id (str): The till.

        Returns:
            Dict[str, Any]: The stored till.

        Raises:
            RegisterNotFoundError: No such till for this viewer.
    '''
    stored = _read_session(dynamodb_resource, owner, session_id)
    if stored is None or (not viewer.is_manager and stored['user_email'] != viewer.email):
        raise RegisterNotFoundError(detail = BillingError.CASH_SESSION_NOT_FOUND.value)
    return stored


def _own_open_session(
    dynamodb_resource: ServiceResource,
    owner: str,
    user_email: str,
    session_id: str
) -> Dict[str, Any]:
    '''
        The user's own till, still open and of today: the only one that takes
        movements.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            user_email (str): Who moves cash.
            session_id (str): The till.

        Returns:
            Dict[str, Any]: The stored till.

        Raises:
            RegisterNotFoundError: Not this user's till.
            InvalidInputError: The till is closed, or from an earlier day.
    '''
    stored = _visible_session(dynamodb_resource, owner, Viewer(user_email, False), session_id)
    if stored['status'] != CashSessionStatus.OPEN.value:
        raise InvalidInputError(detail = BillingError.CASH_SESSION_CLOSED.value)
    if _is_expired(stored):
        raise InvalidInputError(detail = BillingError.CASH_SESSION_EXPIRED.value)
    return stored


def _open_sessions(
    dynamodb_resource: ServiceResource,
    owner: str
) -> List[Dict[str, Any]]:
    '''
        Every till of the shop still open.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.

        Returns:
            List[Dict[str, Any]]: Open tills, oldest first.
    '''
    return [row for row in read_partition(dynamodb_resource, CASH_SESSIONS_TABLE, owner)
            if row['status'] == CashSessionStatus.OPEN.value]


def _is_expired(stored: Dict[str, Any]) -> bool:
    '''
        Whether an open till belongs to an earlier day.

        Args:
            stored (Dict[str, Any]): The till.

        Returns:
            bool: True when it should have been closed already.
    '''
    return (stored['status'] == CashSessionStatus.OPEN.value
            and stored['business_day'] < now().date().isoformat())


def _session_sales(
    dynamodb_resource: ServiceResource,
    owner: str,
    stored: Dict[str, Any]
) -> List[Dict[str, Any]]:
    '''
        The issued sales of a till.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            stored (Dict[str, Any]): The till.

        Returns:
            List[Dict[str, Any]]: Sales not cancelled.
    '''
    sales = read_partition(dynamodb_resource, SALES_TABLE, owner,
                           SortBounds(SALE_SORT_KEY, between = {'from': stored['opened_at']}))
    return [sale for sale in sales
            if sale.get('cash_session_id') == stored['session_id']
            and sale['status'] == SaleStatus.ISSUED.value]


def _session_movements(
    dynamodb_resource: ServiceResource,
    owner: str,
    session_id: str
) -> List[Dict[str, Any]]:
    '''
        Every expense of a till, cancelled ones included.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            session_id (str): The till.

        Returns:
            List[Dict[str, Any]]: Movements in the order they were made.
    '''
    return read_partition(dynamodb_resource, CASH_MOVEMENTS_TABLE, owner,
                          SortBounds(CASH_MOVEMENT_SORT_KEY,
                                     begins_with = movement_key(session_id, '')))


def method_totals(sales: List[Any]) -> List[MethodTotal]:
    '''
        What each payment method brought in. Works on stored items and on
        `SaleNoteOut`, so the till and the daily report count the same way.

        Args:
            sales (List[Any]): Issued sales.

        Returns:
            List[MethodTotal]: One row per method used, in the enum's order.
    '''
    totals: Dict[str, List[float]] = {}
    for sale in sales:
        method = sale['payment_method'] if isinstance(sale, dict) \
            else sale.payment_method.value
        total = sale['total'] if isinstance(sale, dict) else sale.total
        totals.setdefault(method, []).append(total)
    return [MethodTotal(payment_method = method, count = len(totals[method.value]),
                        total = _money(sum(totals[method.value])))
            for method in PaymentMethod if method.value in totals]


def _summary(
    dynamodb_resource: ServiceResource,
    owner: str,
    stored: Dict[str, Any]
) -> CashSessionOut:
    '''
        A till and its count.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            stored (Dict[str, Any]): The till.

        Returns:
            CashSessionOut: Income by method, expenses by type and the
                expected cash.
    '''
    income = method_totals(_session_sales(dynamodb_resource, owner, stored))
    movements = _session_movements(dynamodb_resource, owner, stored['session_id'])
    active = [row for row in movements if row['status'] == MovementStatus.ACTIVE.value]

    by_type: Dict[str, List[float]] = {}
    for row in active:
        by_type.setdefault(row['expense_type'], []).append(row['amount'])
    expenses = [ExpenseTotal(expense_type = kind, count = len(amounts),
                             total = _money(sum(amounts)))
                for kind, amounts in by_type.items()]

    cash_in = sum(row.total for row in income
                  if row.payment_method is PaymentMethod.EFECTIVO)
    expenses_total = _money(sum(row['amount'] for row in active))
    expected = stored.get('expected_cash')
    if stored['status'] == CashSessionStatus.OPEN.value or expected is None:
        expected = _money(stored['opening_cash'] + cash_in - expenses_total)

    return CashSessionOut(
        **{key: stored.get(key) for key in (
            'session_id', 'user_email', 'status', 'business_day', 'opened_at',
            'opening_cash', 'closed_at', 'closed_by', 'counted_cash', 'difference', 'note'
        )},
        expired = _is_expired(stored),
        income = income,
        income_total = _money(sum(row.total for row in income)),
        expenses = expenses,
        expenses_total = expenses_total,
        expected_cash = expected,
        # The stored row also carries its keys; the model ignores them.
        movements = [ExpenseOut.model_validate(row) for row in movements]
    )


# --- opening and selling -----------------------------------------------------

def open_session(
    dynamodb_resource: ServiceResource,
    owner: str,
    user_email: str,
    opening: CashOpenIn
) -> CashSessionOut:
    '''
        Opens the user's till with the cash counted in the drawer.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            user_email (str): Who opens it.
            opening (CashOpenIn): The counted cash.

        Returns:
            CashSessionOut: The open till.

        Raises:
            RegisterAlreadyExistsError: The user already has a till open today.
            InvalidInputError: The user left a till open on an earlier day.
    '''
    for stored in _open_sessions(dynamodb_resource, owner):
        if stored['user_email'] != user_email:
            continue
        if _is_expired(stored):
            raise InvalidInputError(detail = BillingError.CASH_SESSION_EXPIRED.value)
        raise RegisterAlreadyExistsError(detail = BillingError.CASH_SESSION_ALREADY_OPEN.value)

    stamp = _stamp()
    item = CashSessionItem(
        owner = owner, session_id = f'{stamp}#{new_id()}', user_email = user_email,
        status = CashSessionStatus.OPEN.value, business_day = stamp[:10],
        opened_at = stamp, opening_cash = _money(opening.opening_cash)
    )
    write_item(dynamodb_resource, CASH_SESSIONS_TABLE, item.__dict__)

    message = f'Till opened by {user_email} for {owner} with {item.opening_cash}.'
    logger.info(message)
    return _summary(dynamodb_resource, owner, item.__dict__)


def current_session(
    dynamodb_resource: ServiceResource,
    owner: str,
    user_email: str
) -> CashSessionOut:
    '''
        The user's open till, expired or not.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            user_email (str): Who asks.

        Returns:
            CashSessionOut: The open till and its count.

        Raises:
            RegisterNotFoundError: The user has no till open.
    '''
    for stored in _open_sessions(dynamodb_resource, owner):
        if stored['user_email'] == user_email:
            return _summary(dynamodb_resource, owner, stored)
    raise RegisterNotFoundError(detail = BillingError.CASH_SESSION_NOT_FOUND.value)


def require_sale_session(
    dynamodb_resource: ServiceResource,
    owner: str,
    user_email: str
) -> str:
    '''
        The till a sale goes into. Called before any stock moves: a refused
        sale must not have touched a shelf.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            user_email (str): Who sells.

        Returns:
            str: The till identifier.

        Raises:
            InvalidInputError: No till open, or only one from an earlier day.
    '''
    for stored in _open_sessions(dynamodb_resource, owner):
        if stored['user_email'] != user_email:
            continue
        if _is_expired(stored):
            raise InvalidInputError(detail = BillingError.CASH_SESSION_EXPIRED.value)
        return stored['session_id']
    raise InvalidInputError(detail = BillingError.CASH_SESSION_REQUIRED.value)


# --- expenses ----------------------------------------------------------------

def add_expense(
    dynamodb_resource: ServiceResource,
    owner: str,
    user_email: str,
    session_id: str,
    expense: ExpenseIn
) -> CashSessionOut:
    '''
        Records cash leaving the user's open till.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            user_email (str): Who takes the cash out.
            session_id (str): The till.
            expense (ExpenseIn): What left and why.

        Returns:
            CashSessionOut: The till after the expense.

        Raises:
            RegisterNotFoundError: Not this user's till.
            InvalidInputError: Closed or expired till, or more than the drawer
                holds.
    '''
    stored = _own_open_session(dynamodb_resource, owner, user_email, session_id)
    if expense.amount > _summary(dynamodb_resource, owner, stored).expected_cash:
        raise InvalidInputError(detail = BillingError.EXPENSE_EXCEEDS_CASH.value)

    movement_id = new_id()
    item = CashMovementItem(
        owner = owner, movement_key = movement_key(session_id, f'{_stamp()}#{movement_id}'),
        session_id = session_id, movement_id = movement_id,
        expense_type = expense.expense_type.value, amount = _money(expense.amount),
        concept = expense.concept, status = MovementStatus.ACTIVE.value,
        created_by = user_email, created_at = _stamp(), purchase_id = expense.purchase_id
    )
    write_item(dynamodb_resource, CASH_MOVEMENTS_TABLE, item.__dict__)

    message = f'Expense of {item.amount} out of till {session_id} by {user_email}.'
    logger.info(message)
    return _summary(dynamodb_resource, owner, stored)


def cancel_expense(
    dynamodb_resource: ServiceResource,
    owner: str,
    user_email: str,
    session_id: str,
    movement_id: str
) -> CashSessionOut:
    '''
        Cancels an expense of the user's open till. It stays on record with
        who and when, and stops counting.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            user_email (str): Who cancels it.
            session_id (str): The till.
            movement_id (str): The expense.

        Returns:
            CashSessionOut: The till after the cancellation.

        Raises:
            RegisterNotFoundError: Not this user's till, or no such expense.
            InvalidInputError: Closed or expired till.
    '''
    stored = _own_open_session(dynamodb_resource, owner, user_email, session_id)
    movement = next((row for row in _session_movements(dynamodb_resource, owner, session_id)
                     if row['movement_id'] == movement_id
                     and row['status'] == MovementStatus.ACTIVE.value), None)
    if movement is None:
        raise RegisterNotFoundError(detail = BillingError.EXPENSE_NOT_FOUND.value)

    movement.update(status = MovementStatus.CANCELLED.value,
                    cancelled_by = user_email, cancelled_at = _stamp())
    write_item(dynamodb_resource, CASH_MOVEMENTS_TABLE, movement)

    message = f'Expense {movement_id} of till {session_id} cancelled by {user_email}.'
    logger.info(message)
    return _summary(dynamodb_resource, owner, stored)


# --- the count and the closing -------------------------------------------------

def get_session(
    dynamodb_resource: ServiceResource,
    owner: str,
    viewer: Viewer,
    session_id: str
) -> CashSessionOut:
    '''
        A till and its count, for its user or a manager.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            viewer (Viewer): Who asks.
            session_id (str): The till.

        Returns:
            CashSessionOut: The till.
    '''
    return _summary(dynamodb_resource, owner,
                    _visible_session(dynamodb_resource, owner, viewer, session_id))


def close_session(
    dynamodb_resource: ServiceResource,
    owner: str,
    viewer: Viewer,
    session_id: str,
    closing: CashCloseIn
) -> CashSessionOut:
    '''
        Closes a till against the cash counted. Its user closes it, or a
        manager with a note saying why.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            viewer (Viewer): Who closes it.
            session_id (str): The till.
            closing (CashCloseIn): Counted cash and the note.

        Returns:
            CashSessionOut: The closed till, with expected and difference.

        Raises:
            RegisterNotFoundError: A till the viewer may not see.
            InvalidInputError: Already closed, or a manager without a note.
    '''
    stored = _visible_session(dynamodb_resource, owner, viewer, session_id)
    if stored['status'] != CashSessionStatus.OPEN.value:
        raise InvalidInputError(detail = BillingError.CASH_SESSION_CLOSED.value)
    note = (closing.note or '').strip() or None
    if stored['user_email'] != viewer.email and note is None:
        raise InvalidInputError(detail = BillingError.CLOSING_NOTE_REQUIRED.value)

    expected = _summary(dynamodb_resource, owner, stored).expected_cash
    stored.update(
        status = CashSessionStatus.CLOSED.value, closed_at = _stamp(),
        closed_by = viewer.email, counted_cash = _money(closing.counted_cash),
        expected_cash = expected, difference = _money(closing.counted_cash - expected),
        note = note
    )
    write_item(dynamodb_resource, CASH_SESSIONS_TABLE, stored)

    message = (f'Till {session_id} of {stored["user_email"]} closed by {viewer.email}: '
               f'expected {expected}, counted {stored["counted_cash"]}.')
    logger.info(message)
    return _summary(dynamodb_resource, owner, stored)


def list_sessions(
    dynamodb_resource: ServiceResource,
    owner: str,
    viewer: Viewer,
    till_filter: Optional[TillFilter] = None
) -> CashSessionsResponse:
    '''
        The tills of the shop, newest first: every user's for a manager, the
        viewer's own for anybody else.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            viewer (Viewer): Who asks.
            till_filter (TillFilter | None): User and days to narrow to.

        Returns:
            CashSessionsResponse: The tills with their counts.
    '''
    till_filter = till_filter or TillFilter()
    stored = read_partition(
        dynamodb_resource, CASH_SESSIONS_TABLE, owner,
        SortBounds(CASH_SESSION_SORT_KEY,
                   between = date_window(till_filter.date_from, till_filter.date_to)),
        descending = True
    )
    user = viewer.email if not viewer.is_manager else till_filter.user_email
    return CashSessionsResponse(items = [
        _summary(dynamodb_resource, owner, row) for row in stored
        if user is None or row['user_email'] == user
    ])


def cash_alerts(
    dynamodb_resource: ServiceResource,
    owner: str,
    viewer: Viewer
) -> CashAlertsResponse:
    '''
        The tills to close now: open past the shop's alert time, or left open
        from an earlier day. Without an alert time only the second kind.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            owner (str): The shop.
            viewer (Viewer): Who asks; a seller sees only their own till.

        Returns:
            CashAlertsResponse: The alert time and the tills to close.
    '''
    alert_time = get_settings(dynamodb_resource, owner).cash_alert_time
    late = alert_time is not None and now().time() >= alert_time
    items = [
        CashAlert(session_id = row['session_id'], user_email = row['user_email'],
                  business_day = date.fromisoformat(row['business_day']),
                  opened_at = row['opened_at'], expired = _is_expired(row))
        for row in _open_sessions(dynamodb_resource, owner)
        if (viewer.is_manager or row['user_email'] == viewer.email)
        and (late or _is_expired(row))
    ]
    return CashAlertsResponse(alert_time = alert_time, items = items)
