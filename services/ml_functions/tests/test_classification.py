'''
    Tests for the tiers by rank and the association rules.

    They import only the pure module and the schemas: the CI runs this
    service's tests with no .env.
'''
import pytest
from pydantic import ValidationError

from schemas.classification import TiersRequest
from services.classification import association_rules, frequent_itemsets, rank_tiers


def test_the_top_fifth_is_the_first_tier_and_the_order_is_kept():
    '''Ten values with cuts 0.2 and 0.5: two, three and five, in input order.'''
    values = [5.0, 100.0, 1.0, 90.0, 50.0, 40.0, 30.0, 4.0, 3.0, 2.0]
    assert rank_tiers(values, [0.2, 0.5]) == [2, 0, 2, 0, 1, 1, 1, 2, 2, 2]


def test_a_single_value_is_the_top():
    '''One member alone is at the top of its ranking.'''
    assert rank_tiers([7.0], [0.2, 0.5]) == [0]


def test_the_cuts_must_be_increasing_shares():
    '''A cut outside 0..1 or out of order is refused.'''
    with pytest.raises(ValidationError):
        TiersRequest(values = [1.0], cuts = [0.5, 0.2])
    with pytest.raises(ValidationError):
        TiersRequest(values = [1.0], cuts = [1.2])


BASKETS = [['bread', 'milk'], ['bread', 'milk', 'butter'], ['bread', 'butter'],
           ['milk'], ['bread', 'milk']]


def test_the_frequent_itemsets_carry_their_support():
    '''Bread is in four of five baskets; bread with milk in three.'''
    supports = frequent_itemsets(BASKETS, 0.4)
    assert supports[frozenset({'bread'})] == pytest.approx(0.8)
    assert supports[frozenset({'bread', 'milk'})] == pytest.approx(0.6)
    assert frozenset({'milk', 'butter'}) not in supports


def test_the_rules_carry_the_mlxtend_metrics():
    '''butter -> bread: support 0.4, confidence 1, lift 1 / 0.8.'''
    rules = {(rule.antecedents, rule.consequents): rule
             for rule in association_rules(BASKETS, 0.4, 1.0)}
    rule = rules[(('butter',), ('bread',))]
    assert rule.support == pytest.approx(0.4)
    assert rule.confidence == pytest.approx(1.0)
    assert rule.lift == pytest.approx(1.25)
    # bread -> milk has lift 0.9375: below the threshold, it is left out.
    assert (('bread',), ('milk',)) not in rules


def test_no_transactions_give_no_rules():
    '''Nothing mined, nothing found.'''
    assert not association_rules([], 0.1, 1.0)
