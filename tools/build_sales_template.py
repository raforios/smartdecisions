'''
    Builds and publishes the sales template the client downloads.

    It is generated **from the contract** and not by hand: `TEMPLATE_COLUMNS` in
    `schemas/ingest.py` is the single source of truth about which columns exist,
    which are mandatory and in what order they go. A template written apart
    diverges from the validator the day somebody adds a column, and the client
    finds out when their file is rejected.

    It lives in `tools/` and not inside the microservice because it is not part
    of the service: it is a maintenance task run when the contract changes. The
    published file is static and served from S3.

    Usage:
        python -m tools.build_sales_template            # reports what it would do
        python -m tools.build_sales_template --yes      # builds and uploads
        python -m tools.build_sales_template --yes --rows 5
'''
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

import boto3
import pandas as pd


# The microservice declares the contract; this script imports it instead of
# repeating it.
INGEST_PATH = Path(__file__).resolve().parent.parent / 'services' / 'ingest'
sys.path.insert(0, str(INGEST_PATH))

BUCKET = 'ml-data-file-handler'
PROFILE = 'deploy_ml'
SHEET_NAME = 'Ventas'

# Sample rows: enough for the format of each column to be understood —the date
# and the decimals above all— without anybody mistaking the example for real
# data.
SAMPLE_CLIENTS = [
    ('PDV-001', 'Tienda Doña Rosa', 'Zona Sur', 'La Paz', 'Occidente',
     'Tradicional', 'Juan Pérez', -16.5435, -68.0713),
    ('PDV-002', 'Market El Alto', 'Ciudad Satélite', 'El Alto', 'Occidente',
     'Tradicional', 'Juan Pérez', -16.5100, -68.1900),
    ('PDV-003', 'Super Central', 'Centro', 'Cochabamba', 'Valles',
     'Moderno', 'Ana Quispe', -17.3895, -66.1568),
]
SAMPLE_PRODUCTS = [
    ('SKU-100', 'Galleta Salada 200g', 'Galletas', 12.50, 8.20),
    ('SKU-200', 'Leche Entera 1L', 'Lácteos', 7.80, 5.40),
    ('SKU-300', 'Chocolate Barra 90g', 'Confitería', 15.00, 9.75),
]


def _sample_rows(count: int) -> List[Dict[str, Any]]:
    '''
        Builds the sample rows that accompany the headers.

        Args:
            count (int): How many rows to generate.

        Returns:
            List[Dict[str, Any]]: Rows ready for the DataFrame.
    '''
    start = date.today().replace(day = 1) - timedelta(days = 60)
    rows: List[Dict[str, Any]] = []

    for index in range(count):
        client = SAMPLE_CLIENTS[index % len(SAMPLE_CLIENTS)]
        product = SAMPLE_PRODUCTS[index % len(SAMPLE_PRODUCTS)]
        quantity = float(2 + (index % 5))
        rows.append({
            'Fecha': start + timedelta(days = index * 3),
            'Nro Factura': f'F-{1000 + index}',
            'Cliente': client[1],
            'Zona': client[2],
            'Ciudad': client[3],
            'Region': client[4],
            'Canal': client[5],
            'Vendedor': client[6],
            'Latitud': client[7],
            'Longitud': client[8],
            'Producto': product[1],
            'Categoria': product[2],
            'Cantidad': quantity,
            'Precio Unitario': product[3],
            'Costo Unitario': product[4],
            'Monto Total': round(quantity * product[3], 2),
            # Credit is alternated on purpose, so it is visible that both
            # conditions coexist in the same file and that the term of a cash
            # sale is zero.
            'Condicion Venta': 'CREDITO' if index % 3 else 'CONTADO',
            'Plazo Dias': (15, 30, 60)[index % 3] if index % 3 else 0,
            'Fecha Vencimiento': '',
            'Responsable Cobro': client[6],
            'Limite Credito': 5000.00,
        })
    return rows


def _sample_collections(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    '''
        Builds the sample payments of the credit sales.

        One of them is paid in two instalments: that is what has to be seen to
        understand that an invoice takes several rows and that the balance is
        whatever is missing.

        Args:
            rows (List[Dict[str, Any]]): Rows of the sales sheet.

        Returns:
            List[Dict[str, Any]]: Rows of the collections sheet.
    '''
    credit = [row for row in rows if row['Condicion Venta'] == 'CREDITO']
    payments: List[Dict[str, Any]] = []

    for position, sale in enumerate(credit):
        due = sale['Fecha'] + timedelta(days = int(sale['Plazo Dias']))
        total = float(sale['Monto Total'])
        if position == 0:
            # Partial payment in two instalments: the invoice keeps an open
            # balance.
            payments.append({
                'Nro Factura': sale['Nro Factura'], 'Fecha Cobro': due,
                'Monto Cobrado': round(total / 2, 2), 'Medio': 'TRANSFERENCIA',
                'Responsable Cobro': sale['Responsable Cobro'],
            })
            payments.append({
                'Nro Factura': sale['Nro Factura'],
                'Fecha Cobro': due + timedelta(days = 15),
                'Monto Cobrado': round(total / 4, 2), 'Medio': 'EFECTIVO',
                'Responsable Cobro': sale['Responsable Cobro'],
            })
            continue
        if position % 2 == 0:
            # Cobrada completa y a tiempo.
            payments.append({
                'Nro Factura': sale['Nro Factura'], 'Fecha Cobro': due,
                'Monto Cobrado': total, 'Medio': 'TRANSFERENCIA',
                'Responsable Cobro': sale['Responsable Cobro'],
            })
        # The rest carry no payment: they are the example's open balance.

    return payments


def _sample_stock(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    '''
        Builds the sample stock snapshot: one row per product, dated on the last
        day the sales sheet covers.

        `Comprometido` is filled in on purpose, because it is the column that
        most needs explaining: it is what the ERP already committed in orders,
        it is read and never written, and `Existencia - Comprometido` is what is
        actually available to sell.

        Args:
            rows (List[Dict[str, Any]]): Rows of the sales sheet.

        Returns:
            List[Dict[str, Any]]: Rows of the stock sheet.
    '''
    last_day = max(row['Fecha'] for row in rows)
    seen: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        product = row['Producto']
        if product in seen:
            continue
        quantity = float(row['Cantidad'])
        seen[product] = {
            'Fecha': last_day,
            'Producto': product,
            # Twenty days of cover at the pace of this example, so the numbers
            # read as a warehouse and not as a random figure.
            'Existencia': round(quantity * 20, 0),
            'Comprometido': round(quantity * 2, 0),
            'En Transito': round(quantity * 5, 0),
            'Almacen': 'Central',
            'Costo Unitario': row['Costo Unitario'],
        }
    return list(seen.values())


def _sample_visits(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    '''
        Builds the sample visits: one per sale of the sheet, in the order the
        seller would have made them, with the hour and the outcome filled in
        so the two optional columns are visible in the template.

        Args:
            rows (List[Dict[str, Any]]): Rows of the sales sheet.

        Returns:
            List[Dict[str, Any]]: Rows of the visits sheet.
    '''
    visits: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        sold = index % 4 != 3
        visits.append({
            'Fecha': row['Fecha'],
            'Hora': f'{9 + (index % 8):02d}:{(index * 7) % 60:02d}',
            'Vendedor': row['Vendedor'],
            'Cliente': row['Cliente'],
            'Latitud': row['Latitud'],
            'Longitud': row['Longitud'],
            'Resultado': 'VENTA' if sold else 'SIN_VENTA',
            'Nro Factura': row['Nro Factura'] if sold else '',
        })
    return visits


def _build(path: Path, rows: int) -> List[str]:
    '''
        Writes the template file to disk.

        Args:
            path (Path): Where to write it.
            rows (int): Sample rows to include.

        Returns:
            List[str]: The headers written, in order.
    '''
    from schemas.ingest import ( # pylint: disable=import-outside-toplevel
        COLLECTION_COLUMNS,
        COLLECTION_HEADERS,
        COLLECTIONS_SHEET,
        STOCK_COLUMNS,
        STOCK_HEADERS,
        STOCK_SHEET,
        TEMPLATE_COLUMNS,
        TEMPLATE_HEADERS,
        VISIT_COLUMNS,
        VISIT_HEADERS,
        VISITS_SHEET
    )

    sample = _sample_rows(rows)
    frame = pd.DataFrame(sample, columns = list(TEMPLATE_HEADERS))

    with pd.ExcelWriter(path, engine = 'openpyxl') as writer:
        frame.to_excel(writer, index = False, sheet_name = SHEET_NAME)

        # The payments travel in the same workbook, on their own sheet: they
        # are filled in later —an invoice at 90 days is collected three months
        # on— but the client should not have to ask for a second file for that.
        pd.DataFrame(
            _sample_collections(sample), columns = list(COLLECTION_HEADERS)
        ).to_excel(writer, index = False, sheet_name = COLLECTIONS_SHEET)

        # The stock sheet is a snapshot: one row per product and day. It is
        # filled in daily while the sales sheet is filled in once, which is why
        # it also has its own upload endpoint.
        pd.DataFrame(
            _sample_stock(sample), columns = list(STOCK_HEADERS)
        ).to_excel(writer, index = False, sheet_name = STOCK_SHEET)

        # The visits are the executed side of the routes: what the seller's
        # system registered on the street. Coordinates and outcome are optional
        # there; the sample fills them so the reader sees what they look like.
        pd.DataFrame(
            _sample_visits(sample), columns = list(VISIT_HEADERS)
        ).to_excel(writer, index = False, sheet_name = VISITS_SHEET)

        # A second sheet with the rules. The client opening the template needs
        # to know what is mandatory before filling it in, not after the
        # validator rejects it.
        guide = pd.DataFrame([
            {
                'Hoja': sheet,
                'Columna': column.header,
                'Obligatoria': 'Sí' if column.template_required else 'No',
                'Formato': _human_type(column.dtype),
                'Valores admitidos': (
                    ' / '.join(column.rules.allowed) if column.rules.allowed else ''
                ),
            }
            for sheet, columns in ((SHEET_NAME, TEMPLATE_COLUMNS),
                                   (COLLECTIONS_SHEET, COLLECTION_COLUMNS),
                                   (STOCK_SHEET, STOCK_COLUMNS),
                                   (VISITS_SHEET, VISIT_COLUMNS))
            for column in columns
            if not column.filled_by_service
        ])
        guide.to_excel(writer, index = False, sheet_name = 'Instrucciones')

    return list(TEMPLATE_HEADERS)


def _human_type(dtype: str) -> str:
    '''
        Translates the internal dtype into something a person understands.

        Args:
            dtype (str): Type declared in the contract.

        Returns:
            str: A readable description.
    '''
    if 'datetime' in dtype:
        return 'Fecha (DD/MM/AAAA)'
    if 'float' in dtype:
        return 'Número (usa punto decimal)'
    if 'Int' in dtype or 'int' in dtype:
        return 'Número entero'
    return 'Texto'


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 0 when it finished cleanly.
    '''
    parser = argparse.ArgumentParser(
        description = 'Construye la plantilla de ventas desde el contrato.'
    )
    parser.add_argument('--yes', action = 'store_true',
                        help = 'Construye y sube. Sin esto sólo informa.')
    parser.add_argument('--rows', type = int, default = 6,
                        help = 'Filas de ejemplo. Por defecto 6.')
    parser.add_argument('--key', default = 'ingest/templates/template_ventas_v1.xlsx',
                        help = 'Clave en S3. Debe coincidir con TEMPLATE_S3_KEY del .env.')
    args = parser.parse_args()

    target = Path('/tmp/template_ventas.xlsx')
    headers = _build(target, args.rows)

    print(f'Columnas ({len(headers)}): {", ".join(headers)}')
    print(f'Filas de ejemplo: {args.rows}')
    print(f'Archivo: {target} ({target.stat().st_size:,} bytes)')
    print(f'Destino: s3://{BUCKET}/{args.key}')

    if not args.yes:
        print('Simulación: no se subió nada. Repite con --yes.')
        return 0

    boto3.Session(profile_name = PROFILE, region_name = 'us-east-1').client('s3').upload_file(
        str(target), BUCKET, args.key,
        ExtraArgs = {
            'ContentType': ('application/vnd.openxmlformats-officedocument'
                            '.spreadsheetml.sheet')
        }
    )
    print('Plantilla publicada.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
