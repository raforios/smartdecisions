'''
    Unit tests for the ingest parsing pipeline: date conventions, coordinate
    sanitation and format equivalence between .xlsx and .csv.
'''
from io import BytesIO

import pandas as pd

from services.excel_parser import (
    _coerce_dates,
    _sanitize_geo,
    parse_and_validate_partial
)


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
        'latitud': [-16.5, 0.0, -16.4, 95.0],
        'longitud': [-68.1, -68.2, 0.0, -68.3],
    })
    cleaned = _sanitize_geo(frame)
    assert cleaned['latitud'].notna().tolist() == [True, False, False, False]
    assert cleaned['longitud'].notna().tolist() == [True, False, False, False]


def test_xlsx_and_csv_yield_the_same_rows():
    '''
        The same content must ingest identically in both formats: the file
        extension is a transport detail, never a data-loss boundary.
    '''
    frame = _sales_frame(['2024-01-05', '2024-01-18', '2024-01-27'])

    buffer = BytesIO()
    frame.to_excel(buffer, index = False, engine = 'openpyxl')
    from_xlsx, _, _, xlsx_summary = parse_and_validate_partial(
        buffer.getvalue(), 'ventas.xlsx'
    )
    from_csv, _, _, csv_summary = parse_and_validate_partial(
        frame.to_csv(index = False).encode('utf-8'), 'ventas.csv'
    )

    assert xlsx_summary['valid_rows'] == csv_summary['valid_rows'] == 3
    assert xlsx_summary['date_range_start'] == csv_summary['date_range_start']
    assert from_xlsx['fecha'].tolist() == from_csv['fecha'].tolist()


def test_unit_cost_is_carried_through_the_pipeline():
    '''
        'Costo Unitario' is optional, but when present it must reach the
        canonical frame so the margin KPIs have an operand.
    '''
    frame = _sales_frame(['2024-01-05', '2024-01-18'])
    valid, _, _, _ = parse_and_validate_partial(
        frame.to_csv(index = False).encode('utf-8'), 'ventas.csv'
    )
    assert 'costo_unitario' in valid.columns
    assert valid['costo_unitario'].tolist() == [6.0, 6.0]
