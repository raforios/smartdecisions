'''
    Generates the canonical sales Excel template (template_ventas_v1.xlsx).

    The template ships with:
      - A 'Ventas' sheet with the v1 contract headers and 3 example rows.
      - An 'Instrucciones' sheet documenting required vs optional columns.

    Run locally:
        python scripts/generate_template.py
    The file is written to ../assets/template_ventas_v1.xlsx by default.
'''
import argparse
from datetime import date
from pathlib import Path
import pandas as pd

from services.excel_validator import REQUIRED_COLUMNS, TEMPLATE_VERSION


DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / 'assets' / 'template_ventas_v1.xlsx'

EXAMPLE_ROWS = [
    {
        'id_pedido': 'P-0001',
        'fecha': date(2026, 1, 12),
        'id_punto_venta': 'PDV-007',
        'nombre_pdv': 'Tienda Doña Rosa',
        'zona': 'Sur',
        'id_producto': 'SKU-A100',
        'nombre_producto': 'Galleta Integral 200g',
        'cantidad': 12,
        'precio_unitario': 8.5,
        'monto_total': 102.0,
    },
    {
        'id_pedido': 'P-0001',
        'fecha': date(2026, 1, 12),
        'id_punto_venta': 'PDV-007',
        'nombre_pdv': 'Tienda Doña Rosa',
        'zona': 'Sur',
        'id_producto': 'SKU-B200',
        'nombre_producto': 'Yogurt Natural 1L',
        'cantidad': 6,
        'precio_unitario': 15.0,
        'monto_total': 90.0,
    },
    {
        'id_pedido': 'P-0002',
        'fecha': date(2026, 1, 13),
        'id_punto_venta': 'PDV-012',
        'nombre_pdv': 'Mini-market El Sol',
        'zona': 'Centro',
        'id_producto': 'SKU-A100',
        'nombre_producto': 'Galleta Integral 200g',
        'cantidad': 24,
        'precio_unitario': 8.5,
        'monto_total': 204.0,
    },
]

COLUMN_ORDER = [
    'id_pedido', 'fecha', 'id_punto_venta', 'nombre_pdv', 'zona',
    'id_producto', 'nombre_producto', 'cantidad', 'precio_unitario', 'monto_total',
]


def build_instructions_dataframe() -> pd.DataFrame:
    '''
        Builds the 'Instrucciones' sheet content from the v1 contract.

        Returns:
            pd.DataFrame: One row per column, describing its requirement and use.
    '''
    rows = []
    for col in COLUMN_ORDER:
        required = col in REQUIRED_COLUMNS
        rows.append({
            'Columna': col,
            'Obligatoria': 'Sí' if required else 'No',
            'Descripción': _description_for(col),
        })
    return pd.DataFrame(rows)


def _description_for(column: str) -> str:
    '''
        Returns the canonical Spanish description for a template column.
    '''
    descriptions = {
        'id_pedido': 'Identificador del pedido. Agrupa los productos de una misma venta/visita.',
        'fecha': 'Fecha de la venta. Acepta formato ISO (aaaa-mm-dd) o dd/mm/aaaa.',
        'id_punto_venta': 'Identificador del punto de venta o cliente.',
        'nombre_pdv': 'Nombre legible del PdV (solo para la interfaz).',
        'zona': 'Zona geográfica del PdV (para análisis y rutas).',
        'id_producto': 'SKU o código del producto.',
        'nombre_producto': 'Nombre legible del producto (solo para la interfaz).',
        'cantidad': 'Unidades vendidas. Debe ser mayor que 0.',
        'precio_unitario': 'Precio por unidad. Necesario para calcular Drop Size en moneda.',
        'monto_total': 'Monto total de la línea. Se calcula comocantidad × precio_unitario.',
    }
    return descriptions.get(column, '')


def generate(output_path: Path) -> Path:
    '''
        Generates the v1 template at the given path.

        Args:
            output_path (Path): Destination .xlsx file.

        Returns:
            Path: The path where the file was written.
    '''
    output_path.parent.mkdir(parents = True, exist_ok = True)

    ventas = pd.DataFrame(EXAMPLE_ROWS, columns = COLUMN_ORDER)
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


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = \
        'Generates the SmartDecisions sales Excel template.')
    parser.add_argument(
        '--output',
        type = Path,
        default = DEFAULT_OUTPUT,
        help = f'Output path (default: {DEFAULT_OUTPUT}).'
    )
    args = parser.parse_args()
    written = generate(args.output)
    print(f'Generated template {TEMPLATE_VERSION} at: {written}')
