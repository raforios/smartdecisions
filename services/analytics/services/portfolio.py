'''
    Portfolio health engine — the state of the client base over time.

    Revenue can stay flat while the portfolio rots underneath: new clients
    replacing lost ones month after month is a very different business from a
    stable base that grows. This module exposes that movement and, above all,
    turns it into a list of names the sales team can call today:

        * Coverage: how many clients of the base actually bought recently.
        * Movement per month: new, recovered, retained and lost clients.
        * Clients at risk: those whose purchases collapsed against their own
          history, or who simply stopped buying — ranked by what is at stake.
'''
from typing import Any, Dict, List, Set, Optional

import pandas as pd

from schemas.analytics import (
    ClientAtRisk,
    KpiCard,
    MetricCode,
    PortfolioBlock,
    PortfolioMovement,
    RiskReason
)

from services.analytics_utils import (
    setting,
    CLIENT_ID,
    CLIENT_NAME,
    AMOUNT,
    dates,
    label_series,
    money,
    order_count,
    ratio
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

# What counts as "at risk" is a business rule, not a constant of nature: a
# distributor whose clients restock weekly and one whose clients restock
# quarterly need different numbers, and getting them wrong flags either nobody
# or the whole book. They are read from the environment so an operation can be
# tuned without a redeploy, with the defaults below calibrated on real data.
_SETTINGS = load_and_validate_env_vars({}, optional_env_vars = {
    'PORTFOLIO_RISK_DROP_PERCENT': float,
    'PORTFOLIO_RISK_SILENCE_DAYS': int,
    'PORTFOLIO_LOST_SILENCE_DAYS': int,
    'PORTFOLIO_MAX_RISK_CLIENTS': int,
    'PORTFOLIO_MAX_LOST_CLIENTS': int,
})

# A client whose latest month falls this far below their own monthly average is
# not "buying less", they are leaving.
_RISK_DROP_PERCENT = setting(_SETTINGS, 'PORTFOLIO_RISK_DROP_PERCENT', -30.0)
# Days without a single purchase before a client is flagged regardless of amount.
_RISK_SILENCE_DAYS = setting(_SETTINGS, 'PORTFOLIO_RISK_SILENCE_DAYS', 60)
# Past this point the client is not at risk, they are gone: chasing them is a
# reactivation campaign, not this week's route. Keeping both in one list buried
# the actionable names among clients who left a year ago.
_LOST_SILENCE_DAYS = setting(_SETTINGS, 'PORTFOLIO_LOST_SILENCE_DAYS', 180)

# The at-risk list is meant to be worked through, so it is short by design.
_MAX_RISK_CLIENTS = setting(_SETTINGS, 'PORTFOLIO_MAX_RISK_CLIENTS', 25)
_MAX_LOST_CLIENTS = setting(_SETTINGS, 'PORTFOLIO_MAX_LOST_CLIENTS', 100)


def _monthly_client_sets(dataframe: pd.DataFrame, parsed_dates: pd.Series,
                         labels: pd.Series) -> Dict[str, Set[str]]:
    '''
        Groups the clients that bought on each calendar month.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            parsed_dates (pd.Series): Coerced datetimes aligned to the frame.
            labels (pd.Series): Readable client label per row.

        Returns:
            Dict[str, Set[str]]: Client labels keyed by 'YYYY-MM'.
    '''
    valid = parsed_dates.notna()
    scoped = dataframe.loc[valid].assign(
        _month = parsed_dates[valid].dt.strftime('%Y-%m'),
        _client = labels[valid].values
    )
    return {
        str(month): set(group['_client'].astype(str))
        for month, group in scoped.groupby('_month')
    }


def _movement(monthly_sets: Dict[str, Set[str]]) -> List[PortfolioMovement]:
    '''
        Builds the month-by-month movement of the client base.

        A client is *new* the first month they ever appear, *recovered* when
        they had bought before, skipped the previous month and came back, and
        *lost* when they bought last month but not this one.

        Args:
            monthly_sets (Dict[str, Set[str]]): Clients per 'YYYY-MM'.

        Returns:
            List[PortfolioMovement]: One row per month in chronological order.
    '''
    months = sorted(monthly_sets)
    seen: Set[str] = set()
    previous: Set[str] = set()
    rows: List[PortfolioMovement] = []

    for month in months:
        current = monthly_sets[month]
        new_clients = current - seen
        recovered = (current & seen) - previous
        retained = current & previous
        lost = previous - current
        rows.append(PortfolioMovement(
            month = month,
            active = len(current),
            new_clients = len(new_clients),
            recovered = len(recovered),
            retained = len(retained),
            lost = len(lost),
            churn = round(ratio(len(lost), len(previous)) * 100, 1) if previous else None
        ))
        seen |= current
        previous = current
    return rows


def _client_history(dataframe: pd.DataFrame, parsed_dates: pd.Series,
                    labels: pd.Series) -> pd.DataFrame:
    '''
        Per-client history: total amount, months active, last purchase date and
        the amount bought in the most recent month of the dataset.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            parsed_dates (pd.Series): Coerced datetimes aligned to the frame.
            labels (pd.Series): Readable client label per row.

        Returns:
            pd.DataFrame: One row per client, indexed by client label.
    '''
    valid = parsed_dates.notna()
    scoped = dataframe.loc[valid].assign(
        _date = parsed_dates[valid].values,
        _month = parsed_dates[valid].dt.strftime('%Y-%m').values,
        _client = labels[valid].astype(str).values
    )
    last_month = scoped['_month'].max()
    grouped = scoped.groupby('_client')
    history = pd.DataFrame({
        'total_amount': grouped[AMOUNT].sum(),
        'active_months': grouped['_month'].nunique(),
        'last_purchase': grouped['_date'].max()
    })
    recent = scoped.loc[scoped['_month'] == last_month].groupby('_client')[AMOUNT].sum()
    history['last_month_amount'] = recent.reindex(history.index).fillna(0.0)
    return history


def _classify(silence_days: int, drop: float) -> tuple[str, RiskReason] | None:
    '''
        Decides which list a client belongs to, and why.

        The split exists because "about to leave" and "already gone" are two
        different conversations: one is a visit this week, the other is a
        reactivation campaign. Merging them produced a list holding 39% of the
        client base, which no sales manager can act on.

        Args:
            silence_days (int): Days since the client's last purchase.
            drop (float): Percentage change of the last month against the
                client's own monthly average.

        Returns:
            tuple[str, RiskReason] | None: (bucket, reason code), or None when
                the client is behaving normally.
    '''
    if silence_days >= _LOST_SILENCE_DAYS:
        return 'lost', RiskReason.LONG_SILENCE
    if silence_days >= _RISK_SILENCE_DAYS:
        return 'at_risk', RiskReason.SILENCE
    if drop <= _RISK_DROP_PERCENT:
        return 'at_risk', RiskReason.PURCHASE_DROP
    return None


def _client_row(client: Any,
                record: pd.Series,
                reference_date: pd.Timestamp) -> tuple[Optional[str], ClientAtRisk]:
    '''
        Builds one row of the risk / lost tables.

        Args:
            client (Any): Client label.
            record (pd.Series): That client's row of the history frame.
            reference_date (pd.Timestamp): Latest date present in the dataset.

        Returns:
            tuple[Optional[str], ClientAtRisk]: Which list the client belongs to
                ('at_risk', 'lost' or None) and the row itself.
    '''
    months_active = int(record['active_months']) or 1
    monthly_average = float(record['total_amount']) / months_active
    last_amount = float(record['last_month_amount'])
    silence_days = int((reference_date - pd.Timestamp(record['last_purchase'])).days)
    drop = round(ratio(last_amount - monthly_average, monthly_average) * 100, 1)
    verdict = _classify(silence_days, drop)

    row = ClientAtRisk(
        client = str(client),
        monthly_average_amount = money(monthly_average),
        last_month_amount = money(last_amount),
        change = drop,
        days_without_purchase = silence_days,
        last_purchase = pd.Timestamp(record['last_purchase']).strftime('%Y-%m-%d'),
        reason_code = verdict[1].value if verdict else None
    )
    return (verdict[0] if verdict else None), row


def _split_by_risk(history: pd.DataFrame,
                   reference_date: pd.Timestamp) -> tuple[List[ClientAtRisk], ...]:
    '''
        Splits the client base into those worth chasing now and those already
        lost, each ordered by the monthly revenue at stake.

        Args:
            history (pd.DataFrame): Per-client history from _client_history.
            reference_date (pd.Timestamp): Latest date present in the dataset —
                recency is measured against the data, never against "today",
                which would flag every client of an old export.

        Returns:
            tuple: (at-risk rows, lost rows), both capped for readability.
    '''
    buckets: Dict[str, List[ClientAtRisk]] = {'at_risk': [], 'lost': []}
    for client, record in history.iterrows():
        bucket, row = _client_row(client, record, reference_date)
        if bucket:
            buckets[bucket].append(row)

    for rows in buckets.values():
        rows.sort(key = lambda row: row.monthly_average_amount, reverse = True)
    return buckets['at_risk'][:_MAX_RISK_CLIENTS], buckets['lost'][:_MAX_LOST_CLIENTS]


def _portfolio_kpis(history: pd.DataFrame, movement: List[PortfolioMovement],
                    dataframe: pd.DataFrame,
                    counts: tuple[int, int]) -> List[KpiCard]:
    '''
        Headline cards describing the health of the client base.

        Args:
            history (pd.DataFrame): Per-client history.
            movement (List[Dict[str, Any]]): Monthly movement rows.
            dataframe (pd.DataFrame): Normalized sales rows (for order counts).
            counts (tuple[int, int]): (clients at risk, clients already lost).

        Returns:
            List[KpiCard]: KPI cards ready for the UI.
    '''
    total_clients = int(len(history))
    last = movement[-1] if movement else PortfolioMovement(month = '')
    active = last.active
    months = max(len(movement), 1)

    return [
        KpiCard(metric_code = MetricCode.PORTFOLIO_CLIENTS.value,
         value = float(total_clients), format = 'int'),
        KpiCard(metric_code = MetricCode.ACTIVE_LAST_MONTH.value,
         value = float(active), format = 'int'),
        KpiCard(metric_code = MetricCode.COVERAGE.value,
         value = round(ratio(active, total_clients) * 100, 1), format = 'percent'),
        KpiCard(metric_code = MetricCode.CHURN_LAST_MONTH.value,
         value = last.churn, format = 'percent'),
        KpiCard(metric_code = MetricCode.CLIENTS_AT_RISK.value,
         value = float(counts[0]), format = 'int'),
        KpiCard(metric_code = MetricCode.CLIENTS_LOST.value,
         value = float(counts[1]), format = 'int'),
        KpiCard(metric_code = MetricCode.PURCHASE_FREQUENCY.value,
         value = round(ratio(order_count(dataframe), total_clients * months), 2),
         format = 'decimal'),
    ]


def _empty_portfolio() -> Dict[str, Any]:
    '''
        Neutral payload used when the dataset cannot support the analysis.

        Returns:
            Dict[str, Any]: Empty sections with the same shape as a real result.
    '''
    return PortfolioBlock()


def build_portfolio(dataframe: pd.DataFrame) -> PortfolioBlock:
    '''
        Builds the portfolio-health report.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by ingest.

        Returns:
            Dict[str, Any]: 'kpis' (coverage, churn, frequency), 'movement'
                (new/recovered/retained/lost per month), 'at_risk' (a short
                actionable list) and 'lost' (clients gone long enough to need
                a reactivation campaign), each with its total. Empty sections
                instead of errors when the file lacks dates, amounts or ids.
    '''
    parsed_dates = dates(dataframe)
    labels = label_series(dataframe, CLIENT_ID, CLIENT_NAME)
    if parsed_dates is None or labels is None or AMOUNT not in dataframe.columns:
        message = 'Portfolio report skipped: missing date, client or amount column.'
        logger.info(message)
        return _empty_portfolio()

    monthly_sets = _monthly_client_sets(dataframe, parsed_dates, labels)
    if not monthly_sets:
        return _empty_portfolio()

    movement = _movement(monthly_sets)
    history = _client_history(dataframe, parsed_dates, labels)
    at_risk, lost = _split_by_risk(history, parsed_dates.max())

    message = (f'Portfolio report: {len(history)} clients over {len(movement)} months, '
               f'{len(at_risk)} at risk, {len(lost)} lost.')
    logger.info(message)

    return PortfolioBlock(
        kpis = _portfolio_kpis(history, movement, dataframe, (len(at_risk), len(lost))),
        movement = movement,
        at_risk = at_risk,
        total_at_risk = len(at_risk),
        lost = lost,
        total_lost = len(lost)
    )
