'''
    Affinity × Drop Size engine — the SmartDecisions differentiator.

    Pipeline:
        1. Group the ingested sales DataFrame by `id_pedido` to form
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
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from services.logger_config import custom_logger as logger


PRODUCT_NAMES_KEY = 'product_names'
PDV_NAMES_KEY = 'pdv_names'


def _build_transactions(dataframe: pd.DataFrame) -> List[List[str]]:
    '''
        Groups the sales dataframe by `id_pedido` and returns one list of
        product SKUs per transaction. Duplicate products in the same order
        are collapsed, since market-basket support counts itemsets as sets,
        not multisets.

        Args:
            dataframe (pd.DataFrame): Sales rows (one product per row).

        Returns:
            List[List[str]]: Transactions as lists of unique product SKUs.
    '''
    grouped = dataframe.groupby('id_pedido')['id_producto'].apply(
        lambda values: sorted({str(value) for value in values})
    )
    return [products for products in grouped.tolist() if products]


_RULE_COLUMNS = ['antecedents', 'consequents', 'support', 'confidence', 'lift']


def _frequent_itemsets(
    transactions: List[List[str]],
    min_support: float
) -> Dict[frozenset, float]:
    '''
        Apriori frequent-itemset mining without external dependencies.

        Generates candidate k-itemsets from frequent (k-1)-itemsets, prunes
        them with the Apriori property (every (k-1)-subset must be frequent)
        and keeps those whose support reaches `min_support`.

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

    counts: Dict[frozenset, int] = {}
    for items in transaction_sets:
        for item in items:
            single = frozenset((item,))
            counts[single] = counts.get(single, 0) + 1
    current = {itemset: count for itemset, count in counts.items() if count >= min_count}

    supports: Dict[frozenset, float] = dict(current)
    size = 2
    while current:
        previous = list(current.keys())
        candidates: set = set()
        for left in range(len(previous)):
            for right in range(left + 1, len(previous)):
                union = previous[left] | previous[right]
                if len(union) != size:
                    continue
                # Apriori pruning: every (size - 1)-subset must be frequent.
                if all(frozenset(subset) in current
                       for subset in combinations(union, size - 1)):
                    candidates.add(union)

        if not candidates:
            break

        candidate_counts: Dict[frozenset, int] = {candidate: 0 for candidate in candidates}
        for items in transaction_sets:
            for candidate in candidates:
                if candidate <= items:
                    candidate_counts[candidate] += 1

        current = {
            itemset: count
            for itemset, count in candidate_counts.items()
            if count >= min_count
        }
        supports.update(current)
        size += 1

    return {itemset: count / total for itemset, count in supports.items()}


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
        if len(itemset) < 2:
            continue
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
                records.append({
                    'antecedents': antecedents,
                    'consequents': consequents,
                    'support': itemset_support,
                    'confidence': confidence,
                    'lift': lift
                })

    if not records:
        return pd.DataFrame(columns = _RULE_COLUMNS)
    return pd.DataFrame(records, columns = _RULE_COLUMNS)


def _compute_drop_size(
    dataframe: pd.DataFrame
) -> Tuple[pd.Series, pd.Series]:
    '''
        For each product, computes:
            - avg units per transaction (cantidad)
            - avg amount per transaction (monto_total), if available

        Args:
            dataframe (pd.DataFrame): Sales rows.

        Returns:
            Tuple[pd.Series, pd.Series]: (avg_units_by_product, avg_amount_by_product).
            Both indexed by id_producto. The amount series can be all-NaN when
            the source did not provide pricing.
    '''
    grouped = dataframe.groupby(['id_pedido', 'id_producto']).agg(
        cantidad = ('cantidad', 'sum'),
        monto_total = ('monto_total', 'sum')
    ).reset_index()

    avg_units = grouped.groupby('id_producto')['cantidad'].mean()
    avg_amount = grouped.groupby('id_producto')['monto_total'].mean()
    return avg_units, avg_amount


def _build_product_name_index(dataframe: pd.DataFrame) -> Dict[str, str]:
    '''
        Builds a stable id_producto → nombre_producto map for the UI layer.
    '''
    if 'nombre_producto' not in dataframe.columns:
        return {}
    pairs = dataframe[['id_producto', 'nombre_producto']].dropna()
    return {
        str(row['id_producto']): str(row['nombre_producto'])
        for _, row in pairs.drop_duplicates(subset = ['id_producto']).iterrows()
    }


def _build_pdv_name_index(dataframe: pd.DataFrame) -> Dict[str, str]:
    '''
        Builds a stable id_punto_venta → nombre_pdv map for the UI layer.
    '''
    if 'nombre_pdv' not in dataframe.columns:
        return {}
    pairs = dataframe[['id_punto_venta', 'nombre_pdv']].dropna()
    return {
        str(row['id_punto_venta']): str(row['nombre_pdv'])
        for _, row in pairs.drop_duplicates(subset = ['id_punto_venta']).iterrows()
    }


def _format_rationale(
    pdv_name: Optional[str],
    consequent_name: Optional[str],
    consequent_id: str,
    antecedent_names: List[str],
    lift: float,
    drop_units: float,
    drop_amount: Optional[float]
) -> str:
    '''
        Builds the Spanish-language explanation shown to the end user.
    '''
    antecedents_label = ', '.join(antecedent_names) if antecedent_names else 'productos similares'
    consequent_label = consequent_name or consequent_id
    pdv_label = f' en {pdv_name}' if pdv_name else ''
    amount_clause = (
        f' / ${drop_amount:.2f}'
        if drop_amount is not None and not pd.isna(drop_amount)
        else ''
    )
    return (
        f'Quienes compran {antecedents_label} tienden a comprar {consequent_label} '
        f'(lift {lift:.2f}). Drop size esperado{pdv_label}: '
        f'{drop_units:.1f} unidades{amount_clause}.'
    )


def compute_opportunities(
    dataframe: pd.DataFrame,
    min_support: float = 0.01,
    min_lift: float = 1.0,
    top_n_per_pdv: int = 10
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    '''
        End-to-end orchestration. Returns the opportunity list + summary stats.

        Args:
            dataframe (pd.DataFrame): Validated sales rows from ingest.
            min_support (float): Apriori minimum support (0..1).
            min_lift (float): association_rules lift threshold (>= 1 = no anti-correlation).
            top_n_per_pdv (int): Max opportunities returned per PdV.

        Returns:
            Tuple[List[Dict[str, Any]], Dict[str, Any]]:
                - Flat list of Opportunity dicts (ready to wrap in the schema).
                - Summary dict with run-level stats and the parameters used.
    '''
    transactions = _build_transactions(dataframe)
    rules = _compute_affinity_rules(transactions, min_support, min_lift)
    avg_units, avg_amount = _compute_drop_size(dataframe)
    product_names = _build_product_name_index(dataframe)
    pdv_names = _build_pdv_name_index(dataframe)

    parameters = {
        'min_support': min_support,
        'min_lift': min_lift,
        'top_n_per_pdv': top_n_per_pdv
    }

    if rules.empty:
        message = 'Affinity rules table is empty; returning zero opportunities.'
        logger.info(message)
        summary = {
            'total_pdvs_with_opportunities': 0,
            'total_opportunities': 0,
            'total_expected_value': None,
            'affinity_rules_evaluated': 0,
            'parameters': parameters
        }
        return [], summary

    # Pre-index rules by their antecedent frozenset for fast PdV-level lookup.
    pdv_to_products: Dict[str, set] = (
        dataframe.assign(id_producto = dataframe['id_producto'].astype(str))
                 .groupby('id_punto_venta')['id_producto']
                 .apply(lambda values: set(values))
                 .to_dict()
    )

    opportunities: List[Dict[str, Any]] = []
    for pdv_id, products_bought in pdv_to_products.items():
        pdv_id_str = str(pdv_id)
        pdv_label = pdv_names.get(pdv_id_str)
        candidates: List[Dict[str, Any]] = []

        for _, rule in rules.iterrows():
            antecedents = set(rule['antecedents'])
            consequents = set(rule['consequents'])
            # Rule only fires when the PdV already buys every antecedent.
            if not antecedents.issubset(products_bought):
                continue
            for consequent_id in consequents:
                # Skip products the PdV already buys.
                if consequent_id in products_bought:
                    continue
                drop_units = float(avg_units.get(consequent_id, 0.0) or 0.0)
                raw_amount = avg_amount.get(consequent_id)
                drop_amount = (
                    float(raw_amount)
                    if raw_amount is not None and not pd.isna(raw_amount)
                    else None
                )
                # Opportunity score uses monetary impact when prices exist,
                # otherwise falls back to volume.
                ranking_weight = drop_amount if drop_amount is not None else drop_units
                opportunity_score = float(rule['lift']) * float(rule['confidence']) * ranking_weight

                antecedent_ids = sorted(antecedents)
                antecedent_names = [
                    product_names.get(aid, aid) for aid in antecedent_ids
                ]
                candidates.append({
                    'pdv_id': pdv_id_str,
                    'pdv_name': pdv_label,
                    'recommended_product_id': consequent_id,
                    'recommended_product_name': product_names.get(consequent_id),
                    'based_on_products': antecedent_ids,
                    'support': float(rule['support']),
                    'confidence': float(rule['confidence']),
                    'lift': float(rule['lift']),
                    'expected_drop_size_units': round(drop_units, 4),
                    'expected_drop_size_amount': (
                        round(drop_amount, 4) if drop_amount is not None else None
                    ),
                    'opportunity_score': round(opportunity_score, 4),
                    'rationale': _format_rationale(
                        pdv_label, product_names.get(consequent_id), consequent_id,
                        antecedent_names, float(rule['lift']),
                        drop_units, drop_amount
                    )
                })

        # Deduplicate (pdv_id, recommended_product_id) keeping the highest score
        # — a product can appear as consequent of several rules for the same PdV.
        deduped: Dict[str, Dict[str, Any]] = {}
        for candidate in candidates:
            key = candidate['recommended_product_id']
            existing = deduped.get(key)
            if existing is None or candidate['opportunity_score'] > existing['opportunity_score']:
                deduped[key] = candidate

        ranked = sorted(
            deduped.values(),
            key = lambda item: item['opportunity_score'],
            reverse = True
        )[:top_n_per_pdv]
        opportunities.extend(ranked)

    total_expected_value = None
    amounts = [
        opp['expected_drop_size_amount']
        for opp in opportunities
        if opp.get('expected_drop_size_amount') is not None
    ]
    if amounts:
        total_expected_value = round(sum(amounts), 2)

    pdvs_with_opps = {opp['pdv_id'] for opp in opportunities}
    summary = {
        'total_pdvs_with_opportunities': len(pdvs_with_opps),
        'total_opportunities': len(opportunities),
        'total_expected_value': total_expected_value,
        'affinity_rules_evaluated': int(len(rules)),
        'parameters': parameters
    }

    message = (
        f'Affinity engine produced {summary["total_opportunities"]} opportunities '
        f'across {summary["total_pdvs_with_opportunities"]} PdVs from '
        f'{summary["affinity_rules_evaluated"]} rules.'
    )
    logger.info(message)

    return opportunities, summary
