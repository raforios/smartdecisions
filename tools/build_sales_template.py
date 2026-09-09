'''
    Construye y publica la plantilla de ventas que el cliente descarga.

    Se genera **desde el contrato**, no a mano: `TEMPLATE_COLUMNS` en
    `schemas/ingest.py` es la única fuente de verdad sobre qué columnas existen,
    cuáles son obligatorias y en qué orden van. Una plantilla escrita aparte
    diverge del validador el día que alguien agrega una columna, y el cliente se
    entera cuando su archivo es rechazado.

    Vive en `tools/` y no dentro del microservicio porque no es parte del
    servicio: es una tarea de mantenimiento que se corre cuando el contrato
    cambia. El archivo publicado es estático y se sirve desde S3.

    Uso:
        python -m tools.build_sales_template            # informa qué haría
        python -m tools.build_sales_template --yes      # construye y sube
        python -m tools.build_sales_template --yes --rows 5
'''
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

import boto3
import pandas as pd


# El microservicio declara el contrato; este script lo importa en vez de
# repetirlo.
INGEST_PATH = Path(__file__).resolve().parent.parent / 'services' / 'ingest'
sys.path.insert(0, str(INGEST_PATH))

BUCKET = 'ml-data-file-handler'
PROFILE = 'deploy_ml'
SHEET_NAME = 'Ventas'

# Filas de ejemplo: suficientes para que se entienda el formato de cada columna
# —sobre todo la fecha y los decimales— sin que nadie confunda el ejemplo con
# datos reales.
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
        Arma las filas de ejemplo que acompañan a los encabezados.

        Args:
            count (int): Cuántas filas generar.

        Returns:
            List[Dict[str, Any]]: Filas listas para el DataFrame.
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
        })
    return rows


def _build(path: Path, rows: int) -> List[str]:
    '''
        Escribe el archivo de plantilla en disco.

        Args:
            path (Path): Dónde escribirlo.
            rows (int): Filas de ejemplo a incluir.

        Returns:
            List[str]: Encabezados escritos, en orden.
    '''
    from schemas.ingest import ( # pylint: disable=import-outside-toplevel
        TEMPLATE_COLUMNS,
        TEMPLATE_HEADERS
    )

    frame = pd.DataFrame(_sample_rows(rows), columns = list(TEMPLATE_HEADERS))

    with pd.ExcelWriter(path, engine = 'openpyxl') as writer:
        frame.to_excel(writer, index = False, sheet_name = SHEET_NAME)

        # Una segunda hoja con las reglas. El cliente que abre la plantilla
        # necesita saber qué es obligatorio antes de llenarla, no después de
        # que el validador se lo rechace.
        guide = pd.DataFrame([
            {
                'Columna': column.header,
                'Obligatoria': 'Sí' if column.template_required else 'No',
                'Formato': _human_type(column.dtype),
            }
            for column in TEMPLATE_COLUMNS
        ])
        guide.to_excel(writer, index = False, sheet_name = 'Instrucciones')

    return list(TEMPLATE_HEADERS)


def _human_type(dtype: str) -> str:
    '''
        Traduce el tipo interno a algo que una persona entienda.

        Args:
            dtype (str): Tipo declarado en el contrato.

        Returns:
            str: Descripción legible.
    '''
    if 'datetime' in dtype:
        return 'Fecha (DD/MM/AAAA)'
    if 'float' in dtype:
        return 'Número (usa punto decimal)'
    return 'Texto'


def main() -> int:
    '''
        Punto de entrada.

        Returns:
            int: 0 si terminó bien.
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
