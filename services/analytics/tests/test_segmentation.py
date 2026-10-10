'''
    Unit tests for the segmentation_engine.
'''
import pandas as pd

from services import segmentation
from services.segmentation import build_segmentation


def _clients_frame(n: int) -> pd.DataFrame:
    '''
        Builds `n` clients with strictly decreasing spend (client_0 spends the
        most), one purchase each.
    '''
    rows = []
    for i in range(n):
        rows.append({
            'order_id': f'F{i}', 'pos_id': f'C{i}',
            'pos_name': f'Cliente {i}', 'total_amount': float(n - i)
        })
    return pd.DataFrame(rows)


def test_tiers_split_top20_next30_rest():
    '''10 clients -> 2 Alto (top 20%), 3 Medio (next 30%), 5 Bajo.'''
    result = build_segmentation(_clients_frame(10))
    counts = {tier.tier: tier.clients for tier in result.tiers}
    assert counts == {'HIGH': 2, 'MEDIUM': 3, 'LOW': 5}
    assert result.total_clients == 10


def test_top_client_is_alto_and_first():
    '''The highest spender is listed first and tagged Alto.'''
    result = build_segmentation(_clients_frame(10))
    first = result.clients[0]
    assert first.client == 'Cliente 0'
    assert first.tier == 'HIGH'


def test_tier_shares_sum_to_100():
    '''The three tiers' sales shares add up to 100%.'''
    result = build_segmentation(_clients_frame(20))
    total = sum(tier.percentage for tier in result.tiers)
    assert round(total) == 100


def test_missing_columns_returns_empty():
    '''Without amount/client columns the result is empty, not an error.'''
    result = build_segmentation(pd.DataFrame([{'foo': 1}]))
    assert not result.tiers
    assert result.total_clients == 0


def test_each_tier_sums_its_clients_in_every_currency():
    '''`_tier_summary`: amount per tier in the three currencies, share in bolivianos.'''
    agg = pd.DataFrame({'tier': ['HIGH', 'LOW'], 'bob': [300.0, 100.0],
                        'usd': [30.0, 10.0], 'usdt': [29.0, 9.0]}, index = ['A', 'B'])

    tiers = {row.tier: row for row in segmentation._tier_summary(agg)} # pylint: disable=protected-access

    assert tiers['HIGH'].amount.usd == 30.0
    assert tiers['HIGH'].percentage == 75.0
