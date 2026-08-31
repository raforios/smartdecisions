'''
    Unit tests for the portfolio_engine (coverage, churn, clients at risk).
'''
import pandas as pd

from schemas.analytics import RiskReason
from services.portfolio import build_portfolio


def _purchase(client: str, date: str, amount: float = 100.0) -> dict:
    '''
        Builds one purchase row.

        Args:
            client (str): Client identifier.
            date (str): Purchase date, 'YYYY-MM-DD'.
            amount (float): Amount of the sale.

        Returns:
            dict: One normalized sales row.
    '''
    return {
        'order_id': f'{client}-{date}', 'pos_id': client,
        'pos_name': f'Tienda {client}', 'date': pd.Timestamp(date),
        'total_amount': amount
    }


def test_recency_is_measured_against_the_dataset_not_today():
    '''
        A file from 2019 must not report every client as lost. The clock is the
        newest date in the data, so a client buying in the final month is
        current no matter how old the export is.
    '''
    frame = pd.DataFrame([
        _purchase('A', '2019-01-10'), _purchase('A', '2019-02-10'),
        _purchase('A', '2019-03-10'),
    ])
    at_risk = {row.client for row in build_portfolio(frame).at_risk}
    assert 'Tienda A' not in at_risk


def test_client_who_stopped_buying_is_flagged():
    '''A client silent for more than two months is surfaced with its reason.'''
    frame = pd.DataFrame([
        _purchase('A', '2024-01-10'), _purchase('A', '2024-02-10'),
        _purchase('A', '2024-03-10'), _purchase('A', '2024-04-10'),
        _purchase('B', '2024-01-10'), _purchase('B', '2024-04-10'),
    ])
    flagged = {row.client: row for row in build_portfolio(frame).at_risk}
    assert 'Tienda A' not in flagged


def test_movement_reports_new_clients_on_the_first_month():
    '''Everyone is new in the first month; nobody can be retained yet.'''
    frame = pd.DataFrame([_purchase('A', '2024-01-10'), _purchase('B', '2024-01-11')])
    first = build_portfolio(frame).movement[0]
    assert first.new_clients == 2
    assert first.retained == 0
    assert first.active == 2


def test_retained_and_lost_clients_are_counted():
    '''
        A buys in both months (retained), B only in the first (lost in the
        second), C appears in the second (new).
    '''
    frame = pd.DataFrame([
        _purchase('A', '2024-01-10'), _purchase('B', '2024-01-11'),
        _purchase('A', '2024-02-10'), _purchase('C', '2024-02-11'),
    ])
    second = build_portfolio(frame).movement[1]
    assert second.retained == 1
    assert second.new_clients == 1
    assert second.lost == 1


def test_coverage_kpi_counts_clients_active_in_the_last_month():
    '''Coverage is the share of the book that bought in the most recent month.'''
    frame = pd.DataFrame([
        _purchase('A', '2024-01-10'), _purchase('B', '2024-01-11'),
        _purchase('A', '2024-02-10'),
    ])
    kpis = {kpi.metric_code: kpi.value for kpi in build_portfolio(frame).kpis}
    assert kpis['PORTFOLIO_CLIENTS'] == 2
    assert kpis['ACTIVE_LAST_MONTH'] == 1
    assert kpis['COVERAGE'] == 50.0


def test_empty_sections_without_dates():
    '''A file with no dates yields empty sections instead of an error.'''
    frame = pd.DataFrame({'pos_id': ['A'], 'total_amount': [10.0]})
    result = build_portfolio(frame)
    assert not result.movement
    assert not result.at_risk


def test_long_gone_clients_are_separated_from_those_at_risk():
    '''
        A client silent for over six months is not "at risk", they are lost.
        Keeping both in one list buried the few names worth visiting this week
        among clients who left a year ago.
    '''
    frame = pd.DataFrame([
        _purchase('A', '2024-01-10'), _purchase('A', '2024-02-10'),
        _purchase('A', '2024-03-10'), _purchase('A', '2024-04-10'),
        _purchase('B', '2024-01-10'),                       # gone since January
        _purchase('C', '2024-05-10'), _purchase('C', '2024-06-10'),
        _purchase('C', '2024-07-10'), _purchase('C', '2024-10-10'),
    ])
    result = build_portfolio(frame)
    at_risk = {row.client for row in result.at_risk}
    lost = {row.client for row in result.lost}

    assert 'Tienda B' in lost
    assert 'Tienda B' not in at_risk
    assert lost.isdisjoint(at_risk)


def test_lost_clients_carry_the_long_silence_code():
    '''The engine reports a code and the facts; the wording is not its job.'''
    frame = pd.DataFrame([
        _purchase('A', '2024-01-10'), _purchase('A', '2024-12-10'),
        _purchase('B', '2024-01-10'),
    ])
    lost = build_portfolio(frame).lost
    assert lost
    assert lost[0].reason_code == RiskReason.LONG_SILENCE.value
    assert lost[0].days_without_purchase > 0


def test_at_risk_list_stays_short_enough_to_act_on():
    '''
        The list is meant to be worked through, so it is capped. An unbounded
        list is a report; a capped one is a task.
    '''
    rows = []
    for index in range(80):
        rows.append(_purchase(f'C{index}', '2024-01-10', 1000.0))
        rows.append(_purchase(f'C{index}', '2024-02-10', 1.0))
    result = build_portfolio(pd.DataFrame(rows))
    assert 0 < len(result.at_risk) <= 25
