'''
    Customer segmentation engine.

    Classifies each client into value tiers (Alto / Medio / Bajo) from a
    normalized sales DataFrame, so the sales team knows who to prioritize. The
    tiers are cut by monetary quantiles (top 20% -> Alto, next 30% -> Medio, rest
    -> Bajo), a simple and explainable RFM-style value split.

    Returns per-tier totals plus the list of clients (capped) so the frontend can
    show both a summary chart and an actionable table.
'''
from typing import Any, Dict, List

import pandas as pd

from services.logger_config import custom_logger as logger

_MONTO = 'monto_total'
_CLIENTE_ID = 'id_punto_venta'
_CLIENTE_NOMBRE = 'nombre_pdv'
_PEDIDO = 'id_pedido'

# Tier cut points on the cumulative client value (share of total sales).
_ALTO_TOP_SHARE = 0.20   # top 20% of clients by value -> Alto
_MEDIO_TOP_SHARE = 0.50  # next 30% -> Medio; the rest -> Bajo
_MAX_CLIENTS = 500       # cap the returned client list (DynamoDB item / UI size)

_TIER_ALTO = 'Alto'
_TIER_MEDIO = 'Medio'
_TIER_BAJO = 'Bajo'
_TIER_ORDER = (_TIER_ALTO, _TIER_MEDIO, _TIER_BAJO)


def _assign_tier(rank_ratio: float) -> str:
    '''
        Maps a client's descending value-rank ratio (0 = highest spender) to a
        tier. The top 20% are Alto, the next 30% Medio, the remainder Bajo.
    '''
    if rank_ratio < _ALTO_TOP_SHARE:
        return _TIER_ALTO
    if rank_ratio < _MEDIO_TOP_SHARE:
        return _TIER_MEDIO
    return _TIER_BAJO


def build_segmentation(dataframe: pd.DataFrame) -> Dict[str, Any]:
    '''
        Builds the customer value segmentation from a normalized sales frame.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            Dict[str, Any]: 'tiers' (per-tier count, total and share) and
                'clientes' (capped list of {cliente, tier, monto, compras}),
                highest value first.
    '''
    message = f'Building customer segmentation over {len(dataframe)} rows.'
    logger.info(message)

    if _MONTO not in dataframe.columns or _CLIENTE_ID not in dataframe.columns:
        return {'tiers': [], 'clientes': [], 'total_clientes': 0}

    # Readable client label: name when available, else id.
    if _CLIENTE_NOMBRE in dataframe.columns:
        names = dataframe[_CLIENTE_NOMBRE].fillna('').astype(str).str.strip()
        labels = names.where(names != '', dataframe[_CLIENTE_ID].astype(str))
    else:
        labels = dataframe[_CLIENTE_ID].astype(str)

    work = dataframe.assign(_cliente = labels.values)
    agg = work.groupby('_cliente').agg(
        monto = (_MONTO, 'sum'),
        compras = (_PEDIDO, 'nunique') if _PEDIDO in work.columns else (_MONTO, 'size')
    ).sort_values('monto', ascending = False)

    total_clients = len(agg)
    if total_clients == 0:
        return {'tiers': [], 'clientes': [], 'total_clientes': 0}

    # Descending value rank ratio (0 = top spender) -> tier.
    ranks = range(total_clients)
    tiers = [_assign_tier(rank / total_clients) for rank in ranks]
    agg = agg.assign(tier = tiers)

    grand_total = float(agg['monto'].sum()) or 1.0
    tier_summary: List[Dict[str, Any]] = []
    for tier in _TIER_ORDER:
        subset = agg[agg['tier'] == tier]
        tier_summary.append({
            'tier': tier,
            'clientes': int(len(subset)),
            'monto': round(float(subset['monto'].sum()), 2),
            'porcentaje': round(float(subset['monto'].sum()) / grand_total * 100, 1),
        })

    clientes = [
        {
            'cliente': str(idx),
            'tier': row['tier'],
            'monto': round(float(row['monto']), 2),
            'compras': int(row['compras']),
        }
        for idx, row in agg.head(_MAX_CLIENTS).iterrows()
    ]

    return {
        'tiers': tier_summary,
        'clientes': clientes,
        'total_clientes': total_clients,
    }
