'''
    Concentration engine — how exposed the business is to a few names.

    Volume alone hides risk: two companies with the same revenue are not equally
    healthy if one of them bills half of it to three clients. This module makes
    that explicit with the measures a commercial analyst expects:

        * Share of the top 10 clients and the Pareto point (how few clients make
          80% of sales).
        * HHI, the standard concentration index, translated into plain language.

    The ABC of the catalogue used to live here and moved to `volume.py`: which
    products make the volume is a different question from who the revenue
    depends on, and answering both here kept the product tables split across
    two blocks of the dashboard.
'''
from typing import Optional

import pandas as pd

from schemas.analytics import ClientConcentration, ConcentrationBlock
from services.analytics_utils import (
    CLIENT_ID,
    CLIENT_NAME,
    AMOUNT,
    hhi_level,
    label_series,
    money,
    ratio
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

# Business thresholds: configurable per deployment, never literals in the code.
# The HHI cut points are borrowed from competition analysis and read here as
# "how much of the revenue depends on a handful of accounts".
_SETTINGS = load_and_validate_env_vars({
    'CONCENTRATION_PARETO_TARGET': float,
    'CONCENTRATION_TOP_CLIENTS': int,
    'CONCENTRATION_HHI_MODERATE': float,
    'CONCENTRATION_HHI_HIGH': float,
})
_PARETO_TARGET = _SETTINGS['CONCENTRATION_PARETO_TARGET']
_TOP_CLIENTS = _SETTINGS['CONCENTRATION_TOP_CLIENTS']
_HHI_MODERATE = _SETTINGS['CONCENTRATION_HHI_MODERATE']
_HHI_HIGH = _SETTINGS['CONCENTRATION_HHI_HIGH']

def _sorted_totals(
    dataframe: pd.DataFrame,
    labels: Optional[pd.Series]
) -> Optional[pd.Series]:
    '''
        Aggregates amounts by label, descending, dropping non-positive rows.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            labels (pd.Series | None): Readable label per row.

        Returns:
            pd.Series | None: Amount per label sorted high to low, or None when
                the frame cannot support the aggregation.
    '''
    if labels is None or AMOUNT not in dataframe.columns:
        return None
    totals = dataframe.assign(_label = labels.values).groupby('_label')[AMOUNT].sum()
    totals = totals[totals > 0].sort_values(ascending = False)
    return totals if not totals.empty else None


def _client_concentration(totals: pd.Series) -> ClientConcentration:
    '''
        Top-10 share, Pareto point and HHI over the client totals.

        Args:
            totals (pd.Series): Amount per client, descending.

        Returns:
            ClientConcentration: The concentration measures. The list of names
                behind them lives in the volume-source block, where each client
                travels with the product that anchors it.
    '''
    grand_total = float(totals.sum())
    shares = totals / grand_total
    cumulative = shares.cumsum()

    # How many clients are needed to reach 80% of sales.
    pareto_clients = int((cumulative < _PARETO_TARGET).sum()) + 1
    pareto_clients = min(pareto_clients, len(totals))
    hhi = float((shares ** 2).sum())

    return ClientConcentration(
        total_clients = int(len(totals)),
        top10_amount = money(totals.head(_TOP_CLIENTS).sum()),
        top10_percentage = round(ratio(totals.head(_TOP_CLIENTS).sum(), grand_total) * 100, 1),
        pareto_clients = pareto_clients,
        pareto_client_percentage = round(ratio(pareto_clients, len(totals)) * 100, 1),
        hhi = round(hhi, 4),
        hhi_level = hhi_level(hhi, _HHI_MODERATE, _HHI_HIGH).value
    )


def build_concentration(dataframe: pd.DataFrame) -> ConcentrationBlock:
    '''
        Builds the concentration block of the commercial summary.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by ingest.

        Returns:
            ConcentrationBlock: 'clients' with the top-10 share, the Pareto
                point and the HHI. Comes back empty rather than raising when
                the data cannot support it.
    '''
    client_totals = _sorted_totals(dataframe, label_series(dataframe, CLIENT_ID, CLIENT_NAME))

    client_count = 0 if client_totals is None else len(client_totals)
    message = f'Building concentration block ({client_count} clients).'
    logger.info(message)

    return ConcentrationBlock(
        clients = (
            _client_concentration(client_totals)
            if client_totals is not None else ClientConcentration()
        )
    )
