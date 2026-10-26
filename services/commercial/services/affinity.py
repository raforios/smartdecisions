'''
    Affinity × Drop Size engine — the SmartDecisions differentiator.

    Pipeline:
        1. Group the ingested sales DataFrame by `order_id` to form
           transactions (lists of products bought together).
        2. Ask ML_FUNCTIONS for the association rules of those
           transactions (Apriori, with support, confidence and lift): the
           one copy of the algorithm lives there since 24-oct-2026.
        3. Per PdV: identify which products the PdV already buys and which
           association rules apply.
        4. For each candidate consequent (product the PdV doesn't yet buy),
           weight the rule's score by the **expected drop size** of that
           product (avg units sold per transaction × avg unit price).
        5. Return the top N opportunities per PdV, ranked by monetary impact.

    Output is a flat list of `Opportunity` dicts ready to be wrapped in the
    public schema.
'''
from dataclasses import dataclass
from typing import Any

import pandas as pd

from schemas.analytics import AnalyticsError, AnalyticsSummary, Opportunity

from services.calculations import ask_ml_functions
from services.logger_config import custom_logger as logger


PRODUCT_NAMES_KEY = 'product_names'
PDV_NAMES_KEY = 'pdv_names'



@dataclass(frozen = True)
class AffinitySettings:
    '''
        How the engine runs: the Apriori thresholds, how many opportunities
        each point of sale keeps and the basket item ('category' or 'product').
    '''
    min_support: float
    min_lift: float
    top_n_per_pdv: int
    item_level: str


@dataclass
class _EngineData:
    '''
        Read-only bundle of the pre-computed indices shared across every PdV
        while building opportunities.
    '''
    rules: list[dict[str, Any]]
    avg_units: pd.Series
    avg_amount: pd.Series
    product_names: dict[str, str]
    pdv_names: dict[str, str]


@dataclass
class _PdvBasket:
    '''
        A single point of sale together with the set of products it already
        buys — the unit of work for `_candidates_for_pdv`.
    '''
    pdv_id: str
    pdv_name: str | None
    products_bought: set


def _build_transactions(dataframe: pd.DataFrame) -> list[list[str]]:
    '''
        Groups the sales dataframe by `order_id` and returns one list of
        product SKUs per transaction. Duplicate products in the same order
        are collapsed, since market-basket support counts itemsets as sets,
        not multisets.

        Args:
            dataframe (pd.DataFrame): Sales rows (one product per row).

        Returns:
            list[list[str]]: Transactions as lists of unique product SKUs.
    '''
    grouped = dataframe.groupby('order_id')['product_id'].apply(
        lambda values: sorted({str(value) for value in values})
    )
    return [products for products in grouped.tolist() if products]


def _affinity_rules(
    transactions: list[list[str]],
    settings: AffinitySettings,
    auth_token: str
) -> list[dict[str, Any]]:
    '''
        The association rules of the transactions, asked of ML_FUNCTIONS, as
        records whose antecedents and consequents are sets: the PdV loop
        checks them against what each PdV buys.

        Args:
            transactions (list[list[str]]): One list of unique items per order.
            settings (AffinitySettings): The Apriori thresholds.
            auth_token (str): The caller's Authorization header.

        Returns:
            list[dict[str, Any]]: antecedents, consequents, support, confidence, lift.
    '''
    if not transactions:
        return []
    answer = ask_ml_functions(
        '/v1/classification/association-rules',
        {'transactions': transactions, 'min_support': settings.min_support,
         'min_lift': settings.min_lift},
        auth_token, AnalyticsError.CALCULATION_UNAVAILABLE.value)
    return [{**rule, 'antecedents': frozenset(rule['antecedents']),
             'consequents': frozenset(rule['consequents'])} for rule in answer['rules']]


def _compute_drop_size(dataframe: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    '''
        For each product, computes:
            - avg units per transaction (quantity)
            - avg amount per transaction (total_amount), if available

        Args:
            dataframe (pd.DataFrame): Sales rows.

        Returns:
            tuple[pd.Series, pd.Series]: (avg_units_by_product, avg_amount_by_product).
            Both indexed by product_id. The amount series can be all-NaN when
            the source did not provide pricing.
    '''
    grouped = dataframe.groupby(['order_id', 'product_id']).agg(
        quantity = ('quantity', 'sum'),
        total_amount = ('total_amount', 'sum')
    ).reset_index()

    avg_units = grouped.groupby('product_id')['quantity'].mean()
    avg_amount = grouped.groupby('product_id')['total_amount'].mean()
    return avg_units, avg_amount


def _build_product_name_index(dataframe: pd.DataFrame) -> dict[str, str]:
    '''
        Builds a stable product_id → product_name map for the UI layer.
    '''
    if 'product_name' not in dataframe.columns:
        return {}
    pairs = dataframe[['product_id', 'product_name']].dropna()
    return {
        str(row['product_id']): str(row['product_name'])
        for _, row in pairs.drop_duplicates(subset = ['product_id']).iterrows()
    }


def _build_pdv_name_index(dataframe: pd.DataFrame) -> dict[str, str]:
    '''
        Builds a stable pos_id → pos_name map for the UI layer.
    '''
    if 'pos_name' not in dataframe.columns:
        return {}
    pairs = dataframe[['pos_id', 'pos_name']].dropna()
    return {
        str(row['pos_id']): str(row['pos_name'])
        for _, row in pairs.drop_duplicates(subset = ['pos_id']).iterrows()
    }


def _index_pdv_products(dataframe: pd.DataFrame) -> dict[str, set]:
    '''
        Maps each pos_id to the set of product SKUs it already buys.
    '''
    return (
        dataframe.assign(product_id = dataframe['product_id'].astype(str))
                 .groupby('pos_id')['product_id']
                 .apply(set)
                 .to_dict()
    )


def _drop_size_for(
    consequent_id: str,
    data: _EngineData
) -> tuple[float, float | None]:
    '''
        Returns (expected units, expected amount) for a recommended product.
        The amount is None when the source provided no pricing.
    '''
    drop_units = float(data.avg_units.get(consequent_id, 0.0) or 0.0)
    raw_amount = data.avg_amount.get(consequent_id)
    drop_amount = (
        float(raw_amount)
        if raw_amount is not None and not pd.isna(raw_amount)
        else None
    )
    return drop_units, drop_amount


def _build_candidate(
    basket: _PdvBasket,
    rule: dict[str, Any],
    consequent_id: str,
    antecedents: set,
    data: _EngineData
) -> dict[str, Any]:
    '''
        Materializes a single opportunity dict for a (PdV, recommended
        product) pair, scoring it by monetary impact when prices exist and
        falling back to volume otherwise.
    '''
    drop_units, drop_amount = _drop_size_for(consequent_id, data)
    ranking_weight = drop_amount if drop_amount is not None else drop_units
    opportunity_score = float(rule['lift']) * float(rule['confidence']) * ranking_weight

    antecedent_ids = sorted(antecedents)
    antecedent_names = [data.product_names.get(aid, aid) for aid in antecedent_ids]

    return Opportunity(
        pdv_id = basket.pdv_id,
        pdv_name = basket.pdv_name,
        recommended_product_id = consequent_id,
        recommended_product_name = data.product_names.get(consequent_id),
        based_on_products = antecedent_ids,
        based_on_product_names = antecedent_names,
        support = float(rule['support']),
        confidence = float(rule['confidence']),
        lift = float(rule['lift']),
        expected_drop_size_units = round(drop_units, 4),
        expected_drop_size_amount = (
            round(drop_amount, 4) if drop_amount is not None else None
        ),
        opportunity_score = round(opportunity_score, 4)
    )


def _candidates_for_pdv(
    basket: _PdvBasket,
    data: _EngineData
) -> list[Opportunity]:
    '''
        Builds every candidate opportunity for a single PdV: rules only fire
        when the PdV already buys all antecedents, and products it already
        buys are never recommended.

        The rules arrive as plain records, not as the DataFrame: this loop runs
        once per rule for every PdV, and `iterrows()` builds a Series per row.
        With 11 180 rules and 274 PdVs that was 118 s on the Lambda, past the
        29 s API Gateway limit, so the screen answered "Service Unavailable".
    '''
    candidates: list[dict[str, Any]] = []
    for rule in data.rules:
        antecedents = rule['antecedents']
        if not antecedents.issubset(basket.products_bought):
            continue
        for consequent_id in set(rule['consequents']):
            if consequent_id in basket.products_bought:
                continue
            candidates.append(
                _build_candidate(basket, rule, consequent_id, antecedents, data)
            )
    return candidates


def _dedupe_and_rank(
    candidates: list[dict[str, Any]],
    top_n: int
) -> list[Opportunity]:
    '''
        Collapses duplicate (pdv, product) candidates keeping the highest
        score — a product can be the consequent of several rules for the same
        PdV — then returns the top N by opportunity score.
    '''
    deduped: dict[str, Opportunity] = {}
    for candidate in candidates:
        key = candidate.recommended_product_id
        existing = deduped.get(key)
        if existing is None or candidate.opportunity_score > existing.opportunity_score:
            deduped[key] = candidate

    return sorted(
        deduped.values(),
        key = lambda item: item.opportunity_score,
        reverse = True
    )[:top_n]


def _collect_opportunities(
    dataframe: pd.DataFrame,
    data: _EngineData,
    top_n_per_pdv: int
) -> list[Opportunity]:
    '''
        Iterates over every PdV, builds and ranks its candidates and returns
        the flattened opportunity list.
    '''
    opportunities: list[Opportunity] = []
    for pdv_id, products_bought in _index_pdv_products(dataframe).items():
        pdv_id_str = str(pdv_id)
        basket = _PdvBasket(
            pdv_id = pdv_id_str,
            pdv_name = data.pdv_names.get(pdv_id_str),
            products_bought = products_bought
        )
        candidates = _candidates_for_pdv(basket, data)
        opportunities.extend(_dedupe_and_rank(candidates, top_n_per_pdv))
    return opportunities


def _build_summary(
    opportunities: list[Opportunity],
    rules_count: int,
    parameters: dict[str, Any]
) -> dict[str, Any]:
    '''
        Aggregates the run-level statistics returned alongside the
        opportunities.
    '''
    amounts = [
        opp.expected_drop_size_amount
        for opp in opportunities
        if opp.expected_drop_size_amount is not None
    ]
    total_expected_value = round(sum(amounts), 2) if amounts else None
    pdvs_with_opps = {opp.pdv_id for opp in opportunities}
    return AnalyticsSummary(
        total_pos_with_opportunities = len(pdvs_with_opps),
        total_opportunities = len(opportunities),
        total_expected_value = total_expected_value,
        affinity_rules_evaluated = int(rules_count),
        parameters = parameters
    )


def _apply_item_level(
    dataframe: pd.DataFrame,
    item_level: str
) -> pd.DataFrame:
    '''
        Chooses the granularity of the market-basket item. At SKU level ('product')
        real retail baskets are too sparse to yield rules (thousands of unique SKUs
        across mostly-singleton invoices), so 'category' aliases the product
        identity to the product category — far denser and more interpretable
        ('recommend Chocolates'). Returns the frame the engine analyzes.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            item_level (str): 'category' or 'product'.

        Returns:
            pd.DataFrame: The frame to analyze (a category-aliased copy, or the
                input unchanged for SKU level / when no category column exists).
    '''
    if item_level != 'category' or 'category' not in dataframe.columns:
        return dataframe
    category = dataframe['category'].fillna('').astype(str)
    return dataframe.assign(product_id = category, product_name = category)


def compute_opportunities(
    dataframe: pd.DataFrame,
    settings: AffinitySettings,
    auth_token: str
) -> tuple[list[Opportunity], AnalyticsSummary]:
    '''
        End-to-end orchestration. Returns the opportunity list + summary stats.

        Args:
            dataframe (pd.DataFrame): Validated sales rows from ingest.
            settings (AffinitySettings): Thresholds, opportunities per PdV and
                basket granularity — 'category' (default in the controller for
                mass-consumption data) or 'product' (SKU).
            auth_token (str): The caller's Authorization header, for ML_FUNCTIONS.

        Returns:
            tuple[list[Opportunity], AnalyticsSummary]:
                - Flat list of Opportunity dicts (ready to wrap in the schema).
                - Summary dict with run-level stats and the parameters used.
    '''
    working = _apply_item_level(dataframe, settings.item_level)
    rules = _affinity_rules(_build_transactions(working), settings, auth_token)
    parameters = {
        'min_support': settings.min_support,
        'min_lift': settings.min_lift,
        'top_n_per_pdv': settings.top_n_per_pdv,
        'item_level': settings.item_level
    }

    if not rules:
        message = 'Affinity rules table is empty; returning zero opportunities.'
        logger.info(message)
        return [], _build_summary([], 0, parameters)

    avg_units, avg_amount = _compute_drop_size(working)
    data = _EngineData(
        rules = rules,
        avg_units = avg_units,
        avg_amount = avg_amount,
        product_names = _build_product_name_index(working),
        pdv_names = _build_pdv_name_index(working)
    )
    opportunities = _collect_opportunities(working, data, settings.top_n_per_pdv)
    summary = _build_summary(opportunities, len(rules), parameters)

    message = (
        f'Affinity engine produced {summary.total_opportunities} opportunities '
        f'across {summary.total_pos_with_opportunities} PdVs from '
        f'{summary.affinity_rules_evaluated} rules.'
    )
    logger.info(message)

    return opportunities, summary
