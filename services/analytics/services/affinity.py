'''
    Affinity × Drop Size engine — the SmartDecisions differentiator.

    Pipeline:
        1. Group the ingested sales DataFrame by `order_id` to form
           transactions (lists of products bought together).
        2. Run a lightweight, dependency-free Apriori to find frequent
           itemsets, then derive affinity rules with support, confidence
           and lift (same metrics as mlxtend, no scikit-learn/scipy weight).
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
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from schemas.analytics import AnalyticsSummary, Opportunity

from services.logger_config import custom_logger as logger


PRODUCT_NAMES_KEY = 'product_names'
PDV_NAMES_KEY = 'pdv_names'

_RULE_COLUMNS = ['antecedents', 'consequents', 'support', 'confidence', 'lift']


@dataclass
class _EngineData:
    '''
        Read-only bundle of the pre-computed indices shared across every PdV
        while building opportunities.
    '''
    rules: pd.DataFrame
    avg_units: pd.Series
    avg_amount: pd.Series
    product_names: Dict[str, str]
    pdv_names: Dict[str, str]


@dataclass
class _PdvBasket:
    '''
        A single point of sale together with the set of products it already
        buys — the unit of work for `_candidates_for_pdv`.
    '''
    pdv_id: str
    pdv_name: Optional[str]
    products_bought: set


def _build_transactions(dataframe: pd.DataFrame) -> List[List[str]]:
    '''
        Groups the sales dataframe by `order_id` and returns one list of
        product SKUs per transaction. Duplicate products in the same order
        are collapsed, since market-basket support counts itemsets as sets,
        not multisets.

        Args:
            dataframe (pd.DataFrame): Sales rows (one product per row).

        Returns:
            List[List[str]]: Transactions as lists of unique product SKUs.
    '''
    grouped = dataframe.groupby('order_id')['product_id'].apply(
        lambda values: sorted({str(value) for value in values})
    )
    return [products for products in grouped.tolist() if products]


def _count_singletons(transaction_sets: List[frozenset]) -> Dict[frozenset, int]:
    '''
        Counts how many transactions contain each single product.
    '''
    counts: Dict[frozenset, int] = {}
    for items in transaction_sets:
        for item in items:
            single = frozenset((item,))
            counts[single] = counts.get(single, 0) + 1
    return counts


def _generate_candidates(
    previous_frequent: List[frozenset],
    size: int
) -> set:
    '''
        Builds candidate k-itemsets from frequent (k-1)-itemsets and prunes
        them with the Apriori property: every (k-1)-subset must be frequent.
    '''
    frequent = set(previous_frequent)
    candidates: set = set()
    for left, right in combinations(previous_frequent, 2):
        union = left | right
        if len(union) != size:
            continue
        if all(frozenset(subset) in frequent
               for subset in combinations(union, size - 1)):
            candidates.add(union)
    return candidates


def _count_supersets(
    transaction_sets: List[frozenset],
    candidates: set
) -> Dict[frozenset, int]:
    '''
        Counts, for each candidate itemset, the transactions that contain it.
    '''
    candidate_counts: Dict[frozenset, int] = {candidate: 0 for candidate in candidates}
    for items in transaction_sets:
        for candidate in candidates:
            if candidate <= items:
                candidate_counts[candidate] += 1
    return candidate_counts


def _frequent_itemsets(
    transactions: List[List[str]],
    min_support: float
) -> Dict[frozenset, float]:
    '''
        Apriori frequent-itemset mining without external dependencies.

        Args:
            transactions (List[List[str]]): One list of unique SKUs per order.
            min_support (float): Minimum fraction of transactions (0..1).

        Returns:
            Dict[frozenset, float]: Frequent itemsets mapped to their support.
    '''
    total = len(transactions)
    if total == 0:
        return {}

    transaction_sets = [frozenset(items) for items in transactions]
    min_count = min_support * total

    current = {
        itemset: count
        for itemset, count in _count_singletons(transaction_sets).items()
        if count >= min_count
    }
    supports: Dict[frozenset, float] = dict(current)

    size = 2
    while current:
        candidates = _generate_candidates(list(current.keys()), size)
        if not candidates:
            break
        candidate_counts = _count_supersets(transaction_sets, candidates)
        current = {
            itemset: count
            for itemset, count in candidate_counts.items()
            if count >= min_count
        }
        supports.update(current)
        size += 1

    return {itemset: count / total for itemset, count in supports.items()}


def _rules_from_itemset(
    itemset: frozenset,
    itemset_support: float,
    supports: Dict[frozenset, float],
    min_lift: float
) -> List[Opportunity]:
    '''
        Evaluates every non-empty antecedent → consequent partition of a
        single frequent itemset and keeps the rules whose lift reaches
        `min_lift`.
    '''
    rules: List[Dict[str, Any]] = []
    items = sorted(itemset)
    for antecedent_size in range(1, len(items)):
        for antecedent_items in combinations(items, antecedent_size):
            antecedents = frozenset(antecedent_items)
            consequents = itemset - antecedents
            antecedent_support = supports.get(antecedents)
            consequent_support = supports.get(consequents)
            if not antecedent_support or not consequent_support:
                continue
            confidence = itemset_support / antecedent_support
            lift = confidence / consequent_support
            if lift < min_lift:
                continue
            rules.append({
                'antecedents': antecedents,
                'consequents': consequents,
                'support': itemset_support,
                'confidence': confidence,
                'lift': lift
            })
    return rules


def _compute_affinity_rules(
    transactions: List[List[str]],
    min_support: float,
    min_lift: float
) -> pd.DataFrame:
    '''
        Derives association rules from the frequent itemsets and returns the
        rule table with columns
        `[antecedents, consequents, support, confidence, lift]`.

        For every frequent itemset of size >= 2 it evaluates each non-empty
        antecedent → consequent partition, computing the same metrics mlxtend
        produced:
            support    = support(antecedents ∪ consequents)
            confidence = support(itemset) / support(antecedents)
            lift       = confidence / support(consequents)
        Rules are kept when `lift >= min_lift`.
    '''
    supports = _frequent_itemsets(transactions, min_support)
    if not supports:
        return pd.DataFrame(columns = _RULE_COLUMNS)

    records: List[Dict[str, Any]] = []
    for itemset, itemset_support in supports.items():
        if len(itemset) >= 2:
            records.extend(
                _rules_from_itemset(itemset, itemset_support, supports, min_lift)
            )

    if not records:
        return pd.DataFrame(columns = _RULE_COLUMNS)
    return pd.DataFrame(records, columns = _RULE_COLUMNS)


def _compute_drop_size(dataframe: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
    '''
        For each product, computes:
            - avg units per transaction (quantity)
            - avg amount per transaction (total_amount), if available

        Args:
            dataframe (pd.DataFrame): Sales rows.

        Returns:
            Tuple[pd.Series, pd.Series]: (avg_units_by_product, avg_amount_by_product).
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


def _build_product_name_index(dataframe: pd.DataFrame) -> Dict[str, str]:
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


def _build_pdv_name_index(dataframe: pd.DataFrame) -> Dict[str, str]:
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


def _index_pdv_products(dataframe: pd.DataFrame) -> Dict[str, set]:
    '''
        Maps each pos_id to the set of product SKUs it already buys.
    '''
    return (
        dataframe.assign(product_id = dataframe['product_id'].astype(str))
                 .groupby('pos_id')['product_id']
                 .apply(set)
                 .to_dict()
    )


def _drop_size_for(consequent_id: str, data: _EngineData) -> Tuple[float, Optional[float]]:
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
    rule: pd.Series,
    consequent_id: str,
    antecedents: set,
    data: _EngineData
) -> Dict[str, Any]:
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


def _candidates_for_pdv(basket: _PdvBasket, data: _EngineData) -> List[Opportunity]:
    '''
        Builds every candidate opportunity for a single PdV: rules only fire
        when the PdV already buys all antecedents, and products it already
        buys are never recommended.
    '''
    candidates: List[Dict[str, Any]] = []
    for _, rule in data.rules.iterrows():
        antecedents = set(rule['antecedents'])
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
    candidates: List[Dict[str, Any]],
    top_n: int
) -> List[Opportunity]:
    '''
        Collapses duplicate (pdv, product) candidates keeping the highest
        score — a product can be the consequent of several rules for the same
        PdV — then returns the top N by opportunity score.
    '''
    deduped: Dict[str, Opportunity] = {}
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
) -> List[Opportunity]:
    '''
        Iterates over every PdV, builds and ranks its candidates and returns
        the flattened opportunity list.
    '''
    opportunities: List[Opportunity] = []
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
    opportunities: List[Opportunity],
    rules_count: int,
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
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


def _apply_item_level(dataframe: pd.DataFrame, item_level: str) -> pd.DataFrame:
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
    min_support: float = 0.01,
    min_lift: float = 1.0,
    top_n_per_pdv: int = 10,
    item_level: str = 'product'
) -> Tuple[List[Opportunity], AnalyticsSummary]:
    '''
        End-to-end orchestration. Returns the opportunity list + summary stats.

        Args:
            dataframe (pd.DataFrame): Validated sales rows from ingest.
            min_support (float): Apriori minimum support (0..1).
            min_lift (float): association_rules lift threshold (>= 1 = no anti-correlation).
            top_n_per_pdv (int): Max opportunities returned per PdV.
            item_level (str): Basket granularity — 'category' (default in the
                controller for mass-consumption data) or 'product' (SKU).

        Returns:
            Tuple[List[Opportunity], AnalyticsSummary]:
                - Flat list of Opportunity dicts (ready to wrap in the schema).
                - Summary dict with run-level stats and the parameters used.
    '''
    working = _apply_item_level(dataframe, item_level)
    transactions = _build_transactions(working)
    rules = _compute_affinity_rules(transactions, min_support, min_lift)
    avg_units, avg_amount = _compute_drop_size(working)
    data = _EngineData(
        rules = rules,
        avg_units = avg_units,
        avg_amount = avg_amount,
        product_names = _build_product_name_index(working),
        pdv_names = _build_pdv_name_index(working)
    )
    parameters = {
        'min_support': min_support,
        'min_lift': min_lift,
        'top_n_per_pdv': top_n_per_pdv,
        'item_level': item_level
    }

    if rules.empty:
        message = 'Affinity rules table is empty; returning zero opportunities.'
        logger.info(message)
        return [], _build_summary([], 0, parameters)

    opportunities = _collect_opportunities(working, data, top_n_per_pdv)
    summary = _build_summary(opportunities, len(rules), parameters)

    message = (
        f'Affinity engine produced {summary.total_opportunities} opportunities '
        f'across {summary.total_pos_with_opportunities} PdVs from '
        f'{summary.affinity_rules_evaluated} rules.'
    )
    logger.info(message)

    return opportunities, summary
