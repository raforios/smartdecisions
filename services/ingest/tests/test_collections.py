'''
    Unit tests for the collections contract.

    Covers the two rules that are the point of the module —an invoice with no
    payments is an open balance and a payment without its invoice is an issue
    with a code— plus partial payments, the closed-option normalization of the
    sales sheet and the auto mode that must stay silent on a cash-only file.
'''
from io import BytesIO

import pandas as pd

from schemas.ingest import (
    COLLECTIONS_SHEET,
    SALES_SHEET,
    ValidationRule
)
from services.collections import parse_and_validate, read_collections
from services.ingest import parse_and_validate as parse_sales


def _sales_frame() -> pd.DataFrame:
    '''
        Two invoices, one of them with two product lines.

        Returns:
            pd.DataFrame: A normalized sales frame.
    '''
    return pd.DataFrame([
        {'order_id': 'F-1', 'total_amount': 600.0},
        {'order_id': 'F-1', 'total_amount': 400.0},
        {'order_id': 'F-2', 'total_amount': 500.0},
    ])


def _collections_csv(rows: list[dict]) -> bytes:
    '''
        Builds a collections CSV with the published headers.

        Args:
            rows (list[dict]): Rows keyed by template header.

        Returns:
            bytes: CSV content.
    '''
    return pd.DataFrame(rows).to_csv(index = False).encode('utf-8')


def test_payments_are_imputed_against_the_whole_invoice():
    '''
        An invoice spans several product lines, so the receivable is its total:
        1.000 for F-1. A payment of 1.000 matches it and is not an overpayment.
    '''
    file_bytes = _collections_csv([
        {'Nro Factura': 'F-1', 'Fecha Cobro': '2026-03-10', 'Monto Cobrado': 1000.0}
    ])
    result = parse_and_validate(file_bytes, 'cobros.csv', _sales_frame())

    assert not result.issues
    assert result.summary.matched_invoices == 1
    assert result.summary.collected_amount == 1000.0


def test_partial_payments_add_up_and_keep_the_invoice_open():
    '''
        Two instalments against the same invoice are two rows, and the balance
        is what is missing — not an error and not a duplicate.
    '''
    file_bytes = _collections_csv([
        {'Nro Factura': 'F-1', 'Fecha Cobro': '2026-03-10', 'Monto Cobrado': 400.0},
        {'Nro Factura': 'F-1', 'Fecha Cobro': '2026-04-10', 'Monto Cobrado': 300.0},
    ])
    result = parse_and_validate(file_bytes, 'cobros.csv', _sales_frame())

    assert not result.issues
    assert result.summary.valid_rows == 2
    assert result.summary.matched_invoices == 1
    assert result.summary.collected_amount == 700.0


def test_invoice_without_payments_is_not_reported_at_all():
    '''
        F-2 has no payment rows: that is an open balance, which is exactly what
        lets a client load sales today and payments tomorrow.
    '''
    file_bytes = _collections_csv([
        {'Nro Factura': 'F-1', 'Fecha Cobro': '2026-03-10', 'Monto Cobrado': 1000.0}
    ])
    result = parse_and_validate(file_bytes, 'cobros.csv', _sales_frame())

    codes = {issue.rule_code for issue in result.issues}
    assert ValidationRule.UNKNOWN_INVOICE not in codes
    assert result.summary.unmatched_rows == 0


def test_payment_without_its_invoice_is_an_issue_with_a_code():
    '''An orphan payment is reported, never dropped in silence.'''
    file_bytes = _collections_csv([
        {'Nro Factura': 'F-9', 'Fecha Cobro': '2026-03-10', 'Monto Cobrado': 100.0}
    ])
    result = parse_and_validate(file_bytes, 'cobros.csv', _sales_frame())

    assert [issue.rule_code for issue in result.issues] == [ValidationRule.UNKNOWN_INVOICE]
    assert result.summary.unmatched_rows == 1
    assert result.summary.collected_amount == 0.0


def test_collecting_more_than_invoiced_is_reported_and_kept():
    '''
        Over-collection is a fact of the client's data — a duplicated payment,
        a credit note recorded as a collection — so it travels as a code and
        the row stays.
    '''
    file_bytes = _collections_csv([
        {'Nro Factura': 'F-2', 'Fecha Cobro': '2026-03-10', 'Monto Cobrado': 800.0}
    ])
    result = parse_and_validate(file_bytes, 'cobros.csv', _sales_frame())

    assert [issue.rule_code for issue in result.issues] == [ValidationRule.OVERPAID_INVOICE]
    assert result.summary.valid_rows == 1


def test_a_payment_of_zero_breaks_the_contract():
    '''Collecting zero is not a payment: the row cannot pass as valid.'''
    file_bytes = _collections_csv([
        {'Nro Factura': 'F-1', 'Fecha Cobro': '2026-03-10', 'Monto Cobrado': 0.0}
    ])
    result = parse_and_validate(file_bytes, 'cobros.csv', _sales_frame())

    assert result.summary.valid_rows == 0
    assert ValidationRule.BELOW_MINIMUM in {issue.rule_code for issue in result.issues}


def test_auto_mode_stays_silent_on_a_file_without_payments():
    '''
        Scanning a sales upload must report nothing when there is no payments
        sheet: whoever sells cash should not see a broken contract they never
        filled in.
    '''
    sales_csv = pd.DataFrame([
        {'Fecha': '2026-03-10', 'Nro Factura': 'F-1', 'Cliente': 'Tienda',
         'Producto': 'Galleta', 'Cantidad': 2}
    ]).to_csv(index = False).encode('utf-8')

    result = parse_and_validate(sales_csv, 'ventas.csv', _sales_frame(), auto = True)

    assert not result.issues
    assert result.summary.valid_rows == 0
    assert result.accepted.empty


def test_the_payments_sheet_is_found_inside_a_two_sheet_workbook():
    '''
        The published template is one workbook with both sheets, so a client
        who returns it filled in loads sales and payments in a single upload.
    '''
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine = 'openpyxl') as writer:
        pd.DataFrame([
            {'Fecha': '2026-03-10', 'Nro Factura': 'F-1', 'Cliente': 'Tienda',
             'Producto': 'Galleta', 'Cantidad': 2}
        ]).to_excel(writer, sheet_name = SALES_SHEET, index = False)
        pd.DataFrame([
            {'Nro Factura': 'F-1', 'Fecha Cobro': '2026-03-20', 'Monto Cobrado': 500.0}
        ]).to_excel(writer, sheet_name = COLLECTIONS_SHEET, index = False)

    found = read_collections(buffer.getvalue(), 'plantilla.xlsx', auto = True)
    assert found is not None
    assert len(found) == 1

    result = parse_and_validate(
        buffer.getvalue(), 'plantilla.xlsx', _sales_frame(), auto = True
    )
    assert not result.issues
    assert result.summary.collected_amount == 500.0


def test_sales_credit_columns_are_normalized_and_validated():
    '''
        'Crédito' with an accent, lowercase 'contado' and 'CREDITO' are the same
        thing: the contract accepts them and stores them in its own spelling. A
        condition that does not exist cannot pass as cash by omission.
    '''
    good = pd.DataFrame([
        {'Fecha': '2026-03-10', 'Nro Factura': 'F-1', 'Cliente': 'Tienda',
         'Producto': 'Galleta', 'Cantidad': 2, 'Condicion Venta': 'Crédito',
         'Plazo Dias': 30, 'Responsable Cobro': 'Juan Pérez'},
        {'Fecha': '2026-03-11', 'Nro Factura': 'F-2', 'Cliente': 'Market',
         'Producto': 'Leche', 'Cantidad': 1, 'Condicion Venta': 'contado',
         'Plazo Dias': 0, 'Responsable Cobro': 'Juan Pérez'},
    ]).to_csv(index = False).encode('utf-8')

    result = parse_sales(good, 'ventas.csv')
    assert not result.issues
    assert list(result.accepted['payment_terms']) == ['CREDITO', 'CONTADO']
    assert list(result.accepted['credit_days']) == [30, 0]

    bad = pd.DataFrame([
        {'Fecha': '2026-03-10', 'Nro Factura': 'F-1', 'Cliente': 'Tienda',
         'Producto': 'Galleta', 'Cantidad': 2, 'Condicion Venta': 'Cheque'}
    ]).to_csv(index = False).encode('utf-8')

    rejected = parse_sales(bad, 'ventas.csv')
    assert rejected.issues
    assert 'payment_terms' in {issue.column for issue in rejected.issues}
