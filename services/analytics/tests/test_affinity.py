'''
    Unit tests for the affinity_engine pipeline.
'''
import pandas as pd
import pytest

from services.affinity import compute_opportunities


def _sales_frame() -> pd.DataFrame:
    '''
        Builds a small but information-rich sales DataFrame:
          - Two PdVs that buy {A, B} together repeatedly (high lift A↔B).
          - One PdV that buys only A (so B becomes a recommendation for it).
          - C appears as background noise.
    '''
    rows = []
    # PdV-1 and PdV-2 buy A+B together across many orders.
    for order_index in range(1, 11):
        rows.append({'order_id': f'O-1-{order_index}', 'pos_id': 'PDV-1',
                     'product_id': 'A', 'quantity': 2, 'total_amount': 20.0,
                     'pos_name': 'Tienda Uno', 'product_name': 'Galleta A'})
        rows.append({'order_id': f'O-1-{order_index}', 'pos_id': 'PDV-1',
                     'product_id': 'B', 'quantity': 3, 'total_amount': 30.0,
                     'pos_name': 'Tienda Uno', 'product_name': 'Yogurt B'})
    for order_index in range(1, 11):
        rows.append({'order_id': f'O-2-{order_index}', 'pos_id': 'PDV-2',
                     'product_id': 'A', 'quantity': 2, 'total_amount': 20.0,
                     'pos_name': 'Tienda Dos', 'product_name': 'Galleta A'})
        rows.append({'order_id': f'O-2-{order_index}', 'pos_id': 'PDV-2',
                     'product_id': 'B', 'quantity': 3, 'total_amount': 30.0,
                     'pos_name': 'Tienda Dos', 'product_name': 'Yogurt B'})
    # PdV-3 only buys A — perfect target for "recommend B" because it never
    # bought B but always co-occurred with A elsewhere.
    for order_index in range(1, 8):
        rows.append({'order_id': f'O-3-{order_index}', 'pos_id': 'PDV-3',
                     'product_id': 'A', 'quantity': 1, 'total_amount': 10.0,
                     'pos_name': 'Tienda Tres', 'product_name': 'Galleta A'})
    # Add some background orders with C to enrich the rule space.
    for order_index in range(1, 4):
        rows.append({'order_id': f'O-4-{order_index}', 'pos_id': 'PDV-1',
                     'product_id': 'C', 'quantity': 1, 'total_amount': 5.0,
                     'pos_name': 'Tienda Uno', 'product_name': 'Snack C'})

    return pd.DataFrame(rows)


def test_recommends_b_to_pdv3_that_only_buys_a() -> None:
    '''
        Given strong A→B affinity, PdV-3 (only buys A) must receive B.
    '''
    opportunities, summary = compute_opportunities(
        dataframe = _sales_frame(),
        min_support = 0.1,
        min_lift = 1.0,
        top_n_per_pdv = 10
    )
    pdv3 = [opp for opp in opportunities if opp.pdv_id == 'PDV-3']
    assert pdv3, 'expected at least one opportunity for PDV-3'
    assert any(opp.recommended_product_id == 'B' for opp in pdv3)
    assert summary.total_opportunities >= 1


def test_does_not_recommend_already_purchased_products() -> None:
    '''
        PdVs that already buy B must not receive B as a recommendation.
    '''
    opportunities, _ = compute_opportunities(
        dataframe = _sales_frame(),
        min_support = 0.1,
        min_lift = 1.0,
        top_n_per_pdv = 10
    )
    pdv1_recs = {opp.recommended_product_id for opp in opportunities if opp.pdv_id == 'PDV-1'}
    assert 'B' not in pdv1_recs


def test_opportunity_includes_drop_size_amount_when_prices_present() -> None:
    '''
        The dataset includes total_amount for every row, so expected_drop_size_amount
        must be populated and used in the opportunity_score.
    '''
    opportunities, _ = compute_opportunities(
        dataframe = _sales_frame(),
        min_support = 0.1,
        min_lift = 1.0,
        top_n_per_pdv = 10
    )
    assert all(opp.expected_drop_size_amount is not None for opp in opportunities)
    for opp in opportunities:
        expected_score = (
            opp.lift * opp.confidence * opp.expected_drop_size_amount
        )
        assert opp.opportunity_score == pytest.approx(expected_score, rel = 1e-3)


def test_top_n_caps_opportunities_per_pdv() -> None:
    '''
        With top_n_per_pdv = 1, every PdV must have at most one opportunity.
    '''
    opportunities, _ = compute_opportunities(
        dataframe = _sales_frame(),
        min_support = 0.05,
        min_lift = 1.0,
        top_n_per_pdv = 1
    )
    by_pdv: dict = {}
    for opp in opportunities:
        by_pdv.setdefault(opp.pdv_id, 0)
        by_pdv[opp.pdv_id] += 1
    assert all(count <= 1 for count in by_pdv.values())


def test_empty_dataframe_returns_zero_opportunities() -> None:
    '''
        Edge case: no rows in → empty opportunities + zeroed summary.
    '''
    empty = pd.DataFrame(columns = [
        'order_id', 'pos_id', 'product_id', 'quantity', 'total_amount'
    ])
    opportunities, summary = compute_opportunities(empty)
    assert not opportunities
    assert summary.total_opportunities == 0
    assert summary.affinity_rules_evaluated == 0
