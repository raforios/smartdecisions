'''
    Customer segmentation engine.

    Classifies each client into value tiers (Alto / Medio / Bajo) from a
    normalized sales DataFrame, so the sales team knows who to prioritize. The
    tiers are cut by monetary quantiles (top 20% -> Alto, next 30% -> Medio, rest
    -> Bajo), a simple and explainable RFM-style value split.

    Returns per-tier totals plus the list of clients (capped) so the frontend can
    show both a summary chart and an actionable table.
'''

import pandas as pd

from schemas.analytics import SegmentationBlock, SegmentClient, SegmentTier

from services.currency import money_row, money_sums
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

_AMOUNT = 'total_amount'
_CLIENT_ID = 'pos_id'
_CLIENT_NAME = 'pos_name'
_ORDER = 'order_id'

# Tier cut points on the cumulative client value (share of total sales).
# The OPTIMIZATION service colours every route stop by the same tiers, so it
# reads variables of these exact names. Change one, change both, or the same
# client shows as 'HIGH' on one screen and 'MEDIUM' on the other.
_SETTINGS = load_and_validate_env_vars({
    'SEGMENTATION_HIGH_TOP_SHARE': float,
    'SEGMENTATION_MEDIUM_TOP_SHARE': float,
    'SEGMENTATION_MAX_CLIENTS': int,
})
_ALTO_TOP_SHARE = _SETTINGS['SEGMENTATION_HIGH_TOP_SHARE']
_MEDIO_TOP_SHARE = _SETTINGS['SEGMENTATION_MEDIUM_TOP_SHARE']
_MAX_CLIENTS = _SETTINGS['SEGMENTATION_MAX_CLIENTS']

_TIER_ALTO = 'HIGH'
_TIER_MEDIO = 'MEDIUM'
_TIER_BAJO = 'LOW'
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


def _tier_summary(agg: pd.DataFrame) -> list[SegmentTier]:
    '''
        Clients, amount and share of each tier.

        Args:
            agg (pd.DataFrame): One row per client with its `tier` and its
                sums (`bob` and, with the month-close factors, the dollars).

        Returns:
            list[SegmentTier]: One row per tier, in the tier order; the share
                is measured in bolivianos.
    '''
    currencies = [column for column in ('bob', 'usd', 'usdt') if column in agg.columns]
    grand_total = float(agg['bob'].sum()) or 1.0
    summary = []
    for tier in _TIER_ORDER:
        subset = agg[agg['tier'] == tier]
        tier_sums = subset[currencies].sum()
        summary.append(SegmentTier(
            tier = tier,
            clients = int(len(subset)),
            amount = money_row(tier_sums),
            percentage = round(float(tier_sums['bob']) / grand_total * 100, 1)
        ))
    return summary


def build_segmentation(dataframe: pd.DataFrame) -> SegmentationBlock:
    '''
        Builds the customer value segmentation from a normalized sales frame.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.

        Returns:
            dict[str, Any]: 'tiers' (per-tier count, total and share) and
                'clients' (capped list of {client, tier, amount, compras}),
                highest value first.
    '''
    message = f'Building customer segmentation over {len(dataframe)} rows.'
    logger.info(message)

    if _AMOUNT not in dataframe.columns or _CLIENT_ID not in dataframe.columns:
        return SegmentationBlock()

    # Readable client label: name when available, else id.
    if _CLIENT_NAME in dataframe.columns:
        names = dataframe[_CLIENT_NAME].fillna('').astype(str).str.strip()
        labels = names.where(names != '', dataframe[_CLIENT_ID].astype(str))
    else:
        labels = dataframe[_CLIENT_ID].astype(str)

    work = dataframe.assign(_client = labels.values)
    # Ranked in bolivianos; each month's dollars at its close ride along.
    agg = work.groupby('_client').agg(
        purchases = (_ORDER, 'nunique') if _ORDER in work.columns else (_AMOUNT, 'size')
    ).join(money_sums(work, work[_AMOUNT], '_client')).sort_values('bob', ascending = False)

    total_clients = len(agg)
    if total_clients == 0:
        return SegmentationBlock()

    # Descending value rank ratio (0 = top spender) -> tier.
    ranks = range(total_clients)
    tiers = [_assign_tier(rank / total_clients) for rank in ranks]
    agg = agg.assign(tier = tiers)

    tier_summary = _tier_summary(agg)

    clients = [
        SegmentClient(
            client = str(idx),
            tier = row['tier'],
            amount = money_row(row),
            purchases = int(row['purchases'])
        )
        for idx, row in agg.head(_MAX_CLIENTS).iterrows()
    ]

    return SegmentationBlock(
        tiers = tier_summary,
        clients = clients,
        total_clients = total_clients
    )
