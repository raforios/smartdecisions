'''
    Unit tests for the column mapping layer (real-world header aliases).
'''
import pandas as pd

from services.column_mapper import map_columns


def test_maps_real_erp_headers_to_canonical():
    '''
        A distributor-style export (accented, spaced, ERP names) is renamed to
        the canonical template columns the validator expects.
    '''
    raw = pd.DataFrame(columns = [
        'Numero Factura', 'Fecha', 'Cliente ID', 'Codigo Sap', 'Producto',
        'Categoria', 'Unidades', 'Monto Final', 'Región', 'Latitud', 'Longitud'
    ])
    mapped = map_columns(raw)
    assert 'id_pedido' in mapped.columns          # Numero Factura
    assert 'id_punto_venta' in mapped.columns      # Cliente ID
    assert 'id_producto' in mapped.columns         # Codigo Sap
    assert 'nombre_producto' in mapped.columns     # Producto
    assert 'cantidad' in mapped.columns            # Unidades
    assert 'monto_total' in mapped.columns         # Monto Final
    assert {'categoria', 'region', 'latitud', 'longitud'} <= set(mapped.columns)


def test_first_alias_wins_on_collision():
    '''
        When two source columns map to the same canonical name, the first is
        renamed and the second keeps its original header (no silent overwrite).
    '''
    raw = pd.DataFrame(columns = ['Monto', 'Monto Final'])
    mapped = map_columns(raw)
    assert list(mapped.columns) == ['monto_total', 'Monto Final']


def test_unknown_columns_are_left_untouched():
    '''Columns with no known alias pass through unchanged.'''
    raw = pd.DataFrame(columns = ['id_pedido', 'ColumnaRara'])
    mapped = map_columns(raw)
    assert 'id_pedido' in mapped.columns
    assert 'ColumnaRara' in mapped.columns
