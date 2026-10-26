'''
    Classifications every service may ask for by HTTP instead of keeping its
    own copy (Rafael, 17-oct-2026; moved from COMMERCIAL on 24-oct-2026):

      - Tiers by rank: the values are sorted from the highest down and each one
        takes the tier of the share of the ranking it falls in. With cuts
        (0.2, 0.5), the top 20 % is tier 0, the next 30 % tier 1 and the rest
        tier 2. Whoever asks names the tiers; this module only counts them.
      - Association rules (Apriori): from transactions —each one a set of
        items bought together— the frequent itemsets and the rules
        antecedents -> consequents, with support, confidence and lift.
        Implemented here because mlxtend does not fit in the Lambda.

    Pure Python and free of the environment: the CI runs this service's tests
    with no .env.
'''
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen = True)
class Rule:
    '''
        One association rule: when a transaction holds `antecedents`, it tends
        to hold `consequents` too.
    '''
    antecedents: tuple[str, ...]
    consequents: tuple[str, ...]
    support: float
    confidence: float
    lift: float


def rank_tiers(
    values: list[float],
    cuts: list[float]
) -> list[int]:
    '''
        The tier of each value by its place in the ranking, highest first.

        Args:
            values (list[float]): One value per member, in any order.
            cuts (list[float]): Increasing shares of the ranking (0..1) where
                each tier ends; one tier more than cuts.

        Returns:
            list[int]: The tier of each value, in the order of `values`
                (0 = the top).
    '''
    total = len(values)
    order = sorted(range(total), key = lambda index: values[index], reverse = True)
    tiers = [0] * total
    for rank, index in enumerate(order):
        share = rank / total
        tiers[index] = next((tier for tier, cut in enumerate(cuts) if share < cut), len(cuts))
    return tiers


def _count_singletons(transactions: list[frozenset]) -> dict[frozenset, int]:
    '''
        How many transactions hold each single item.
    '''
    counts: dict[frozenset, int] = {}
    for items in transactions:
        for item in items:
            single = frozenset((item,))
            counts[single] = counts.get(single, 0) + 1
    return counts


def _generate_candidates(
    previous_frequent: list[frozenset],
    size: int
) -> set[frozenset]:
    '''
        Candidate itemsets of `size` from the frequent ones a size smaller,
        pruned by the Apriori property: every subset must be frequent.
    '''
    frequent = set(previous_frequent)
    candidates: set[frozenset] = set()
    for left, right in combinations(previous_frequent, 2):
        union = left | right
        if len(union) != size:
            continue
        if all(frozenset(subset) in frequent for subset in combinations(union, size - 1)):
            candidates.add(union)
    return candidates


def _count_supersets(
    transactions: list[frozenset],
    candidates: set[frozenset]
) -> dict[frozenset, int]:
    '''
        How many transactions hold each candidate itemset.
    '''
    counts: dict[frozenset, int] = dict.fromkeys(candidates, 0)
    for items in transactions:
        for candidate in candidates:
            if candidate <= items:
                counts[candidate] += 1
    return counts


def frequent_itemsets(
    transactions: list[list[str]],
    min_support: float
) -> dict[frozenset, float]:
    '''
        The itemsets present in at least `min_support` of the transactions.

        Args:
            transactions (list[list[str]]): The items of each transaction.
            min_support (float): Minimum share of transactions (0..1).

        Returns:
            dict[frozenset, float]: Each frequent itemset and its support.
    '''
    total = len(transactions)
    if total == 0:
        return {}
    sets = [frozenset(items) for items in transactions]
    min_count = min_support * total

    current = {itemset: count for itemset, count in _count_singletons(sets).items()
               if count >= min_count}
    counts: dict[frozenset, int] = dict(current)
    size = 2
    while current:
        candidates = _generate_candidates(list(current), size)
        if not candidates:
            break
        current = {itemset: count for itemset, count in _count_supersets(sets, candidates).items()
                   if count >= min_count}
        counts.update(current)
        size += 1
    return {itemset: count / total for itemset, count in counts.items()}


def _rules_of(
    itemset: frozenset,
    supports: dict[frozenset, float],
    min_lift: float
) -> list[Rule]:
    '''
        Every antecedent -> consequent split of one frequent itemset whose
        lift reaches `min_lift`.
    '''
    rules: list[Rule] = []
    support = supports[itemset]
    items = sorted(itemset)
    for antecedent_size in range(1, len(items)):
        for antecedent_items in combinations(items, antecedent_size):
            antecedents = frozenset(antecedent_items)
            consequents = itemset - antecedents
            antecedent_support = supports.get(antecedents)
            consequent_support = supports.get(consequents)
            if not antecedent_support or not consequent_support:
                continue
            confidence = support / antecedent_support
            lift = confidence / consequent_support
            if lift >= min_lift:
                rules.append(Rule(tuple(sorted(antecedents)), tuple(sorted(consequents)),
                                  support, confidence, lift))
    return rules


def association_rules(
    transactions: list[list[str]],
    min_support: float,
    min_lift: float
) -> list[Rule]:
    '''
        The association rules of the transactions, with the same metrics
        mlxtend gives:
            support    = support(antecedents and consequents)
            confidence = support(itemset) / support(antecedents)
            lift       = confidence / support(consequents)

        Args:
            transactions (list[list[str]]): The items of each transaction.
            min_support (float): Minimum share of transactions (0..1).
            min_lift (float): Minimum lift a rule needs to be kept.

        Returns:
            list[Rule]: The rules kept.
    '''
    supports = frequent_itemsets(transactions, min_support)
    rules: list[Rule] = []
    for itemset in supports:
        if len(itemset) >= 2:
            rules.extend(_rules_of(itemset, supports, min_lift))
    return rules
