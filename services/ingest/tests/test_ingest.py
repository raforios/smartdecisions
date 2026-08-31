'''
    Unit tests for the ingest domain: header mapping against the published
    contract, DataFrame validation, and the parsing pipeline (date conventions,
    coordinate sanitation, format equivalence between .xlsx and .csv).
'''
import io
from io import BytesIO

import pandas as pd
import pytest

from schemas.ingest import ValidationRule
from services.ingest import (
    _coerce_dates,
    _sanitize_geo,
    map_columns,
    parse_and_validate,
    parse_and_validate_partial
)


# ---------------------------------------------------------------------------
# Column mapper
# ---------------------------------------------------------------------------

def test_maps_template_headers_to_canonical():
    '''
        The published template, filled in by the client, is renamed to the
        canonical English columns the validator expects.
    '''
    raw = pd.DataFrame(columns = [
        'Fecha', 'Nro Factura', 'Cliente', 'Zona', 'Ciudad', 'Vendedor',
        'Latitud', 'Longitud', 'Producto', 'Categoria', 'Cantidad',
        'Precio Unitario', 'Costo Unitario', 'Monto Total'
    ])

    mapped = map_columns(raw)

    assert set(mapped.columns) == {
        'date', 'order_id', 'pos_name', 'zone', 'city', 'seller', 'latitude',
        'longitude', 'product_name', 'category', 'quantity', 'unit_price',
        'unit_cost', 'total_amount'
    }


def test_matching_ignores_accents_and_case():
    '''A client who types 'CATEGORÍA' still lands on the canonical column.'''
    raw = pd.DataFrame(columns = ['CATEGORÍA', 'precio unitario'])

    mapped = map_columns(raw)

    assert set(mapped.columns) == {'category', 'unit_price'}


def test_canonical_names_are_accepted_as_is():
    '''A file already using the contract's English names passes through.'''
    raw = pd.DataFrame(columns = ['order_id', 'total_amount'])

    mapped = map_columns(raw)

    assert list(mapped.columns) == ['order_id', 'total_amount']


def test_first_header_wins_on_collision():
    '''
        When two source columns map to the same canonical name, the first is
        renamed and the second keeps its original header (no silent overwrite).
    '''
    raw = pd.DataFrame(columns = ['Monto Total', 'MONTO TOTAL'])

    mapped = map_columns(raw)

    assert list(mapped.columns) == ['total_amount', 'MONTO TOTAL']


def test_unknown_columns_are_left_untouched():
    '''Columns outside the contract pass through unchanged.'''
    raw = pd.DataFrame(columns = ['order_id', 'ColumnaRara'])

    mapped = map_columns(raw)

    assert 'order_id' in mapped.columns
    assert 'ColumnaRara' in mapped.columns


# ---------------------------------------------------------------------------
# Excel validator
# ---------------------------------------------------------------------------

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
        {'order_id': 'P-001', 'date': '2026-01-12', 'pos_id': 'PDV-1',
         'product_id': 'SKU-A', 'quantity': 5},
    ])
    result = parse_and_validate(_to_xlsx_bytes(dataframe), 'min.xlsx')
    assert not result.issues
    assert result.summary.total_rows == 1
    assert result.summary.valid_rows == 1


def test_missing_required_column_is_reported() -> None:
    '''
        Removing a required column raises a column-level error.
    '''
    dataframe = pd.DataFrame([
        {'order_id': 'P-001', 'date': '2026-01-12', 'pos_id': 'PDV-1',
         'quantity': 5},  # missing product_id
    ])
    result = parse_and_validate(_to_xlsx_bytes(dataframe), 'missing_col.xlsx')
    assert any(issue.column == 'product_id' for issue in result.issues)
    assert any(issue.rule_code is ValidationRule.MISSING_COLUMN for issue in result.issues)


def test_negative_quantity_is_rejected() -> None:
    '''
        Cantidad must be strictly greater than 0.
    '''
    dataframe = pd.DataFrame([
        {'order_id': 'P-001', 'date': '2026-01-12', 'pos_id': 'PDV-1',
         'product_id': 'SKU-A', 'quantity': -2},
    ])
    result = parse_and_validate(_to_xlsx_bytes(dataframe), 'neg_qty.xlsx')
    assert any(issue.column == 'quantity' for issue in result.issues)
    assert any(issue.rule_code is ValidationRule.BELOW_MINIMUM for issue in result.issues)


def test_invalid_date_is_rejected() -> None:
    '''
        Non-parseable dates produce an error on the date column.
    '''
    dataframe = pd.DataFrame([
        {'order_id': 'P-001', 'date': 'no-es-date', 'pos_id': 'PDV-1',
         'product_id': 'SKU-A', 'quantity': 5},
    ])
    result = parse_and_validate(_to_xlsx_bytes(dataframe), 'bad_date.xlsx')
    assert any(issue.column == 'date' for issue in result.issues)


def test_total_amount_is_derived_when_missing() -> None:
    '''
        When total_amount is absent but quantity + unit_price exist, the
        pipeline fills it as quantity * unit_price.
    '''
    dataframe = pd.DataFrame([
        {'order_id': 'P-001', 'date': '2026-01-12', 'pos_id': 'PDV-1',
         'product_id': 'SKU-A', 'quantity': 3, 'unit_price': 10.0},
    ])
    result = parse_and_validate(_to_xlsx_bytes(dataframe), 'derived.xlsx')
    df_out = result.accepted
    assert not result.issues
    assert df_out['total_amount'].iloc[0] == pytest.approx(30.0)


def test_unsupported_extension_raises() -> None:
    '''
        Files with unsupported extensions are rejected by the parser.
    '''
    with pytest.raises(ValueError):
        parse_and_validate(b'irrelevant', 'data.txt')


# ---------------------------------------------------------------------------
# Excel parser
# ---------------------------------------------------------------------------

def _sales_frame(dates: list[str]) -> pd.DataFrame:
    '''
        Builds a minimal template-shaped frame with the given date strings.

        Args:
            dates (list[str]): Values for the 'Fecha' column.

        Returns:
            pd.DataFrame: Frame using the client-facing template headers.
    '''
    return pd.DataFrame({
        'Fecha': dates,
        'Nro Factura': [f'F-{index:03d}' for index in range(len(dates))],
        'Cliente': ['Tienda Uno'] * len(dates),
        'Producto': ['Galleta 200g'] * len(dates),
        'Cantidad': [3] * len(dates),
        'Precio Unitario': [8.5] * len(dates),
        'Costo Unitario': [6.0] * len(dates),
    })


def test_iso_dates_past_the_twelfth_are_not_dropped():
    '''
        Regression: day-first parsing made pandas infer '%Y-%d-%m' from the
        first ISO value, so every date after the 12th silently became NaT and
        its row was rejected. ISO input must survive intact.
    '''
    parsed = _coerce_dates(pd.Series(['2022-02-02', '2022-02-25', '2023-11-30']))
    assert parsed.notna().all()
    assert [str(value.date()) for value in parsed] == [
        '2022-02-02', '2022-02-25', '2023-11-30'
    ]


def test_day_first_dates_are_still_read_as_day_first():
    '''
        Bolivian exports write dd/mm/aaaa; 03/02/2024 is 3 February, not 2 March.
    '''
    parsed = _coerce_dates(pd.Series(['25/12/2023', '03/02/2024']))
    assert [str(value.date()) for value in parsed] == ['2023-12-25', '2024-02-03']


def test_placeholder_coordinates_are_cleared():
    '''
        A literal 0 is an ERP's "no GPS reading", not a location off Africa.
        Both members of the pair are cleared together.
    '''
    frame = pd.DataFrame({
        'latitude': [-16.5, 0.0, -16.4, 95.0],
        'longitude': [-68.1, -68.2, 0.0, -68.3],
    })
    cleaned = _sanitize_geo(frame)
    assert cleaned['latitude'].notna().tolist() == [True, False, False, False]
    assert cleaned['longitude'].notna().tolist() == [True, False, False, False]


def test_xlsx_and_csv_yield_the_same_rows():
    '''
        The same content must ingest identically in both formats: the file
        extension is a transport detail, never a data-loss boundary.
    '''
    frame = _sales_frame(['2024-01-05', '2024-01-18', '2024-01-27'])

    buffer = BytesIO()
    frame.to_excel(buffer, index = False, engine = 'openpyxl')
    from_xlsx = parse_and_validate_partial(buffer.getvalue(), 'ventas.xlsx')
    from_csv = parse_and_validate_partial(
        frame.to_csv(index = False).encode('utf-8'), 'ventas.csv'
    )

    assert from_xlsx.summary.valid_rows == from_csv.summary.valid_rows == 3
    assert from_xlsx.summary.date_range_start == from_csv.summary.date_range_start
    assert from_xlsx.accepted['date'].tolist() == from_csv.accepted['date'].tolist()


def test_unit_cost_is_carried_through_the_pipeline():
    '''
        'Costo Unitario' is optional, but when present it must reach the
        canonical frame so the margin KPIs have an operand.
    '''
    frame = _sales_frame(['2024-01-05', '2024-01-18'])
    result = parse_and_validate_partial(
        frame.to_csv(index = False).encode('utf-8'), 'ventas.csv'
    )
    assert 'unit_cost' in result.accepted.columns
    assert result.accepted['unit_cost'].tolist() == [6.0, 6.0]
