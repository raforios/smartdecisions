'''
    Receivables — the tables a person acts on.

    The engine in `receivables.py` builds the book and measures it; this module
    turns that same book into the four lists somebody actually works from: who
    owes, who is responsible for collecting it, what falls due when, and who to
    call today.

    It takes the book already built and never reads the raw sales again, so
    there is one definition of a balance and one definition of an age in the
    whole service.
'''
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd

from schemas.receivables import (
    CollectionCurvePoint,
    CollectorRow,
    CreditRisk,
    DebtorRow,
    DueDateRow,
    DueWindow,
    PriorityRow
)
from services.analytics_utils import money, ratio
from services.environment import load_and_validate_env_vars

_SETTINGS = load_and_validate_env_vars({
    'RECEIVABLES_CALENDAR_DAYS': int,
    'RECEIVABLES_COHORT_MONTHS': int,
    'RECEIVABLES_TOP_CLIENTS': int,
    'RECEIVABLES_TOP_COLLECTORS': int,
    'RECEIVABLES_PRIORITY_ROWS': int,
})
_CALENDAR_DAYS = _SETTINGS['RECEIVABLES_CALENDAR_DAYS']
_COHORT_MONTHS = _SETTINGS['RECEIVABLES_COHORT_MONTHS']
_TOP_CLIENTS = _SETTINGS['RECEIVABLES_TOP_CLIENTS']
_TOP_COLLECTORS = _SETTINGS['RECEIVABLES_TOP_COLLECTORS']
_PRIORITY_ROWS = _SETTINGS['RECEIVABLES_PRIORITY_ROWS']

_PERCENT = 100.0

# Risk cut points of a debtor, in days past due of its oldest balance. They are
# reading bands, not provisioning ones: the provision is decided by the policy.
_WATCH_DAYS = 1
_DELINQUENT_DAYS = 30
_CRITICAL_DAYS = 90

# Windows of the collection calendar. Overdue goes on its own because it is not
# a cash projection: it is money that should already have been collected.
_WINDOW_OVERDUE = 'OVERDUE'
_WINDOWS: Tuple[Tuple[str, int], ...] = (
    ('DAYS_7', 7), ('DAYS_15', 15), ('DAYS_30', 30)
)
_WINDOW_BEYOND = 'BEYOND'

# Horizons of the collection curve, in days.
_CURVE_DAYS: Tuple[int, ...] = (30, 60, 90)


@dataclass(frozen = True)
class DueCalendar:
    '''
        The collection calendar: the windows for the cash projection and the
        per-date detail for the agenda.
    '''
    windows: List[DueWindow]
    dates: List[DueDateRow]


def risk_of(oldest_days: float, delinquent_days: int) -> CreditRisk:
    '''
        Reads a debtor's risk from the age of its oldest open balance.

        Args:
            oldest_days (float): Days past due of its oldest open balance.
            delinquent_days (int): Days from which the policy counts a client
                as delinquent.

        Returns:
            CreditRisk: The risk code; the UI words it.
    '''
    if oldest_days >= _CRITICAL_DAYS:
        return CreditRisk.CRITICAL
    if oldest_days >= _DELINQUENT_DAYS:
        return CreditRisk.DELINQUENT
    if oldest_days >= max(delinquent_days, _WATCH_DAYS):
        return CreditRisk.WATCH
    return CreditRisk.HEALTHY


def _weighted_late(group: pd.DataFrame) -> float:
    '''
        Days late of a group, weighted by the balance at stake.

        Args:
            group (pd.DataFrame): Open invoices of one client or collector.

        Returns:
            float: Weighted days late, 0.0 when nothing is overdue.
    '''
    overdue = group.loc[group['days_past_due'] > 0]
    total = float(overdue['balance'].sum())
    if total <= 0:
        return 0.0
    return round(
        float((overdue['days_past_due'] * overdue['balance']).sum()) / total, 1
    )


def build_debtors(book: pd.DataFrame, delinquent_days: int) -> List[DebtorRow]:
    '''
        Who owes, largest open balance first.

        Args:
            book (pd.DataFrame): The credit book.
            delinquent_days (int): Policy threshold for delinquency.

        Returns:
            List[DebtorRow]: One row per client with debt, capped at the
                configured top.
    '''
    open_book = book.loc[book['is_open']]
    if open_book.empty:
        return []

    rows: List[DebtorRow] = []
    for client, group in open_book.groupby('client'):
        limit = pd.to_numeric(group['credit_limit'], errors = 'coerce').max()
        open_amount = float(group['balance'].sum())
        oldest = int(group['days_past_due'].max())
        rows.append(DebtorRow(
            label = str(client),
            open_amount = money(open_amount),
            overdue_amount = money(
                float(group.loc[group['days_past_due'] > 0, 'balance'].sum())
            ),
            oldest_days = oldest,
            weighted_days_late = _weighted_late(group),
            invoices = int(len(group)),
            credit_limit = money(float(limit)) if pd.notna(limit) else None,
            # An unknown limit is not an unused one: when the file does not
            # carry it, utilization travels empty and never as 0%.
            limit_utilization = (
                round(ratio(open_amount, float(limit)) * _PERCENT, 1)
                if pd.notna(limit) and float(limit) > 0 else None
            ),
            risk_code = risk_of(oldest, delinquent_days),
            collector = (
                str(group['collector'].dropna().iloc[0])
                if group['collector'].notna().any() else None
            )
        ))

    rows.sort(key = lambda row: row.open_amount, reverse = True)
    return rows[:_TOP_CLIENTS]


def build_collectors(book: pd.DataFrame) -> List[CollectorRow]:
    '''
        Who is responsible for collecting what.

        The on-time rate measures the collector; the overdue amount measures
        the book they were handed. Both travel, because judging one by the
        other is how a good collector on a hard zone gets blamed.

        Args:
            book (pd.DataFrame): The credit book.

        Returns:
            List[CollectorRow]: One row per collector, largest open first.
    '''
    if 'collector' not in book.columns or not book['collector'].notna().any():
        return []

    rows: List[CollectorRow] = []
    for collector, group in book.loc[book['collector'].notna()].groupby('collector'):
        open_group = group.loc[group['is_open']]
        settled = group.loc[group['days_late'].notna()]
        on_time = float(settled.loc[settled['days_late'] <= 0, 'amount'].sum())

        rows.append(CollectorRow(
            label = str(collector),
            open_amount = money(float(open_group['balance'].sum())),
            overdue_amount = money(
                float(open_group.loc[open_group['days_past_due'] > 0, 'balance'].sum())
            ),
            clients = int(open_group['client'].nunique()),
            invoices = int(len(open_group)),
            weighted_days_late = _weighted_late(open_group),
            on_time_rate = (
                round(ratio(on_time, float(settled['amount'].sum())) * _PERCENT, 1)
                if not settled.empty else None
            )
        ))

    rows.sort(key = lambda row: row.open_amount, reverse = True)
    return rows[:_TOP_COLLECTORS]


def _due_windows(open_book: pd.DataFrame, as_of: pd.Timestamp) -> List[DueWindow]:
    '''
        The open balance split into the windows a cash projection needs.

        Args:
            open_book (pd.DataFrame): Open invoices.
            as_of (pd.Timestamp): Reference date.

        Returns:
            List[DueWindow]: Overdue first, then each horizon, then the rest.
    '''
    windows: List[DueWindow] = []
    overdue = open_book.loc[open_book['days_past_due'] > 0]
    if not overdue.empty:
        windows.append(DueWindow(
            window_code = _WINDOW_OVERDUE,
            amount = money(float(overdue['balance'].sum())),
            invoices = int(len(overdue))
        ))

    upcoming = open_book.loc[open_book['days_past_due'] <= 0]
    previous = 0
    for code, days in _WINDOWS:
        limit = as_of + pd.Timedelta(days = days)
        floor = as_of + pd.Timedelta(days = previous)
        inside = upcoming.loc[
            (upcoming['due_date'] > floor) & (upcoming['due_date'] <= limit)
        ]
        previous = days
        if inside.empty:
            continue
        windows.append(DueWindow(
            window_code = code,
            amount = money(float(inside['balance'].sum())),
            invoices = int(len(inside))
        ))

    beyond = upcoming.loc[upcoming['due_date'] > as_of + pd.Timedelta(days = previous)]
    if not beyond.empty:
        windows.append(DueWindow(
            window_code = _WINDOW_BEYOND,
            amount = money(float(beyond['balance'].sum())),
            invoices = int(len(beyond))
        ))
    return windows


def build_due_calendar(book: pd.DataFrame, as_of: pd.Timestamp) -> DueCalendar:
    '''
        What falls due and when: the windows and the day-by-day agenda.

        Args:
            book (pd.DataFrame): The credit book.
            as_of (pd.Timestamp): Reference date.

        Returns:
            DueCalendar: Windows for the projection, dates for the agenda.
    '''
    open_book = book.loc[book['is_open'] & book['due_date'].notna()]
    if open_book.empty:
        return DueCalendar(windows = [], dates = [])

    horizon = as_of + pd.Timedelta(days = _CALENDAR_DAYS)
    agenda = open_book.loc[
        (open_book['due_date'] > as_of) & (open_book['due_date'] <= horizon)
    ]
    dates = [
        DueDateRow(
            due_date = day.date().isoformat(),
            amount = money(float(group['balance'].sum())),
            invoices = int(len(group)),
            clients = int(group['client'].nunique())
        )
        for day, group in agenda.groupby('due_date')
    ]
    return DueCalendar(windows = _due_windows(open_book, as_of), dates = dates)


def build_collection_curve(book: pd.DataFrame,
                           collections: Optional[pd.DataFrame]) -> List[CollectionCurvePoint]:
    '''
        How fast each month's credit sales came back.

        Of everything billed on credit in a month, how much had been collected
        30, 60 and 90 days later. It answers what a single DSO cannot: whether
        collection is getting faster or slower.

        A horizon that has not elapsed yet travels as None instead of as a low
        percentage: last month cannot have a 90-day figure, and showing one
        would read as a collapse.

        Args:
            book (pd.DataFrame): The credit book.
            collections (pd.DataFrame | None): Normalized payment rows.

        Returns:
            List[CollectionCurvePoint]: One point per cohort, oldest first.
    '''
    if collections is None or collections.empty or book.empty:
        return []
    if 'order_id' not in collections.columns:
        return []

    payments = collections.copy()
    payments['payment_date'] = pd.to_datetime(
        payments.get('payment_date'), errors = 'coerce'
    )
    invoiced = book.set_index('order_id')[['date', 'amount']]
    payments = payments.join(invoiced, on = 'order_id', rsuffix = '_invoice')
    payments = payments.loc[payments['date'].notna() & payments['payment_date'].notna()]
    if payments.empty:
        return []

    payments['elapsed'] = (payments['payment_date'] - payments['date']).dt.days
    payments['cohort'] = payments['date'].dt.strftime('%Y-%m')

    book_cohorts = book.assign(cohort = book['date'].dt.strftime('%Y-%m'))
    totals = book_cohorts.groupby('cohort')['amount'].sum()
    last_activity = payments['payment_date'].max()

    points: List[CollectionCurvePoint] = []
    for cohort in sorted(totals.index)[-_COHORT_MONTHS:]:
        credit_amount = float(totals.loc[cohort])
        if credit_amount <= 0:
            continue
        cohort_start = pd.Period(cohort, freq = 'M').start_time
        rows = payments.loc[payments['cohort'] == cohort]
        collected = {}
        for days in _CURVE_DAYS:
            if cohort_start + pd.Timedelta(days = days) > last_activity:
                collected[days] = None
                continue
            paid = float(rows.loc[rows['elapsed'] <= days, 'paid_amount'].sum())
            collected[days] = round(ratio(paid, credit_amount) * _PERCENT, 1)

        points.append(CollectionCurvePoint(
            cohort_month = cohort,
            credit_amount = money(credit_amount),
            collected_30 = collected[30],
            collected_60 = collected[60],
            collected_90 = collected[90]
        ))
    return points


def build_priority(book: pd.DataFrame, delinquent_days: int) -> List[PriorityRow]:
    '''
        Who to call today.

        Sorted by what can still be recovered —overdue balance × the
        probability of recovering it, which is one minus the expected loss of
        its bucket— and not by days overdue. A large balance that is still
        recoverable is worth the call; the oldest one on the list often is not.

        Args:
            book (pd.DataFrame): The credit book.
            delinquent_days (int): Policy threshold for delinquency.

        Returns:
            List[PriorityRow]: The actionable list, best expected recovery first.
    '''
    overdue = book.loc[book['is_open'] & (book['days_past_due'] > 0)]
    if overdue.empty:
        return []

    frame = overdue.assign(
        recovery = (1.0 - overdue['loss_rate']) * overdue['balance']
    )
    rows: List[PriorityRow] = []
    for client, group in frame.groupby('client'):
        amount = float(group['balance'].sum())
        recovery = float(group['recovery'].sum())
        oldest = int(group['days_past_due'].max())
        rows.append(PriorityRow(
            label = str(client),
            collector = (
                str(group['collector'].dropna().iloc[0])
                if group['collector'].notna().any() else None
            ),
            overdue_amount = money(amount),
            oldest_days = oldest,
            recovery_probability = round(ratio(recovery, amount), 3),
            expected_recovery = money(recovery),
            risk_code = risk_of(oldest, delinquent_days)
        ))

    rows.sort(key = lambda row: row.expected_recovery, reverse = True)
    return rows[:_PRIORITY_ROWS]
