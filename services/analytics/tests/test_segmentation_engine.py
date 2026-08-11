'''
    Unit tests for the segmentation_engine.
'''
import pandas as pd

from services.segmentation_engine import build_segmentation


def _clients_frame(n: int) -> pd.DataFrame:
    '''
        Builds `n` clients with strictly decreasing spend (client_0 spends the
        most), one purchase each.
    '''
    rows = []
    for i in range(n):
        rows.append({
            'id_pedido': f'F{i}', 'id_punto_venta': f'C{i}',
            'nombre_pdv': f'Cliente {i}', 'monto_total': float(n - i)
        })
    return pd.DataFrame(rows)


def test_tiers_split_top20_next30_rest():
    '''10 clients -> 2 Alto (top 20%), 3 Medio (next 30%), 5 Bajo.'''
    result = build_segmentation(_clients_frame(10))
    counts = {tier['tier']: tier['clientes'] for tier in result['tiers']}
    assert counts == {'Alto': 2, 'Medio': 3, 'Bajo': 5}
    assert result['total_clientes'] == 10


def test_top_client_is_alto_and_first():
    '''The highest spender is listed first and tagged Alto.'''
    result = build_segmentation(_clients_frame(10))
    first = result['clientes'][0]
    assert first['cliente'] == 'Cliente 0'
    assert first['tier'] == 'Alto'


def test_tier_shares_sum_to_100():
    '''The three tiers' sales shares add up to 100%.'''
    result = build_segmentation(_clients_frame(20))
    total = sum(tier['porcentaje'] for tier in result['tiers'])
    assert round(total) == 100


def test_missing_columns_returns_empty():
    '''Without monto/cliente columns the result is empty, not an error.'''
    result = build_segmentation(pd.DataFrame([{'foo': 1}]))
    assert result['tiers'] == []
    assert result['total_clientes'] == 0
