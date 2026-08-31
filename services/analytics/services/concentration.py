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
from typing import Any, Dict, Optional

import pandas as pd

from schemas.analytics import (
    AbcBlock,
    ClientConcentration,
    ConcentrationBlock,
    ConcentrationLevel,
    DistRow
)
from services.analytics_utils import (
    CLIENT_ID,
    CLIENT_NAME,
    AMOUNT,
    PRODUCT_ID,
    PRODUCT_NAME,
    label_series,
    money,
    ratio,
    setting
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

# Business thresholds: configurable per deployment, never literals in the code.
# The HHI cut points are borrowed from competition analysis and read here as
# "how much of the revenue depends on a handful of accounts".
_SETTINGS = load_and_validate_env_vars({}, optional_env_vars = {
    'CONCENTRATION_PARETO_TARGET': float,
    'CONCENTRATION_ABC_A_LIMIT': float,
    'CONCENTRATION_ABC_B_LIMIT': float,
    'CONCENTRATION_TOP_CLIENTS': int,
    'CONCENTRATION_MAX_ABC_ROWS': int,
    'CONCENTRATION_HHI_MODERATE': float,
    'CONCENTRATION_HHI_HIGH': float,
})
_PARETO_TARGET = setting(_SETTINGS, 'CONCENTRATION_PARETO_TARGET', 0.80)
_ABC_A_LIMIT = setting(_SETTINGS, 'CONCENTRATION_ABC_A_LIMIT', 0.80)
_ABC_B_LIMIT = setting(_SETTINGS, 'CONCENTRATION_ABC_B_LIMIT', 0.95)
_TOP_CLIENTS = setting(_SETTINGS, 'CONCENTRATION_TOP_CLIENTS', 10)
_MAX_ABC_ROWS = setting(_SETTINGS, 'CONCENTRATION_MAX_ABC_ROWS', 300)
_HHI_MODERATE = setting(_SETTINGS, 'CONCENTRATION_HHI_MODERATE', 0.15)
_HHI_HIGH = setting(_SETTINGS, 'CONCENTRATION_HHI_HIGH', 0.25)

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
    if labels is None or AMOUNT not in dataframe.columns:
        return None
    totals = dataframe.assign(_label = labels.values).groupby('_label')[AMOUNT].sum()
    totals = totals[totals > 0].sort_values(ascending = False)
    return totals if not totals.empty else None


def _hhi_level(index: float) -> ConcentrationLevel:
    '''
        Classifies an HHI value into a concentration level.

        Args:
            index (float): Herfindahl-Hirschman index between 0 and 1.

        Returns:
            ConcentrationLevel: The level code; the UI words it.
    '''
    if index >= _HHI_HIGH:
        return ConcentrationLevel.HIGH
    if index >= _HHI_MODERATE:
        return ConcentrationLevel.MODERATE
    return ConcentrationLevel.LOW


def _client_concentration(totals: pd.Series) -> Dict[str, Any]:
    '''
        Top-10 share, Pareto point and HHI over the client totals.

        Args:
            totals (pd.Series): Amount per client, descending.

        Returns:
            ClientConcentration: Concentration measures plus the top-10 rows.
    '''
    grand_total = float(totals.sum())
    shares = totals / grand_total
    cumulative = shares.cumsum()

    # How many clients are needed to reach 80% of sales.
    pareto_clients = int((cumulative < _PARETO_TARGET).sum()) + 1
    pareto_clients = min(pareto_clients, len(totals))
    top_rows = [
        DistRow(
            label = str(label),
            amount = money(amount),
            percentage = round(ratio(amount, grand_total) * 100, 2)
        )
        for label, amount in totals.head(_TOP_CLIENTS).items()
    ]
    hhi = float((shares ** 2).sum())

    return ClientConcentration(
        total_clients = int(len(totals)),
        top10_amount = money(totals.head(_TOP_CLIENTS).sum()),
        top10_percentage = round(ratio(totals.head(_TOP_CLIENTS).sum(), grand_total) * 100, 1),
        pareto_clients = pareto_clients,
        pareto_client_percentage = round(ratio(pareto_clients, len(totals)) * 100, 1),
        hhi = round(hhi, 4),
        hhi_level = _hhi_level(hhi).value,
        top_clients = top_rows
    )


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
        'amount': [money(amount) for amount in totals.values],
        'abc_class': classes,
        'cumulative': [round(value * 100, 2) for value in cumulative.values]
    })

    summary = []
    for abc_class in ('A', 'B', 'C'):
        rows = frame.loc[frame['abc_class'] == abc_class]
        class_amount = rows['amount'].sum()
        summary.append({
            'abc_class': abc_class,
            'products': int(len(rows)),
            'amount': money(class_amount),
            'percentage': round(ratio(class_amount, grand_total) * 100, 1)
        })
    return {'summary': summary, 'products': frame.head(_MAX_ABC_ROWS).to_dict('records')}


def build_concentration(dataframe: pd.DataFrame) -> ConcentrationBlock:
    '''
        Builds the concentration block of the commercial summary.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows as produced by ingest.

        Returns:
            Dict[str, Any]: 'clients' (top-10 share, Pareto point, HHI) and
                'abc' (product classification). Sections the data cannot
                support come back empty rather than raising.
    '''
    client_totals = _sorted_totals(dataframe, label_series(dataframe, CLIENT_ID, CLIENT_NAME))
    product_totals = _sorted_totals(
        dataframe, label_series(dataframe, PRODUCT_ID, PRODUCT_NAME))

    client_count = 0 if client_totals is None else len(client_totals)
    product_count = 0 if product_totals is None else len(product_totals)
    message = f'Building concentration block ({client_count} clients, {product_count} products).'
    logger.info(message)

    return ConcentrationBlock(
        clients = (
            _client_concentration(client_totals)
            if client_totals is not None else ClientConcentration()
        ),
        abc = (
            AbcBlock(**_abc_products(product_totals))
            if product_totals is not None else AbcBlock()
        )
    )
