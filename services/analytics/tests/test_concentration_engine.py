'''
    Unit tests for the concentration_engine (dependency risk + ABC).
'''
import pandas as pd

from services.concentration_engine import build_concentration


def _clients_frame(amounts: list[float]) -> pd.DataFrame:
    '''
        One client per amount, one purchase each.

        Args:
            amounts (list[float]): Spend of each client.

        Returns:
            pd.DataFrame: Normalized sales rows.
    '''
    return pd.DataFrame([
        {
            'id_pedido': f'F{index}', 'id_punto_venta': f'C{index}',
            'nombre_pdv': f'Cliente {index}', 'id_producto': f'P{index}',
            'nombre_producto': f'Producto {index}', 'monto_total': amount
        }
        for index, amount in enumerate(amounts)
    ])


def test_single_client_is_flagged_as_maximum_concentration():
    '''
        One client holding all the sales is the riskiest possible portfolio:
        HHI is 1 and the plain-language reading must warn about it.
    '''
    result = build_concentration(_clients_frame([1000.0]))['clientes']
    assert result['hhi'] == 1.0
    assert result['top10_porcentaje'] == 100.0
    assert 'lta' in result['hhi_lectura']  # 'Alta: ...'


def test_evenly_spread_sales_report_low_concentration():
    '''Fifty identical clients is a well-distributed book of business.'''
    result = build_concentration(_clients_frame([100.0] * 50))['clientes']
    assert result['total_clientes'] == 50
    assert result['hhi'] < 0.15
    assert result['hhi_lectura'].startswith('Baja')


def test_pareto_point_counts_clients_making_up_eighty_percent():
    '''
        Four clients at 200 and sixteen at 5: the four heavyweights are 80% of
        the 880 total, so the Pareto point is 4.
    '''
    result = build_concentration(_clients_frame([200.0] * 4 + [5.0] * 16))['clientes']
    assert result['pareto_clientes'] == 4


def test_abc_classes_cover_the_whole_catalog():
    '''Every product lands in exactly one class and the shares add to 100%.'''
    abc = build_concentration(_clients_frame([100.0, 50.0, 25.0, 10.0, 5.0]))['abc']
    assert sum(row['productos'] for row in abc['resumen']) == 5
    assert round(sum(row['porcentaje'] for row in abc['resumen'])) == 100
    assert {row['clase'] for row in abc['resumen']} <= {'A', 'B', 'C'}


def test_empty_sections_without_client_data():
    '''No client column means no concentration analysis, not a crash.'''
    frame = pd.DataFrame({'monto_total': [10.0, 20.0]})
    result = build_concentration(frame)
    assert not result['clientes']
    assert not result['abc']
