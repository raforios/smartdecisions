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
from typing import Any, Dict, List, Set

import pandas as pd

from services.frame_utils import (
    CLIENTE_ID,
    CLIENTE_NOMBRE,
    MONTO,
    dates,
    label_series,
    money,
    order_count,
    ratio
)
from services.logger_config import custom_logger as logger

# A client whose latest month falls this far below their own monthly average is
# not "buying less", they are leaving.
_RISK_DROP_PERCENT = -30.0
# Days without a single purchase before a client is flagged regardless of amount.
_RISK_SILENCE_DAYS = 60
_MAX_RISK_CLIENTS = 300


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
        _mes = parsed_dates[valid].dt.strftime('%Y-%m'),
        _cliente = labels[valid].values
    )
    return {
        str(month): set(group['_cliente'].astype(str))
        for month, group in scoped.groupby('_mes')
    }


def _movement(monthly_sets: Dict[str, Set[str]]) -> List[Dict[str, Any]]:
    '''
        Builds the month-by-month movement of the client base.

        A client is *new* the first month they ever appear, *recovered* when
        they had bought before, skipped the previous month and came back, and
        *lost* when they bought last month but not this one.

        Args:
            monthly_sets (Dict[str, Set[str]]): Clients per 'YYYY-MM'.

        Returns:
            List[Dict[str, Any]]: One row per month in chronological order.
    '''
    months = sorted(monthly_sets)
    seen: Set[str] = set()
    previous: Set[str] = set()
    rows: List[Dict[str, Any]] = []

    for month in months:
        current = monthly_sets[month]
        new_clients = current - seen
        recovered = (current & seen) - previous
        retained = current & previous
        lost = previous - current
        rows.append({
            'mes': month,
            'activos': len(current),
            'nuevos': len(new_clients),
            'recuperados': len(recovered),
            'retenidos': len(retained),
            'perdidos': len(lost),
            'churn': round(ratio(len(lost), len(previous)) * 100, 1) if previous else None
        })
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
        _fecha = parsed_dates[valid].values,
        _mes = parsed_dates[valid].dt.strftime('%Y-%m').values,
        _cliente = labels[valid].astype(str).values
    )
    last_month = scoped['_mes'].max()
    grouped = scoped.groupby('_cliente')
    history = pd.DataFrame({
        'monto_total': grouped[MONTO].sum(),
        'meses_activo': grouped['_mes'].nunique(),
        'ultima_compra': grouped['_fecha'].max()
    })
    recent = scoped.loc[scoped['_mes'] == last_month].groupby('_cliente')[MONTO].sum()
    history['monto_ultimo_mes'] = recent.reindex(history.index).fillna(0.0)
    return history


def _at_risk(history: pd.DataFrame, reference_date: pd.Timestamp) -> List[Dict[str, Any]]:
    '''
        Selects the clients whose behaviour signals they are leaving.

        Args:
            history (pd.DataFrame): Per-client history from _client_history.
            reference_date (pd.Timestamp): Latest date present in the dataset —
                recency is measured against the data, never against "today",
                which would flag every client of an old export.

        Returns:
            List[Dict[str, Any]]: At-risk clients ordered by the monthly revenue
                at stake, with the reason spelled out for the sales rep.
    '''
    rows: List[Dict[str, Any]] = []
    for client, record in history.iterrows():
        months_active = int(record['meses_activo']) or 1
        monthly_average = float(record['monto_total']) / months_active
        last_amount = float(record['monto_ultimo_mes'])
        silence_days = int((reference_date - pd.Timestamp(record['ultima_compra'])).days)
        drop = round(ratio(last_amount - monthly_average, monthly_average) * 100, 1)

        if silence_days >= _RISK_SILENCE_DAYS:
            reason = f'No compra hace {silence_days} días.'
        elif drop <= _RISK_DROP_PERCENT:
            reason = f'Su última compra cayó {abs(drop):.0f}% frente a su promedio mensual.'
        else:
            continue

        rows.append({
            'cliente': str(client),
            'monto_promedio_mes': money(monthly_average),
            'monto_ultimo_mes': money(last_amount),
            'variacion': drop,
            'dias_sin_comprar': silence_days,
            'ultima_compra': pd.Timestamp(record['ultima_compra']).strftime('%Y-%m-%d'),
            'motivo': reason
        })
    rows.sort(key = lambda row: row['monto_promedio_mes'], reverse = True)
    return rows[:_MAX_RISK_CLIENTS]


def _portfolio_kpis(history: pd.DataFrame, movement: List[Dict[str, Any]],
                    dataframe: pd.DataFrame, at_risk_total: int) -> List[Dict[str, Any]]:
    '''
        Headline cards describing the health of the client base.

        Args:
            history (pd.DataFrame): Per-client history.
            movement (List[Dict[str, Any]]): Monthly movement rows.
            dataframe (pd.DataFrame): Normalized sales rows (for order counts).
            at_risk_total (int): Number of clients flagged as at risk.

        Returns:
            List[Dict[str, Any]]: KPI cards ready for the UI.
    '''
    total_clients = int(len(history))
    last = movement[-1] if movement else {}
    active = int(last.get('activos', 0))
    months = max(len(movement), 1)

    return [
        {'label': 'Clientes en la cartera', 'value': float(total_clients), 'format': 'int',
         'hint': 'Clientes distintos que compraron en el período'},
        {'label': 'Activos el último mes', 'value': float(active), 'format': 'int',
         'hint': 'Compraron en el mes más reciente'},
        {'label': 'Cobertura', 'value': round(ratio(active, total_clients) * 100, 1),
         'format': 'percent', 'hint': 'Activos del último mes sobre la cartera total'},
        {'label': 'Churn del último mes',
         'value': last.get('churn'), 'format': 'percent',
         'hint': 'Clientes que compraron el mes previo y dejaron de comprar'},
        {'label': 'Clientes en riesgo', 'value': float(at_risk_total), 'format': 'int',
         'hint': 'Cayeron fuerte o dejaron de comprar — lista accionable abajo'},
        {'label': 'Frecuencia de compra',
         'value': round(ratio(order_count(dataframe), total_clients * months), 2),
         'format': 'decimal', 'hint': 'Pedidos por cliente por mes'},
    ]


def _empty_portfolio() -> Dict[str, Any]:
    '''
        Neutral payload used when the dataset cannot support the analysis.

        Returns:
            Dict[str, Any]: Empty sections with the same shape as a real result.
    '''
    return {'kpis': [], 'movimiento': [], 'en_riesgo': [], 'total_en_riesgo': 0}


def build_portfolio(dataframe: pd.DataFrame) -> Dict[str, Any]:
    '''
        Builds the portfolio-health report.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by ingest.

        Returns:
            Dict[str, Any]: 'kpis' (coverage, churn, frequency), 'movimiento'
                (new/recovered/retained/lost per month), 'en_riesgo' (actionable
                client list) and 'total_en_riesgo'. Empty sections instead of
                errors when the file lacks dates, amounts or client ids.
    '''
    parsed_dates = dates(dataframe)
    labels = label_series(dataframe, CLIENTE_ID, CLIENTE_NOMBRE)
    if parsed_dates is None or labels is None or MONTO not in dataframe.columns:
        message = 'Portfolio report skipped: missing date, client or amount column.'
        logger.info(message)
        return _empty_portfolio()

    monthly_sets = _monthly_client_sets(dataframe, parsed_dates, labels)
    if not monthly_sets:
        return _empty_portfolio()

    movement = _movement(monthly_sets)
    history = _client_history(dataframe, parsed_dates, labels)
    at_risk = _at_risk(history, parsed_dates.max())

    message = (f'Portfolio report: {len(history)} clients over {len(movement)} months, '
               f'{len(at_risk)} at risk.')
    logger.info(message)

    return {
        'kpis': _portfolio_kpis(history, movement, dataframe, len(at_risk)),
        'movimiento': movement,
        'en_riesgo': at_risk,
        'total_en_riesgo': len(at_risk)
    }
