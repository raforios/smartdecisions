'''
    Canonical sales Excel template builder (plantilla de ventas).

    Produces the workbook the INGEST service serves via
    `GET /v1/ingest/template/file`. The headers are **friendly Spanish names**
    (Fecha, Nro Factura, Cliente, Producto, …) so a Bolivian sales center can
    fill it without any technical knowledge. On upload, `column_mapper`
    translates these headers to the internal canonical names the engine uses.

    The workbook has:
      - A 'Ventas' sheet with the friendly headers and example rows (two
        invoices forming baskets, so the affinity engine has signal).
      - An 'Instrucciones' sheet documenting each column and whether it is
        required.
'''
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import pandas as pd


# The template lives in the OS temp dir because the Lambda package (/var/task)
# is a read-only filesystem. /tmp is the only writable path at runtime and is
# also writable in local dev, so a single location works everywhere.
TEMPLATE_FILENAME = 'template_ventas_v1.xlsx'
TEMPLATE_PATH = Path(tempfile.gettempdir()) / TEMPLATE_FILENAME


@dataclass(frozen = True)
class TemplateColumn:
    '''One column of the downloadable template: friendly header + metadata.'''
    header: str          # Friendly Spanish header shown to the client.
    required: bool
    description: str


# Order + contract of the client-facing template. Required columns are the
# minimum the analysis needs; the rest enrich the dashboard and route module.
TEMPLATE_COLUMNS: list[TemplateColumn] = [
    TemplateColumn('Fecha', True,
                   'Fecha de la venta. Formato dd/mm/aaaa.'),
    TemplateColumn('Nro Factura', True,
                   'Número de factura o venta. Agrupa los productos comprados juntos.'),
    TemplateColumn('Cliente', True,
                   'Nombre del cliente o punto de venta.'),
    TemplateColumn('Zona', False,
                   'Zona o barrio del cliente (para análisis por sector).'),
    TemplateColumn('Ciudad', False,
                   'Ciudad del cliente.'),
    TemplateColumn('Vendedor', False,
                   'Vendedor o preventista que realizó la venta.'),
    TemplateColumn('Latitud', False,
                   'Latitud del cliente (opcional; habilita la optimización de rutas).'),
    TemplateColumn('Longitud', False,
                   'Longitud del cliente (opcional; habilita la optimización de rutas).'),
    TemplateColumn('Producto', True,
                   'Nombre del producto vendido.'),
    TemplateColumn('Categoria', False,
                   'Categoría o línea del producto (ej. Galletas, Lácteos).'),
    TemplateColumn('Cantidad', True,
                   'Unidades vendidas. Debe ser mayor que 0.'),
    TemplateColumn('Precio Unitario', False,
                   'Precio por unidad. Ayuda a valorar las oportunidades en Bs.'),
    TemplateColumn('Costo Unitario', False,
                   'Costo por unidad. Habilita los indicadores de margen y rentabilidad.'),
    TemplateColumn('Monto Total', False,
                   'Monto total de la línea (Cantidad × Precio Unitario).'),
]

# Gross margin used only to fill the example rows, so the downloaded template
# shows a coherent Precio/Costo pair instead of an empty column.
_EXAMPLE_MARGIN: float = 0.28

HEADERS: list[str] = [column.header for column in TEMPLATE_COLUMNS]


@dataclass(frozen = True)
class ExampleClient:
    '''One example buyer: the fields repeated across every line of its invoice.'''
    invoice: str
    name: str
    zone: str
    city: str
    seller: str
    latitude: float
    longitude: float


@dataclass(frozen = True)
class ExampleItem:
    '''One example product line within an invoice.'''
    product: str
    category: str
    quantity: int
    price: float


def _example_line(client: ExampleClient, item: ExampleItem) -> dict:
    '''
        Builds one example row keyed by the friendly headers.

        Args:
            client (ExampleClient): Buyer repeated across the invoice's lines.
            item (ExampleItem): Product line being written.

        Returns:
            dict: One row of the 'Ventas' sheet.
    '''
    return {
        'Fecha': date(2026, 1, 12), 'Nro Factura': client.invoice,
        'Cliente': client.name, 'Zona': client.zone, 'Ciudad': client.city,
        'Vendedor': client.seller, 'Latitud': client.latitude,
        'Longitud': client.longitude, 'Producto': item.product,
        'Categoria': item.category, 'Cantidad': item.quantity,
        'Precio Unitario': item.price,
        'Costo Unitario': round(item.price * (1 - _EXAMPLE_MARGIN), 2),
        'Monto Total': round(item.quantity * item.price, 2),
    }


# Two invoices (Nro Factura) forming baskets, so the affinity engine has signal.
_EXAMPLE_BASKETS: list[tuple[ExampleClient, list[ExampleItem]]] = [
    (
        ExampleClient('F-1001', 'Tienda Doña Rosa', 'Sur', 'La Paz',
                      'Juan Pérez', -16.5450, -68.1200),
        [
            ExampleItem('Galleta Integral 200g', 'Galletas', 12, 8.5),
            ExampleItem('Chocolate Barra 90g', 'Chocolates', 8, 6.0),
        ],
    ),
    (
        ExampleClient('F-1002', 'Mini-market El Sol', 'Centro', 'La Paz',
                      'Ana Vargas', -16.4980, -68.1330),
        [
            ExampleItem('Galleta Integral 200g', 'Galletas', 24, 8.5),
            ExampleItem('Yogurt Natural 1L', 'Lácteos', 6, 15.0),
        ],
    ),
]

EXAMPLE_ROWS: list[dict] = [
    _example_line(client, item)
    for client, items in _EXAMPLE_BASKETS for item in items
]


def build_instructions_dataframe() -> pd.DataFrame:
    '''
        Builds the 'Instrucciones' sheet: one row per column with its
        requirement and description, in Spanish.
    '''
    return pd.DataFrame([
        {
            'Columna': column.header,
            'Obligatoria': 'Sí' if column.required else 'No',
            'Descripción': column.description,
        }
        for column in TEMPLATE_COLUMNS
    ])


def generate(output_path: Path) -> Path:
    '''
        Generates the sales template at the given path.

        Args:
            output_path (Path): Destination .xlsx file.

        Returns:
            Path: The path where the file was written.
    '''
    output_path.parent.mkdir(parents = True, exist_ok = True)

    ventas = pd.DataFrame(EXAMPLE_ROWS, columns = HEADERS)
    instrucciones = build_instructions_dataframe()

    with pd.ExcelWriter(output_path, engine = 'openpyxl') as writer:
        ventas.to_excel(writer, sheet_name = 'Ventas', index = False)
        instrucciones.to_excel(writer, sheet_name = 'Instrucciones', index = False)

        worksheet = writer.sheets['Ventas']
        for column_cells in worksheet.columns:
            max_length = max((len(str(cell.value or '')) for cell in column_cells), default = 12)
            worksheet.column_dimensions[column_cells[0].column_letter].width = \
                min(max_length + 2, 28)

    return output_path


def ensure_template() -> Path:
    '''
        Returns the path to the downloadable template, generating it in the
        writable temp dir on first use. Idempotent and self-healing: if the
        Lambda's /tmp was cleared between invocations, the next call rebuilds it.

        Returns:
            Path: The ready-to-stream template file.
    '''
    if not TEMPLATE_PATH.exists():
        generate(TEMPLATE_PATH)
    return TEMPLATE_PATH
