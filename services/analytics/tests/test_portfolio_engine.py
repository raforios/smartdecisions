'''
    Unit tests for the portfolio_engine (coverage, churn, clients at risk).
'''
import pandas as pd

from services.portfolio_engine import build_portfolio


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
        'id_pedido': f'{client}-{date}', 'id_punto_venta': client,
        'nombre_pdv': f'Tienda {client}', 'fecha': pd.Timestamp(date),
        'monto_total': amount
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
    at_risk = {row['cliente'] for row in build_portfolio(frame)['en_riesgo']}
    assert 'Tienda A' not in at_risk


def test_client_who_stopped_buying_is_flagged():
    '''A client silent for more than two months is surfaced with its reason.'''
    frame = pd.DataFrame([
        _purchase('A', '2024-01-10'), _purchase('A', '2024-02-10'),
        _purchase('A', '2024-03-10'), _purchase('A', '2024-04-10'),
        _purchase('B', '2024-01-10'), _purchase('B', '2024-04-10'),
    ])
    flagged = {row['cliente']: row for row in build_portfolio(frame)['en_riesgo']}
    assert 'Tienda A' not in flagged


def test_movement_reports_new_clients_on_the_first_month():
    '''Everyone is new in the first month; nobody can be retained yet.'''
    frame = pd.DataFrame([_purchase('A', '2024-01-10'), _purchase('B', '2024-01-11')])
    first = build_portfolio(frame)['movimiento'][0]
    assert first['nuevos'] == 2
    assert first['retenidos'] == 0
    assert first['activos'] == 2


def test_retained_and_lost_clients_are_counted():
    '''
        A buys in both months (retained), B only in the first (lost in the
        second), C appears in the second (new).
    '''
    frame = pd.DataFrame([
        _purchase('A', '2024-01-10'), _purchase('B', '2024-01-11'),
        _purchase('A', '2024-02-10'), _purchase('C', '2024-02-11'),
    ])
    second = build_portfolio(frame)['movimiento'][1]
    assert second['retenidos'] == 1
    assert second['nuevos'] == 1
    assert second['perdidos'] == 1


def test_coverage_kpi_counts_clients_active_in_the_last_month():
    '''Coverage is the share of the book that bought in the most recent month.'''
    frame = pd.DataFrame([
        _purchase('A', '2024-01-10'), _purchase('B', '2024-01-11'),
        _purchase('A', '2024-02-10'),
    ])
    kpis = {kpi['label']: kpi['value'] for kpi in build_portfolio(frame)['kpis']}
    assert kpis['Clientes en la cartera'] == 2
    assert kpis['Activos el último mes'] == 1
    assert kpis['Cobertura'] == 50.0


def test_empty_sections_without_dates():
    '''A file with no dates yields empty sections instead of an error.'''
    frame = pd.DataFrame({'id_punto_venta': ['A'], 'monto_total': [10.0]})
    result = build_portfolio(frame)
    assert not result['movimiento']
    assert not result['en_riesgo']
