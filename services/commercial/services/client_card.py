'''
    The client card (plan phase 7): everything about one client in one place —
    who it is, what and how much it buys, what it owes — and the timeline of
    its invoices and payments, which is the follow-up of its collection.

    Decision 5 (Rafael, 07-oct): what concerns a single client lives in
    Clientes, not scattered across the areas.
'''
import pandas as pd

from schemas.client import (
    ClientListRow,
    ClientMonth,
    ClientProduct,
    ClientReceivable,
    TimelineEntry,
    TimelineKind
)
from services.analytics_utils import (
    AMOUNT, AMOUNT_DECIMALS, CLIENT_ID, CLIENT_NAME, DATE, ORDER, RANKING_SIZE
)
from services.currency import money_row, money_sums
from services.receivables import (
    CREDIT, CREDIT_DAYS, CREDIT_LIMIT, DUE_DATE, PAID_AMOUNT, PAYMENT_DATE, TERMS,
    build_receivables, invoice_frame, resolve_policy
)

_IDENTITY = ('seller', 'city', 'zone', 'channel')


def _first(
    rows: pd.DataFrame,
    column: str
) -> str | None:
    '''
        The first value a column has for the client, when the file has it.

        Args:
            rows (pd.DataFrame): The client's sales rows.
            column (str): The column.

        Returns:
            str | None: The value, or None.
    '''
    if column not in rows.columns:
        return None
    values = rows[column].dropna()
    return str(values.iloc[0]) if not values.empty else None


def build_client_list(sales: pd.DataFrame) -> list[ClientListRow]:
    '''
        Every client of the dataset, the largest first.

        Args:
            sales (pd.DataFrame): Normalized sales rows.

        Returns:
            list[ClientListRow]: One row per client.
    '''
    frame = sales.assign(**{DATE: pd.to_datetime(sales[DATE], errors = 'coerce')})
    grouped = frame.groupby(frame[CLIENT_ID].astype(str)).agg(
        name = (CLIENT_NAME, 'first') if CLIENT_NAME in frame.columns else (AMOUNT, 'size'),
        amount = (AMOUNT, 'sum'),
        purchases = (ORDER, 'nunique') if ORDER in frame.columns else (AMOUNT, 'size'),
        last_purchase = (DATE, 'max')
    ).sort_values('amount', ascending = False)
    return [
        ClientListRow(
            client_id = client_id,
            name = str(row['name']) if CLIENT_NAME in frame.columns else None,
            amount = round(float(row['amount']), AMOUNT_DECIMALS),
            purchases = int(row['purchases']),
            last_purchase = row['last_purchase'].date().isoformat()
            if pd.notna(row['last_purchase']) else None
        )
        for client_id, row in grouped.iterrows()
    ]


def client_rows(
    sales: pd.DataFrame,
    client_id: str
) -> pd.DataFrame:
    '''
        The sales rows of one client.

        Args:
            sales (pd.DataFrame): Normalized sales rows.
            client_id (str): The client.

        Returns:
            pd.DataFrame: Its rows; empty when the client is not in the file.
    '''
    return sales.loc[sales[CLIENT_ID].astype(str) == str(client_id)]


def build_profile(
    rows: pd.DataFrame,
    as_of: pd.Timestamp
) -> dict:
    '''
        Who the client is and how it buys.

        Args:
            rows (pd.DataFrame): The client's sales rows, with month-close factors.
            as_of (pd.Timestamp): The last day with activity in the file.

        Returns:
            dict: Identity, dates, purchases, totals, months and products.
    '''
    dates = pd.to_datetime(rows[DATE], errors = 'coerce')
    orders = int(rows[ORDER].nunique()) if ORDER in rows.columns else int(len(rows))
    total = float(rows[AMOUNT].sum())
    monthly = money_sums(rows, rows[AMOUNT], dates.dt.strftime('%Y-%m'), by_month = True)
    product = 'product_name' if 'product_name' in rows.columns else 'product_id'
    top = rows.groupby(product).agg(amount = (AMOUNT, 'sum'), quantity = ('quantity', 'sum')) \
        .sort_values('amount', ascending = False).head(RANKING_SIZE)
    return {
        'name': _first(rows, CLIENT_NAME),
        **{column: _first(rows, column) for column in _IDENTITY},
        'first_purchase': dates.min().date().isoformat(),
        'last_purchase': dates.max().date().isoformat(),
        'days_since_last': int((as_of - dates.max()).days),
        'purchases': orders,
        'total': round(total, AMOUNT_DECIMALS),
        'average_ticket': round(total / orders, AMOUNT_DECIMALS) if orders else 0.0,
        'months': [ClientMonth(month = str(month), amount = money_row(sums))
                   for month, sums in monthly.iterrows()],
        'products': [ClientProduct(product = str(name), amount = round(float(row['amount']),
                                                                      AMOUNT_DECIMALS),
                                   quantity = float(row['quantity']))
                     for name, row in top.iterrows()]
    }


def _due_dates(
    invoices: pd.DataFrame,
    default_term: int
) -> pd.Series:
    '''
        The due date of each invoice: the stated one, or its date plus its
        term, or the policy's default term.

        Args:
            invoices (pd.DataFrame): One row per invoice.
            default_term (int): Days, from the credit policy.

        Returns:
            pd.Series: One date per invoice.
    '''
    days = pd.to_numeric(invoices[CREDIT_DAYS], errors = 'coerce').fillna(default_term)
    derived = invoices['date'] + pd.to_timedelta(days, unit = 'D')
    return invoices[DUE_DATE].where(invoices[DUE_DATE].notna(), derived)


def build_timeline(
    rows: pd.DataFrame,
    payments: pd.DataFrame | None,
    default_term: int
) -> list[TimelineEntry]:
    '''
        The client's invoices and payments, the latest first: the follow-up
        of its collection.

        Args:
            rows (pd.DataFrame): The client's sales rows.
            payments (pd.DataFrame | None): The client's payment rows.
            default_term (int): Days, from the credit policy.

        Returns:
            list[TimelineEntry]: Invoices with what was paid and what is owed,
                and every payment.
    '''
    invoices = invoice_frame(rows) if TERMS in rows.columns else None
    if invoices is None or invoices.empty:
        return []
    paid = pd.Series(dtype = float)
    entries: list[TimelineEntry] = []
    if payments is not None and not payments.empty:
        paid = payments.groupby(ORDER)[PAID_AMOUNT].sum()
        for _, payment in payments.iterrows():
            day = pd.to_datetime(payment[PAYMENT_DATE], errors = 'coerce')
            entries.append(TimelineEntry(
                date = day.date().isoformat() if pd.notna(day) else '',
                kind = TimelineKind.PAYMENT, order_id = str(payment[ORDER]),
                amount = round(float(payment[PAID_AMOUNT]), AMOUNT_DECIMALS)))
    invoices = invoices.assign(due = _due_dates(invoices, default_term))
    for _, invoice in invoices.iterrows():
        credit = str(invoice['terms']).upper() == CREDIT
        collected = float(paid.get(invoice[ORDER], 0.0)) if credit else float(invoice['amount'])
        entries.append(TimelineEntry(
            date = invoice['date'].date().isoformat(), kind = TimelineKind.INVOICE,
            order_id = str(invoice[ORDER]), amount = round(float(invoice['amount']),
                                                           AMOUNT_DECIMALS),
            terms = str(invoice['terms']),
            due_date = invoice['due'].date().isoformat() if credit and pd.notna(invoice['due'])
            else None,
            paid = round(collected, AMOUNT_DECIMALS),
            balance = round(max(float(invoice['amount']) - collected, 0.0), AMOUNT_DECIMALS)))
    return sorted(entries, key = lambda entry: entry.date, reverse = True)


def build_client_receivable(
    rows: pd.DataFrame,
    payments: pd.DataFrame | None,
    stored_policy: dict | None,
    timeline: list[TimelineEntry]
) -> ClientReceivable:
    '''
        What the client owes, with the same engine as the receivables view.

        Args:
            rows (pd.DataFrame): The client's sales rows.
            payments (pd.DataFrame | None): The client's payment rows.
            stored_policy (dict | None): The account's credit policy.
            timeline (list[TimelineEntry]): From `build_timeline`.

        Returns:
            ClientReceivable: Balance, overdue, open invoices, oldest delay, limit.
    '''
    book = build_receivables(sales = rows, collections = payments, stored_policy = stored_policy)
    if not book.available:
        return ClientReceivable()
    as_of = pd.Timestamp(book.kpis.as_of) if book.kpis.as_of else None
    late = [(as_of - pd.Timestamp(entry.due_date)).days for entry in timeline
            if entry.kind is TimelineKind.INVOICE and entry.balance and entry.due_date
            and as_of is not None]
    limit = pd.to_numeric(rows[CREDIT_LIMIT], errors = 'coerce').max() \
        if CREDIT_LIMIT in rows.columns else None
    return ClientReceivable(
        available = True, balance = book.kpis.receivable_total,
        overdue = book.kpis.overdue_amount, open_invoices = book.kpis.open_invoices,
        oldest_days_past_due = max([0, *late]),
        credit_limit = float(limit) if limit is not None and pd.notna(limit) else None)


def default_term_days(stored_policy: dict | None) -> int:
    '''
        The credit term that applies when an invoice states none.

        Args:
            stored_policy (dict | None): The account's credit policy.

        Returns:
            int: Days.
    '''
    return resolve_policy(stored_policy).default_term_days
