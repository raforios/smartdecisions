'''
    Unit tests for the forecast_engine.
'''
import pandas as pd

from services.forecast_engine import build_forecast


def _monthly_frame() -> pd.DataFrame:
    '''Four months of clearly increasing total sales (100, 200, 300, 400).'''
    rows = []
    for month, monto in [('2026-01', 100), ('2026-02', 200),
                         ('2026-03', 300), ('2026-04', 400)]:
        rows.append({'fecha': f'{month}-15', 'monto_total': monto, 'categoria': 'A'})
    return pd.DataFrame(rows)


def test_linear_forecast_continues_the_trend():
    '''A +100/month history projects 500, 600, 700 next.'''
    result = build_forecast(_monthly_frame(), months_ahead = 3, method = 'linear')
    serie = result['series'][0]
    assert [p['mes'] for p in serie['historico']] == ['2026-01', '2026-02', '2026-03', '2026-04']
    proyectado = [round(p['monto']) for p in serie['pronostico']]
    assert proyectado == [500, 600, 700]
    assert [p['mes'] for p in serie['pronostico']] == ['2026-05', '2026-06', '2026-07']


def test_moving_average_is_flat():
    '''Moving average projects the recent mean, flat across the horizon.'''
    result = build_forecast(_monthly_frame(), months_ahead = 2, method = 'moving_average')
    proyectado = [p['monto'] for p in result['series'][0]['pronostico']]
    assert proyectado[0] == proyectado[1]  # flat
    assert proyectado[0] == 300.0          # mean of last 3 (200,300,400)


def test_forecast_never_goes_negative():
    '''A steep decline is clamped at 0, not negative.'''
    rows = [{'fecha': f'2026-0{m}-15', 'monto_total': v}
            for m, v in [(1, 400), (2, 300), (3, 200), (4, 100)]]
    result = build_forecast(pd.DataFrame(rows), months_ahead = 4, method = 'linear')
    proyectado = [p['monto'] for p in result['series'][0]['pronostico']]
    assert all(v >= 0 for v in proyectado)


def test_group_by_category_returns_one_series_each():
    '''Grouping by category yields one forecast block per category.'''
    frame = _monthly_frame()
    frame = pd.concat([frame, frame.assign(categoria = 'B')], ignore_index = True)
    result = build_forecast(frame, months_ahead = 2, method = 'linear', group_by = 'categoria')
    nombres = {serie['nombre'] for serie in result['series']}
    assert nombres == {'A', 'B'}
