'''
    Receivables engine — the credit book and what it is worth.

    Most of the sales the prospects described are on credit (they said around
    70%, with terms from 5 to 120 days), so the question "how are we doing" has
    an answer the sales file alone cannot give: how much of what we billed is
    still out there, how old it is, how much of it is coming back, and what the
    credit costs once financed and provisioned.

    Everything is derived at INVOICE level. In the sales sheet an invoice spans
    one row per product line, so the receivable is the sum of `total_amount`
    per `order_id`, and the payments of the collections contract are imputed
    against that total.

    The reference date is the last day with activity in the dataset, never the
    day the request runs: a file from last quarter would otherwise report its
    whole book as overdue because time passed.

    Policy parameters —aging buckets, expected loss per bucket, the daily
    financial rate, when a client counts as delinquent and the term to assume
    when none is stated— come from the client's own stored policy, and fall back
    to the service defaults FIELD BY FIELD: somebody who only wants to change
    the interest rate should not have to restate the whole policy.
'''
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from schemas.receivables import (
    AgingBucket,
    AgingRow,
    CreditMargin,
    CreditPolicy,
    ReceivablesBlock,
    ReceivablesKpis,
    ReceivablesUnavailable
)
from services.analytics_utils import (
    AMOUNT,
    CLIENT_ID,
    CLIENT_NAME,
    COST,
    DATE,
    ORDER,
    PRICE,
    QUANTITY,
    label_series,
    money,
    ratio
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger
from services.receivables_views import (
    build_collection_curve,
    build_collectors,
    build_debtors,
    build_due_calendar,
    build_priority
)

# Business parameters. They are defaults, not constants: the policy of a client
# overrides them one by one.
_SETTINGS = load_and_validate_env_vars({
    'RECEIVABLES_AGING_BUCKETS': str,
    'RECEIVABLES_LOSS_RATES': str,
    'RECEIVABLES_FINANCIAL_RATE_DAILY': float,
    'RECEIVABLES_DELINQUENT_DAYS': int,
    'RECEIVABLES_DEFAULT_TERM_DAYS': int,
    'RECEIVABLES_DSO_WINDOW_DAYS': int,
    'RECEIVABLES_CEI_WINDOW_DAYS': int,
})


def _numbers(raw: str) -> List[float]:
    '''
        Reads a dash-separated list of numbers from configuration.

        The separator is a dash and not a comma because the deploy passes the
        whole `.env` to `--environment Variables={...}`, where a comma starts a
        new variable.

        Args:
            raw (str): Value as configured, e.g. '15-30-60-90-120'.

        Returns:
            List[float]: The numbers, in the order given.
    '''
    return [float(found) for found in raw.replace('-', ' ').split()]


_DEFAULT_BUCKETS: Tuple[int, ...] = tuple(
    int(value) for value in _numbers(_SETTINGS['RECEIVABLES_AGING_BUCKETS'])
)
_DEFAULT_LOSS_RATES: Tuple[float, ...] = tuple(
    _numbers(_SETTINGS['RECEIVABLES_LOSS_RATES'])
)
_DEFAULT_RATE = _SETTINGS['RECEIVABLES_FINANCIAL_RATE_DAILY']
_DEFAULT_DELINQUENT_DAYS = _SETTINGS['RECEIVABLES_DELINQUENT_DAYS']
_DEFAULT_TERM_DAYS = _SETTINGS['RECEIVABLES_DEFAULT_TERM_DAYS']
_DSO_WINDOW = _SETTINGS['RECEIVABLES_DSO_WINDOW_DAYS']
_CEI_WINDOW = _SETTINGS['RECEIVABLES_CEI_WINDOW_DAYS']

# Contract columns this engine reads on top of the sales ones.
TERMS = 'payment_terms'
CREDIT_DAYS = 'credit_days'
DUE_DATE = 'due_date'
COLLECTOR = 'collector'
CREDIT_LIMIT = 'credit_limit'
PAID_AMOUNT = 'paid_amount'
PAYMENT_DATE = 'payment_date'

CREDIT = 'CREDITO'
CASH = 'CONTADO'

# The aging scale, in the order the buckets are reported. CURRENT is not an
# overdue bucket: it is what has not fallen due yet.
_BUCKET_ORDER: Tuple[AgingBucket, ...] = (
    AgingBucket.CURRENT,
    AgingBucket.DAYS_1_15,
    AgingBucket.DAYS_16_30,
    AgingBucket.DAYS_31_60,
    AgingBucket.DAYS_61_90,
    AgingBucket.DAYS_91_120,
    AgingBucket.DAYS_OVER_120,
)
_DAYS_IN_YEAR = 365
_PERCENT = 100.0


@dataclass(frozen = True)
class Policy:
    '''
        The parameters one book is read with, already resolved.

        A frozen dataclass and not a dict so every consumer reads
        `policy.loss_rates` instead of guessing a key, and so an unknown
        parameter fails at construction instead of silently defaulting to zero.
    '''
    buckets: Tuple[int, ...] = _DEFAULT_BUCKETS
    loss_rates: Tuple[float, ...] = _DEFAULT_LOSS_RATES
    financial_rate_daily: float = _DEFAULT_RATE
    delinquent_days: int = _DEFAULT_DELINQUENT_DAYS
    default_term_days: int = _DEFAULT_TERM_DAYS
    source_code: str = 'DEFAULT'

    def as_dto(self) -> CreditPolicy:
        '''
            Returns the policy as it travels in the response.

            Returns:
                CreditPolicy: The parameters that produced the figures.
        '''
        return CreditPolicy(
            source_code = self.source_code,
            aging_buckets = list(self.buckets),
            loss_rates = list(self.loss_rates),
            financial_rate_daily = self.financial_rate_daily,
            delinquent_days = self.delinquent_days,
            default_term_days = self.default_term_days
        )


def resolve_policy(stored: Optional[Dict[str, Any]]) -> Policy:
    '''
        Builds the policy to apply, falling back field by field.

        Args:
            stored (Dict[str, Any] | None): The client's stored policy, if any.

        Returns:
            Policy: The resolved parameters, tagged with where they came from.
    '''
    if not stored:
        return Policy()

    given = {key: value for key, value in stored.items() if value not in (None, [], '')}
    buckets = given.get('aging_buckets')
    rates = given.get('loss_rates')

    return Policy(
        buckets = tuple(int(value) for value in buckets) if buckets else _DEFAULT_BUCKETS,
        loss_rates = tuple(float(value) for value in rates) if rates else _DEFAULT_LOSS_RATES,
        financial_rate_daily = float(
            given.get('financial_rate_daily', _DEFAULT_RATE)
        ),
        delinquent_days = int(given.get('delinquent_days', _DEFAULT_DELINQUENT_DAYS)),
        default_term_days = int(given.get('default_term_days', _DEFAULT_TERM_DAYS)),
        source_code = 'CLIENT'
    )


def _bucket_of(days_past_due: float, buckets: Tuple[int, ...]) -> AgingBucket:
    '''
        Places a balance on the aging scale.

        Args:
            days_past_due (float): Days beyond the due date; 0 or less is not due.
            buckets (Tuple[int, ...]): Upper bound of each overdue bucket.

        Returns:
            AgingBucket: The bucket code.
    '''
    if days_past_due <= 0:
        return AgingBucket.CURRENT
    for position, limit in enumerate(buckets):
        if days_past_due <= limit:
            return _BUCKET_ORDER[position + 1]
    return _BUCKET_ORDER[min(len(buckets) + 1, len(_BUCKET_ORDER) - 1)]


def _loss_rate_of(bucket: AgingBucket, policy: Policy) -> float:
    '''
        The expected loss of a bucket under a policy.

        Args:
            bucket (AgingBucket): Bucket code.
            policy (Policy): Resolved parameters.

        Returns:
            float: Expected loss, 0 to 1. The last configured rate covers every
                bucket beyond the ones configured, so a short policy never
                silently provisions at zero.
    '''
    position = _BUCKET_ORDER.index(bucket)
    if position < len(policy.loss_rates):
        return float(policy.loss_rates[position])
    return float(policy.loss_rates[-1]) if policy.loss_rates else 0.0


def _invoice_frame(sales: pd.DataFrame) -> Optional[pd.DataFrame]:
    '''
        Collapses the sales rows into one row per invoice.

        Args:
            sales (pd.DataFrame): Normalized sales rows.

        Returns:
            pd.DataFrame | None: One row per invoice with its client, collector,
                terms and amount, or None when the frame cannot support it.
    '''
    if ORDER not in sales.columns or AMOUNT not in sales.columns:
        return None

    labels = label_series(sales, CLIENT_ID, CLIENT_NAME)
    frame = sales.assign(_client = labels.values if labels is not None else '')
    if COLLECTOR not in frame.columns:
        frame[COLLECTOR] = pd.NA
    if CREDIT_LIMIT not in frame.columns:
        frame[CREDIT_LIMIT] = pd.NA
    if CREDIT_DAYS not in frame.columns:
        frame[CREDIT_DAYS] = pd.NA
    if DUE_DATE not in frame.columns:
        frame[DUE_DATE] = pd.NaT

    aggregated = frame.groupby(ORDER, as_index = False).agg(
        client = ('_client', 'first'),
        collector = (COLLECTOR, 'first'),
        date = (DATE, 'min'),
        amount = (AMOUNT, 'sum'),
        terms = (TERMS, 'first'),
        credit_days = (CREDIT_DAYS, 'first'),
        due_date = (DUE_DATE, 'min'),
        credit_limit = (CREDIT_LIMIT, 'max')
    )
    aggregated['date'] = pd.to_datetime(aggregated['date'], errors = 'coerce')
    aggregated['due_date'] = pd.to_datetime(aggregated['due_date'], errors = 'coerce')
    return aggregated


def _with_terms(invoices: pd.DataFrame, policy: Policy) -> pd.DataFrame:
    '''
        Fills the due date of every credit invoice.

        A stated due date wins over the term, because that is the date the two
        parties agreed on; when neither is there the policy's default term
        applies, and that is a configured decision and not a guess made here.

        Args:
            invoices (pd.DataFrame): One row per invoice.
            policy (Policy): Resolved parameters.

        Returns:
            pd.DataFrame: The same frame with `due_date` resolved.
    '''
    frame = invoices.copy()
    days = pd.to_numeric(frame['credit_days'], errors = 'coerce')
    is_credit = frame['terms'].astype(str).str.upper() == CREDIT
    fallback = days.where(days.notna(), policy.default_term_days)

    derived = frame['date'] + pd.to_timedelta(fallback.fillna(0), unit = 'D')
    frame['due_date'] = frame['due_date'].where(frame['due_date'].notna(), derived)
    frame['due_date'] = frame['due_date'].where(is_credit, frame['date'])
    frame['is_credit'] = is_credit
    frame['credit_days'] = fallback.where(is_credit, 0)
    return frame


def _payments_by_invoice(collections: Optional[pd.DataFrame]) -> pd.DataFrame:
    '''
        Totals the payments of each invoice and finds its last payment date.

        Args:
            collections (pd.DataFrame | None): Normalized payment rows.

        Returns:
            pd.DataFrame: Indexed by invoice, with `paid` and `last_payment`.
    '''
    # With declared dtypes: an untyped empty frame leaves `last_payment` as
    # float, and subtracting it from the due date raises on the join.
    empty = pd.DataFrame({
        'paid': pd.Series(dtype = 'float64'),
        'last_payment': pd.Series(dtype = 'datetime64[ns]')
    })
    if collections is None or collections.empty:
        return empty
    if ORDER not in collections.columns or PAID_AMOUNT not in collections.columns:
        return empty

    frame = collections.copy()
    if PAYMENT_DATE in frame.columns:
        frame[PAYMENT_DATE] = pd.to_datetime(frame[PAYMENT_DATE], errors = 'coerce')
    else:
        frame[PAYMENT_DATE] = pd.NaT

    return frame.groupby(ORDER).agg(
        paid = (PAID_AMOUNT, 'sum'),
        last_payment = (PAYMENT_DATE, 'max')
    )


def _book(invoices: pd.DataFrame, payments: pd.DataFrame,
          as_of: pd.Timestamp, policy: Policy) -> pd.DataFrame:
    '''
        Builds the credit book: every invoice with its balance and its age.

        Args:
            invoices (pd.DataFrame): Credit invoices with their due date.
            payments (pd.DataFrame): Payments totalled per invoice.
            as_of (pd.Timestamp): Reference date.
            policy (Policy): Resolved parameters.

        Returns:
            pd.DataFrame: The book, one row per credit invoice.
    '''
    book = invoices.loc[invoices['is_credit']].copy()
    book = book.join(payments, on = ORDER)
    book['paid'] = pd.to_numeric(book['paid'], errors = 'coerce').fillna(0.0)
    book['last_payment'] = pd.to_datetime(book['last_payment'], errors = 'coerce')
    book['balance'] = (book['amount'] - book['paid']).round(2)
    book['is_open'] = book['balance'] > 0.01

    # Days past due only count for what is still open. An invoice collected
    # late is no longer overdue debt: it is payment history.
    days_past_due = (as_of - book['due_date']).dt.days
    book['days_past_due'] = days_past_due.where(book['is_open'], 0).fillna(0).clip(lower = 0)
    book['days_outstanding'] = (as_of - book['date']).dt.days.clip(lower = 0)
    # The bucket travels as plain text. A column of str-Enum members is stored
    # as strings by pandas 3, and under its Python string storage —the Lambda
    # has no pyarrow— comparing that column with an Enum member is False on
    # every row: the aging came back empty in production while every test
    # passed on a machine with pyarrow.
    buckets = [_bucket_of(float(days), policy.buckets) for days in book['days_past_due']]
    book['bucket'] = [bucket.value for bucket in buckets]
    book['loss_rate'] = [_loss_rate_of(bucket, policy) for bucket in buckets]
    book['provision'] = (book['balance'].clip(lower = 0) * book['loss_rate']).round(2)

    # Behaviour of what was already collected: how many days late it was paid
    # and at what real term. It is what says whether a 30-day client pays at 47.
    settled = ~book['is_open'] & book['last_payment'].notna()
    book['days_late'] = (book['last_payment'] - book['due_date']).dt.days.where(settled)
    book['real_term'] = (book['last_payment'] - book['date']).dt.days.where(settled)
    return book


def _aging(book: pd.DataFrame, policy: Policy) -> List[AgingRow]:
    '''
        The aging of the open book, bucket by bucket.

        Args:
            book (pd.DataFrame): The credit book.
            policy (Policy): Resolved parameters.

        Returns:
            List[AgingRow]: One row per bucket that holds something.
    '''
    open_book = book.loc[book['is_open']]
    total = float(open_book['balance'].sum())
    rows: List[AgingRow] = []

    for bucket in _BUCKET_ORDER:
        held = open_book.loc[open_book['bucket'] == bucket.value]
        if held.empty:
            continue
        amount = float(held['balance'].sum())
        rows.append(AgingRow(
            bucket_code = bucket,
            invoices = int(len(held)),
            clients = int(held['client'].nunique()),
            amount = money(amount),
            share = round(ratio(amount, total) * _PERCENT, 1),
            expected_loss_rate = _loss_rate_of(bucket, policy),
            provision = money(float(held['provision'].sum()))
        ))
    return rows


def _dso(book: pd.DataFrame, as_of: pd.Timestamp, receivable: float) -> Optional[float]:
    '''
        Days sales outstanding over the configured window.

        Args:
            book (pd.DataFrame): The credit book.
            as_of (pd.Timestamp): Reference date.
            receivable (float): Open balance today.

        Returns:
            float | None: DSO in days, or None when there were no credit sales
                in the window — with no denominator the ratio would be a
                division by zero dressed up as a number.
    '''
    window_start = as_of - pd.Timedelta(days = _DSO_WINDOW)
    recent = book.loc[book['date'] > window_start, 'amount'].sum()
    if recent <= 0:
        return None
    return round(receivable / float(recent) * _DSO_WINDOW, 1)


def _balance_at(book: pd.DataFrame, collections: Optional[pd.DataFrame],
                moment: pd.Timestamp) -> float:
    '''
        The open balance of the book at a past date.

        It has to be rebuilt from the payment DATES and not from the totals:
        subtracting everything an invoice ever paid would credit the opening
        balance with money collected after that date, which is exactly the
        money the index is trying to measure.

        Args:
            book (pd.DataFrame): The credit book.
            collections (pd.DataFrame | None): Normalized payment rows.
            moment (pd.Timestamp): The date to rebuild the balance at.

        Returns:
            float: Open balance at that date.
    '''
    issued = float(book.loc[book['date'] <= moment, 'amount'].sum())
    if collections is None or collections.empty:
        return issued
    if PAYMENT_DATE not in collections.columns or PAID_AMOUNT not in collections.columns:
        return issued

    dates = pd.to_datetime(collections[PAYMENT_DATE], errors = 'coerce')
    paid = float(collections.loc[dates <= moment, PAID_AMOUNT].sum())
    return issued - paid


def _collection_effectiveness(book: pd.DataFrame, collections: Optional[pd.DataFrame],
                              as_of: pd.Timestamp) -> Optional[float]:
    '''
        Collection Effectiveness Index over the configured window.

        CEI measures the collections team and not the clients: of everything
        that was collectable in the period, how much was actually collected.
        100 means everything that could be collected, was.

        Args:
            book (pd.DataFrame): The credit book.
            collections (pd.DataFrame | None): Normalized payment rows, needed
                to rebuild the opening balance at the right date.
            as_of (pd.Timestamp): Reference date.

        Returns:
            float | None: The index, 0 to 100, or None when the window has no
                movement to measure.
    '''
    start = as_of - pd.Timedelta(days = _CEI_WINDOW)
    opening = _balance_at(book, collections, start)
    credit_sales = float(book.loc[book['date'] > start, 'amount'].sum())
    ending_total = float(book.loc[book['is_open'], 'balance'].sum())
    ending_current = float(
        book.loc[book['is_open'] & (book['days_past_due'] <= 0), 'balance'].sum()
    )

    collectable = opening + credit_sales - ending_current
    if collectable <= 0:
        return None
    collected = opening + credit_sales - ending_total
    return round(max(min(ratio(collected, collectable) * _PERCENT, _PERCENT), 0.0), 1)


def _weighted(values: pd.Series, weights: pd.Series) -> float:
    '''
        Weighted mean, guarding against an empty or zero-weight series.

        Weighted by amount and never a plain average: one small invoice sitting
        200 days late would otherwise move the figure more than a large one
        that is barely late.

        Args:
            values (pd.Series): The measure.
            weights (pd.Series): The weight of each value.

        Returns:
            float: The weighted mean, or 0.0 when it cannot be computed.
    '''
    mask = values.notna() & weights.notna()
    total = float(weights.loc[mask].sum())
    if total <= 0:
        return 0.0
    return round(float((values.loc[mask] * weights.loc[mask]).sum()) / total, 1)


def _kpis(book: pd.DataFrame, cash_amount: float, as_of: pd.Timestamp,
          aging: List[AgingRow],
          collections: Optional[pd.DataFrame] = None) -> ReceivablesKpis:
    '''
        The headline figures of the book: position, speed and recoverability.

        Args:
            book (pd.DataFrame): The credit book.
            cash_amount (float): Amount sold in cash, for the mix.
            as_of (pd.Timestamp): Reference date.
            aging (List[AgingRow]): The aging rows, to total the provision.
            collections (pd.DataFrame | None): Payment rows, for the index that
                needs the balance at a past date.

        Returns:
            ReceivablesKpis: Every headline figure of the view.
    '''
    open_book = book.loc[book['is_open']]
    credit_amount = float(book['amount'].sum())
    receivable = float(open_book['balance'].sum())
    overdue = float(open_book.loc[open_book['days_past_due'] > 0, 'balance'].sum())
    uncollectible = float(sum(row.provision for row in aging))

    settled = book.loc[book['days_late'].notna()]
    on_time = settled.loc[settled['days_late'] <= 0, 'amount'].sum()

    return ReceivablesKpis(
        as_of = as_of.date().isoformat(),
        credit_amount = money(credit_amount),
        cash_amount = money(cash_amount),
        credit_share = round(ratio(credit_amount, credit_amount + cash_amount) * _PERCENT, 1),
        receivable_total = money(receivable),
        current_amount = money(receivable - overdue),
        overdue_amount = money(overdue),
        overdue_rate = round(ratio(overdue, receivable) * _PERCENT, 1),
        clients_with_debt = int(open_book['client'].nunique()),
        open_invoices = int(len(open_book)),
        recoverable_amount = money(receivable - uncollectible),
        uncollectible_amount = money(uncollectible),
        recoverable_rate = round(ratio(receivable - uncollectible, receivable) * _PERCENT, 1),
        uncollectible_rate = round(ratio(uncollectible, receivable) * _PERCENT, 1),
        days_sales_outstanding = _dso(book, as_of, receivable),
        average_days_delinquent = _weighted(
            open_book['days_past_due'], open_book['balance']
        ),
        weighted_days_late = _weighted(
            open_book.loc[open_book['days_past_due'] > 0, 'days_past_due'],
            open_book.loc[open_book['days_past_due'] > 0, 'balance']
        ),
        collection_effectiveness = _collection_effectiveness(
            book, collections, as_of
        ),
        on_time_rate = (
            round(ratio(float(on_time), float(settled['amount'].sum())) * _PERCENT, 1)
            if not settled.empty else None
        ),
        average_term_granted = _weighted(
            pd.to_numeric(book['credit_days'], errors = 'coerce'), book['amount']
        ),
        average_term_real = (
            _weighted(settled['real_term'], settled['amount'])
            if not settled.empty else None
        )
    )


def _gross_margin(sales: pd.DataFrame, credit_rows: pd.Series) -> Tuple[float, float, float]:
    '''
        Gross margin of the credit sales and of the cash ones.

        Args:
            sales (pd.DataFrame): Normalized sales rows.
            credit_rows (pd.Series): Boolean mask of the credit rows.

        Returns:
            Tuple[float, float, float]: Credit revenue, credit margin and cash
                margin rate. Zeros when the file has no cost column.
    '''
    if COST not in sales.columns or PRICE not in sales.columns:
        return 0.0, 0.0, 0.0

    frame = sales.assign(
        _margin = (
            pd.to_numeric(sales[PRICE], errors = 'coerce').fillna(0.0)
            - pd.to_numeric(sales[COST], errors = 'coerce').fillna(0.0)
        ) * pd.to_numeric(sales[QUANTITY], errors = 'coerce').fillna(0.0)
    )
    credit = frame.loc[credit_rows]
    cash = frame.loc[~credit_rows]

    credit_revenue = float(credit[AMOUNT].sum())
    cash_rate = ratio(float(cash['_margin'].sum()), float(cash[AMOUNT].sum())) * _PERCENT
    return credit_revenue, float(credit['_margin'].sum()), round(cash_rate, 1)


def _credit_margin(book: pd.DataFrame, sales: pd.DataFrame,
                   policy: Policy, uncollectible: float) -> CreditMargin:
    '''
        What the credit leaves once financed and provisioned.

        The financing cost is the whole time the money is out; the delinquency
        cost is only the part beyond the agreed term. They are reported apart
        because the first one is a commercial decision and the second one is a
        failure to collect.

        Args:
            book (pd.DataFrame): The credit book.
            sales (pd.DataFrame): Normalized sales rows.
            policy (Policy): Resolved parameters.
            uncollectible (float): Provision over the open book.

        Returns:
            CreditMargin: The margin chain, or an unavailable block with its
                code when the file carries no unit cost.
    '''
    if COST not in sales.columns:
        return CreditMargin(available = False, reason_code = 'NO_COST_COLUMN')

    credit_rows = sales[TERMS].astype(str).str.upper() == CREDIT
    revenue, gross, cash_rate = _gross_margin(sales, credit_rows)

    rate = policy.financial_rate_daily
    open_book = book.loc[book['is_open']]
    financing = float((open_book['balance'] * open_book['days_outstanding'] * rate).sum())
    delinquency = float((open_book['balance'] * open_book['days_past_due'] * rate).sum())
    net = gross - financing - uncollectible

    return CreditMargin(
        available = True,
        credit_revenue = money(revenue),
        credit_gross_margin = money(gross),
        credit_gross_margin_rate = round(ratio(gross, revenue) * _PERCENT, 1),
        financing_cost = money(financing),
        delinquency_cost = money(delinquency),
        expected_loss = money(uncollectible),
        net_margin = money(net),
        net_margin_rate = round(ratio(net, revenue) * _PERCENT, 1),
        cash_gross_margin_rate = cash_rate
    )


def _unavailable(code: ReceivablesUnavailable) -> ReceivablesBlock:
    '''
        Returns the block a dataset without credit data gets.

        Args:
            code (ReceivablesUnavailable): Why it cannot be built.

        Returns:
            ReceivablesBlock: Not available, with its reason code.
    '''
    message = f'Receivables block skipped: {code.value}.'
    logger.info(message)
    return ReceivablesBlock(available = False, reason_code = code.value)


def build_receivables(sales: pd.DataFrame,
                      collections: Optional[pd.DataFrame] = None,
                      stored_policy: Optional[Dict[str, Any]] = None) -> ReceivablesBlock:
    '''
        Builds the receivables view from the sales and their payments.

        Args:
            sales (pd.DataFrame): Normalized sales rows as produced by ingest,
                including the credit columns of the contract.
            collections (pd.DataFrame | None): Normalized payment rows, when the
                dataset has any. Their absence means every credit invoice is
                still open, which is a fact and not an error.
            stored_policy (Dict[str, Any] | None): The client's own policy.

        Returns:
            ReceivablesBlock: The whole view, or an unavailable block with its
                code when the dataset carries no credit information.
    '''
    if TERMS not in sales.columns:
        return _unavailable(ReceivablesUnavailable.NO_CREDIT_COLUMNS)

    policy = resolve_policy(stored_policy)
    invoices = _invoice_frame(sales)
    if invoices is None or invoices.empty:
        return _unavailable(ReceivablesUnavailable.NO_CREDIT_COLUMNS)

    invoices = _with_terms(invoices, policy)
    if not invoices['is_credit'].any():
        return _unavailable(ReceivablesUnavailable.NO_CREDIT_SALES)

    payments = _payments_by_invoice(collections)
    # The cut-off is the last day with activity in the file, payments included.
    # Using today's date would report the whole book of a dataset from last
    # quarter as overdue, only because time passed.
    last_payment = payments['last_payment'].max() if not payments.empty else pd.NaT
    as_of = max(
        value for value in (invoices['date'].max(), last_payment) if pd.notna(value)
    )

    book = _book(invoices, payments, as_of, policy)
    aging = _aging(book, policy)
    cash_amount = float(invoices.loc[~invoices['is_credit'], 'amount'].sum())
    kpis = _kpis(book, cash_amount, as_of, aging, collections)

    calendar = build_due_calendar(book, as_of)
    message = (f'Building receivables block: {len(book)} credit invoice(s), '
               f'{kpis.open_invoices} open, as of {kpis.as_of}.')
    logger.info(message)

    return ReceivablesBlock(
        available = True,
        policy = policy.as_dto(),
        kpis = kpis,
        margin = _credit_margin(book, sales, policy, kpis.uncollectible_amount),
        aging = aging,
        debtors = build_debtors(book, policy.delinquent_days),
        collectors = build_collectors(book),
        due_windows = calendar.windows,
        due_dates = calendar.dates,
        collection_curve = build_collection_curve(book, collections),
        priority = build_priority(book, policy.delinquent_days)
    )
