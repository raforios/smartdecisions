'''
    Concentration engine — how exposed the business is to a few names.

    Volume alone hides risk: two companies with the same revenue are not equally
    healthy if one of them bills half of it to three clients. This module makes
    that explicit with the measures a commercial analyst expects:

        * Share of the top 10 clients and the Pareto point (how few clients make
          80% of sales).
        * HHI, the standard concentration index, translated into plain language.
        * ABC classification of products (A = first 80% of sales, B = next 15%,
          C = the long tail) to separate the core catalogue from the noise.
'''
from typing import Any, Dict, List, Optional

import pandas as pd

from services.frame_utils import (
    CLIENTE_ID,
    CLIENTE_NOMBRE,
    MONTO,
    PRODUCTO_ID,
    PRODUCTO_NOMBRE,
    label_series,
    money,
    ratio
)
from services.logger_config import custom_logger as logger

_PARETO_TARGET = 0.80   # share of sales that defines the Pareto core
_ABC_A_LIMIT = 0.80     # cumulative share closing class A
_ABC_B_LIMIT = 0.95     # cumulative share closing class B
_TOP_CLIENTS = 10
_MAX_ABC_ROWS = 300     # cap the returned product list (UI + payload size)

# HHI thresholds borrowed from competition analysis, read here as "how much of
# the revenue depends on a handful of accounts".
_HHI_MODERATE = 0.15
_HHI_HIGH = 0.25

_ABC_DESCRIPTIONS = {
    'A': 'Núcleo del negocio: concentran el 80% de la venta. Nunca deben quebrar stock.',
    'B': 'Complementarios: aportan el siguiente 15%. Mantener con rotación controlada.',
    'C': 'Cola larga: el 5% restante. Candidatos a depurar o vender bajo pedido.'
}


def _sorted_totals(dataframe: pd.DataFrame, labels: Optional[pd.Series]) -> Optional[pd.Series]:
    '''
        Aggregates amounts by label, descending, dropping non-positive rows.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            labels (pd.Series | None): Readable label per row.

        Returns:
            pd.Series | None: Amount per label sorted high to low, or None when
                the frame cannot support the aggregation.
    '''
    if labels is None or MONTO not in dataframe.columns:
        return None
    totals = dataframe.assign(_label = labels.values).groupby('_label')[MONTO].sum()
    totals = totals[totals > 0].sort_values(ascending = False)
    return totals if not totals.empty else None


def _hhi_label(index: float) -> str:
    '''
        Translates an HHI value into the sentence a manager can act on.

        Args:
            index (float): Herfindahl-Hirschman index between 0 and 1.

        Returns:
            str: Plain-language reading of the concentration level.
    '''
    if index >= _HHI_HIGH:
        return 'Alta: la venta depende de muy pocos clientes.'
    if index >= _HHI_MODERATE:
        return 'Moderada: hay dependencia de algunos clientes clave.'
    return 'Baja: la venta está bien repartida entre los clientes.'


def _client_concentration(totals: pd.Series) -> Dict[str, Any]:
    '''
        Top-10 share, Pareto point and HHI over the client totals.

        Args:
            totals (pd.Series): Amount per client, descending.

        Returns:
            Dict[str, Any]: Concentration measures plus the top-10 rows.
    '''
    grand_total = float(totals.sum())
    shares = totals / grand_total
    cumulative = shares.cumsum()

    # How many clients are needed to reach 80% of sales.
    pareto_clients = int((cumulative < _PARETO_TARGET).sum()) + 1
    pareto_clients = min(pareto_clients, len(totals))
    top_rows = [
        {'label': str(label), 'monto': money(amount),
         'porcentaje': round(ratio(amount, grand_total) * 100, 2)}
        for label, amount in totals.head(_TOP_CLIENTS).items()
    ]
    hhi = float((shares ** 2).sum())

    return {
        'total_clientes': int(len(totals)),
        'top10_monto': money(totals.head(_TOP_CLIENTS).sum()),
        'top10_porcentaje': round(ratio(totals.head(_TOP_CLIENTS).sum(), grand_total) * 100, 1),
        'pareto_clientes': pareto_clients,
        'pareto_porcentaje_clientes': round(ratio(pareto_clients, len(totals)) * 100, 1),
        'hhi': round(hhi, 4),
        'hhi_lectura': _hhi_label(hhi),
        'top_clientes': top_rows
    }


def _abc_products(totals: pd.Series) -> Dict[str, Any]:
    '''
        Classifies products into A/B/C by cumulative share of sales.

        Args:
            totals (pd.Series): Amount per product, descending.

        Returns:
            Dict[str, Any]: Per-class counts and amounts plus the (capped)
                classified product rows.
    '''
    grand_total = float(totals.sum())
    cumulative = (totals / grand_total).cumsum()

    def _class_of(accumulated: float) -> str:
        if accumulated <= _ABC_A_LIMIT:
            return 'A'
        if accumulated <= _ABC_B_LIMIT:
            return 'B'
        return 'C'

    classes = [_class_of(value) for value in cumulative]
    frame = pd.DataFrame({
        'label': [str(label) for label in totals.index],
        'monto': [money(amount) for amount in totals.values],
        'clase': classes,
        'acumulado': [round(value * 100, 2) for value in cumulative.values]
    })

    resumen = [
        {
            'clase': clase,
            'productos': int((frame['clase'] == clase).sum()),
            'monto': money(frame.loc[frame['clase'] == clase, 'monto'].sum()),
            'porcentaje': round(
                ratio(frame.loc[frame['clase'] == clase, 'monto'].sum(), grand_total) * 100, 1),
            'descripcion': _ABC_DESCRIPTIONS[clase]
        }
        for clase in ('A', 'B', 'C')
    ]
    return {'resumen': resumen, 'productos': frame.head(_MAX_ABC_ROWS).to_dict('records')}


def build_concentration(dataframe: pd.DataFrame) -> Dict[str, Any]:
    '''
        Builds the concentration block of the commercial summary.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by ingest.

        Returns:
            Dict[str, Any]: 'clientes' (top-10 share, Pareto point, HHI) and
                'abc' (product classification). Sections the data cannot
                support come back empty rather than raising.
    '''
    client_totals = _sorted_totals(dataframe, label_series(dataframe, CLIENTE_ID, CLIENTE_NOMBRE))
    product_totals = _sorted_totals(
        dataframe, label_series(dataframe, PRODUCTO_ID, PRODUCTO_NOMBRE))

    client_count = 0 if client_totals is None else len(client_totals)
    product_count = 0 if product_totals is None else len(product_totals)
    message = f'Building concentration block ({client_count} clients, {product_count} products).'
    logger.info(message)

    return {
        'clientes': _client_concentration(client_totals) if client_totals is not None else {},
        'abc': _abc_products(product_totals) if product_totals is not None else {}
    }
