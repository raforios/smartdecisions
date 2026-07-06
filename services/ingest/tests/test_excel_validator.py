'''
    Unit tests for the Excel validation pipeline.
'''
import io
import pandas as pd
import pytest

from services.excel_parser import parse_and_validate


def _to_xlsx_bytes(dataframe: pd.DataFrame) -> bytes:
    '''
        Helper to materialize a DataFrame as an .xlsx byte buffer.
    '''
    buffer = io.BytesIO()
    dataframe.to_excel(buffer, index = False, engine = 'openpyxl')
    buffer.seek(0)
    return buffer.getvalue()


def test_valid_minimum_required_columns() -> None:
    '''
        A file with only the required columns passes validation.
    '''
    dataframe = pd.DataFrame([
        {'id_pedido': 'P-001', 'fecha': '2026-01-12', 'id_punto_venta': 'PDV-1',
         'id_producto': 'SKU-A', 'cantidad': 5},
    ])
    _, errors, summary = parse_and_validate(_to_xlsx_bytes(dataframe), 'min.xlsx')
    assert not errors
    assert summary['total_rows'] == 1
    assert summary['valid_rows'] == 1


def test_missing_required_column_is_reported() -> None:
    '''
        Removing a required column raises a column-level error.
    '''
    dataframe = pd.DataFrame([
        {'id_pedido': 'P-001', 'fecha': '2026-01-12', 'id_punto_venta': 'PDV-1',
         'cantidad': 5},  # missing id_producto
    ])
    _, errors, _ = parse_and_validate(_to_xlsx_bytes(dataframe), 'missing_col.xlsx')
    assert any(err['column'] == 'id_producto' for err in errors)


def test_negative_quantity_is_rejected() -> None:
    '''
        Cantidad must be strictly greater than 0.
    '''
    dataframe = pd.DataFrame([
        {'id_pedido': 'P-001', 'fecha': '2026-01-12', 'id_punto_venta': 'PDV-1',
         'id_producto': 'SKU-A', 'cantidad': -2},
    ])
    _, errors, _ = parse_and_validate(_to_xlsx_bytes(dataframe), 'neg_qty.xlsx')
    assert any(err['column'] == 'cantidad' for err in errors)


def test_invalid_date_is_rejected() -> None:
    '''
        Non-parseable dates produce an error on the fecha column.
    '''
    dataframe = pd.DataFrame([
        {'id_pedido': 'P-001', 'fecha': 'no-es-fecha', 'id_punto_venta': 'PDV-1',
         'id_producto': 'SKU-A', 'cantidad': 5},
    ])
    _, errors, _ = parse_and_validate(_to_xlsx_bytes(dataframe), 'bad_date.xlsx')
    assert any(err['column'] == 'fecha' for err in errors)


def test_monto_total_is_derived_when_missing() -> None:
    '''
        When monto_total is absent but cantidad + precio_unitario exist, the
        pipeline fills it as cantidad * precio_unitario.
    '''
    dataframe = pd.DataFrame([
        {'id_pedido': 'P-001', 'fecha': '2026-01-12', 'id_punto_venta': 'PDV-1',
         'id_producto': 'SKU-A', 'cantidad': 3, 'precio_unitario': 10.0},
    ])
    df_out, errors, _ = parse_and_validate(_to_xlsx_bytes(dataframe), 'derived.xlsx')
    assert not errors
    assert df_out['monto_total'].iloc[0] == pytest.approx(30.0)


def test_unsupported_extension_raises() -> None:
    '''
        Files with unsupported extensions are rejected by the parser.
    '''
    with pytest.raises(ValueError):
        parse_and_validate(b'irrelevant', 'data.txt')
