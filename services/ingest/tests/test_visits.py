'''
    Unit tests for the visits contract.

    The visits are the executed side of a route, married to the sales dataset
    by client and by seller. These tests pin what the pipeline promises: the
    hour is normalized, placeholders in the GPS pair are cleared, an unknown
    client is reported and kept, and a bad outcome code never passes as a
    sale by omission.
'''
from io import BytesIO

import pandas as pd

from schemas.ingest import SALES_SHEET, VISITS_SHEET, ValidationRule
from services.visits import parse_and_validate, read_visits


def _sales_frame() -> pd.DataFrame:
    '''
        Two clients served by one seller.

        Returns:
            pd.DataFrame: A normalized sales frame.
    '''
    return pd.DataFrame([
        {'pos_id': 'Tienda Norte', 'seller': 'Mario', 'total_amount': 600.0},
        {'pos_id': 'Tienda Sur', 'seller': 'Mario', 'total_amount': 400.0},
    ])


def _visits_csv(rows: list[dict]) -> bytes:
    '''
        Builds a visits CSV with the published headers.

        Args:
            rows (list[dict]): Rows keyed by template header.

        Returns:
            bytes: CSV content.
    '''
    return pd.DataFrame(rows).to_csv(index = False).encode('utf-8')


def test_a_visit_marries_the_client_and_the_seller_of_the_dataset():
    '''The plain case: date, seller and client, nothing else.'''
    file_bytes = _visits_csv([
        {'Fecha': '2026-03-10', 'Vendedor': 'Mario', 'Cliente': 'Tienda Norte'},
        {'Fecha': '2026-03-10', 'Vendedor': 'Mario', 'Cliente': 'Tienda Sur'},
    ])
    result = parse_and_validate(file_bytes, 'visitas.csv', _sales_frame())

    assert not result.issues
    assert result.summary.valid_rows == 2
    assert result.summary.sellers == 1
    assert result.summary.clients == 2
    assert result.summary.unknown_clients == 0
    assert result.summary.with_coordinates == 0
    assert result.summary.visit_date_start == '2026-03-10'
    assert list(result.accepted['pos_id']) == ['Tienda Norte', 'Tienda Sur']


def test_the_hour_is_normalized_and_an_unreadable_one_stays_empty():
    '''
        '9:05' and '09:05:00' are the same hour; 'mañana' is no hour at all
        and must not become midnight.
    '''
    file_bytes = _visits_csv([
        {'Fecha': '2026-03-10', 'Hora': '9:05', 'Vendedor': 'Mario', 'Cliente': 'Tienda Norte'},
        {'Fecha': '2026-03-10', 'Hora': 'mañana', 'Vendedor': 'Mario', 'Cliente': 'Tienda Sur'},
    ])
    result = parse_and_validate(file_bytes, 'visitas.csv', _sales_frame())

    times = list(result.accepted['visit_time'])
    assert times[0] == '09:05:00'
    assert pd.isna(times[1])


def test_a_zero_coordinate_is_no_coordinate():
    '''The ERP placeholder 0,0 must not count as a GPS reading.'''
    file_bytes = _visits_csv([
        {'Fecha': '2026-03-10', 'Vendedor': 'Mario', 'Cliente': 'Tienda Norte',
         'Latitud': -16.5, 'Longitud': -68.15},
        {'Fecha': '2026-03-10', 'Vendedor': 'Mario', 'Cliente': 'Tienda Sur',
         'Latitud': 0, 'Longitud': 0},
    ])
    result = parse_and_validate(file_bytes, 'visitas.csv', _sales_frame())

    assert not result.issues
    assert result.summary.with_coordinates == 1


def test_an_unknown_client_is_reported_and_kept():
    '''
        A visit to a prospect is a fact: it travels with its code instead of
        being dropped, so the reader can tell a prospect from a typo.
    '''
    file_bytes = _visits_csv([
        {'Fecha': '2026-03-10', 'Vendedor': 'Mario', 'Cliente': 'Tienda Norte'},
        {'Fecha': '2026-03-10', 'Vendedor': 'Mario', 'Cliente': 'Kiosco Nuevo'},
    ])
    result = parse_and_validate(file_bytes, 'visitas.csv', _sales_frame())

    assert result.summary.valid_rows == 2
    assert result.summary.unknown_clients == 1
    codes = [issue.rule_code for issue in result.issues]
    assert codes == [ValidationRule.UNKNOWN_CLIENT]
    assert result.issues[0].value == 'Kiosco Nuevo'


def test_an_unknown_seller_is_reported_too():
    '''A seller the sales file never mentions is either new or a typo.'''
    file_bytes = _visits_csv([
        {'Fecha': '2026-03-10', 'Vendedor': 'Lucía', 'Cliente': 'Tienda Norte'},
    ])
    result = parse_and_validate(file_bytes, 'visitas.csv', _sales_frame())

    assert result.summary.unknown_sellers == 1
    assert [issue.rule_code for issue in result.issues] == [ValidationRule.UNKNOWN_SELLER]


def test_the_outcome_is_a_closed_list():
    '''
        'venta' in lowercase is a sale; 'VENDIDO' is not a code and fails the
        row instead of passing as something it is not.
    '''
    good = _visits_csv([
        {'Fecha': '2026-03-10', 'Vendedor': 'Mario', 'Cliente': 'Tienda Norte',
         'Resultado': 'venta', 'Nro Factura': 'F-1'},
    ])
    result = parse_and_validate(good, 'visitas.csv', _sales_frame())
    assert not result.issues
    assert result.summary.with_outcome == 1
    assert list(result.accepted['outcome']) == ['VENTA']

    bad = _visits_csv([
        {'Fecha': '2026-03-10', 'Vendedor': 'Mario', 'Cliente': 'Tienda Norte',
         'Resultado': 'VENDIDO'},
    ])
    result = parse_and_validate(bad, 'visitas.csv', _sales_frame())
    assert result.summary.valid_rows == 0
    assert any(issue.rule_code == ValidationRule.INVALID_VALUE for issue in result.issues)


def test_the_visits_sheet_is_found_inside_the_workbook():
    '''
        The published template is one workbook; a client who returns it with
        the visits sheet filled loads sales and visits in a single upload, and
        one without that sheet loads nothing about visits and says nothing.
    '''
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine = 'openpyxl') as writer:
        pd.DataFrame([
            {'Fecha': '2026-03-10', 'Nro Factura': 'F-1', 'Cliente': 'Tienda Norte',
             'Producto': 'Galleta', 'Cantidad': 2}
        ]).to_excel(writer, sheet_name = SALES_SHEET, index = False)
        pd.DataFrame([
            {'Fecha': '2026-03-10', 'Hora': '10:30', 'Vendedor': 'Mario',
             'Cliente': 'Tienda Norte'}
        ]).to_excel(writer, sheet_name = VISITS_SHEET, index = False)

    found = read_visits(buffer.getvalue(), 'plantilla.xlsx', auto = True)
    assert found is not None and len(found) == 1

    result = parse_and_validate(buffer.getvalue(), 'plantilla.xlsx', _sales_frame(), auto = True)
    assert result.summary.valid_rows == 1

    without = BytesIO()
    with pd.ExcelWriter(without, engine = 'openpyxl') as writer:
        pd.DataFrame([{'Fecha': '2026-03-10'}]).to_excel(
            writer, sheet_name = SALES_SHEET, index = False)
    assert read_visits(without.getvalue(), 'plantilla.xlsx', auto = True) is None
