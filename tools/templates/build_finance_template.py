'''
    Builds the data template of the financial analysis.

    It is generated **from the contract** and not by hand: `ENTRY_COLUMNS` in
    FINANCE's `schemas/entries.py` is the single definition of which columns
    exist and in what order, and the words the client may write
    (Diaria/Mensual/Anual, Sí/No) come from the same module the validator
    reads. A template written apart diverges from the validator the day a
    column is added, and the client finds out when their file is refused.

    The cells that only take a few words carry a drop-down with exactly those
    words, and the date column is text, so Excel never turns «2026-03» into a
    day it invented.

        python -m tools.templates.build_finance_template
        python -m tools.templates.build_finance_template --out /ruta/plantilla.xlsx
'''
import argparse
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parents[2]
FINANCE_PATH = ROOT / 'services' / 'finance'
sys.path.insert(0, str(FINANCE_PATH))

# pylint: disable=wrong-import-position
from schemas.entries import ENTRY_COLUMNS  # noqa: E402
# pylint: enable=wrong-import-position

DEFAULT_OUT = Path('/tmp/plantilla_analisis_financiero.xlsx')
# Rows that carry the drop-downs and the text format, below the header.
_FILLABLE_ROWS = 2000

# What each column asks for, in the client's words. Keyed by API field, so a
# column added to the contract without its explanation fails here, loudly.
_GUIDE: dict[str, tuple[str, str, str]] = {
    'date': ('Sí', 'Texto: AAAA-MM-DD (diaria), AAAA-MM (mensual) o AAAA (anual)',
             'Nunca una fecha futura'),
    'periodicity': ('Sí', 'Lista', 'Diaria / Mensual / Anual. Un período, una sola'),
    'account_code': ('Sí', 'Texto', 'Un código del catálogo de cuentas (6.1.03), no un grupo'),
    'amount': ('Sí', 'Número en bolivianos, con punto decimal',
               'Siempre positivo: la aplicación sabe qué cuentas restan'),
    'note': ('No', 'Texto', 'Lo que quieras recordar de esa cifra'),
    'taxes_included': ('Sólo en ventas con factura', 'Lista',
                       'Sí (venta bruta) / No (líquida). La cuenta dice si lleva factura'),
}

# Plausible rows, so the format is understood at a glance: one month of a
# small shop and a past year loaded whole.
_SAMPLE_ROWS: list[dict[str, object]] = [
    {'date': '2026-01', 'periodicity': 'Mensual', 'account_code': '4.1.01',
     'amount': 85000, 'note': 'Ventas con factura', 'taxes_included': 'Sí'},
    {'date': '2026-01', 'periodicity': 'Mensual', 'account_code': '4.1.05',
     'amount': 12000, 'note': 'Ventas sin factura'},
    {'date': '2026-01', 'periodicity': 'Mensual', 'account_code': '6.1.03',
     'amount': 3500, 'note': 'Alquiler del local'},
    {'date': '2025', 'periodicity': 'Anual', 'account_code': '4.1.01',
     'amount': 940000, 'note': 'Año anterior completo', 'taxes_included': 'Sí'},
]

_LISTS: dict[str, str] = {
    'periodicity': '"Diaria,Mensual,Anual"',
    'taxes_included': '"Sí,No"',
}


def build(path: Path) -> list[str]:
    '''
        Writes the template: the data sheet first, because that is the one
        the reader takes, and the instructions second.

        Args:
            path (Path): Where to write it.

        Returns:
            list[str]: The headers written, in order.
    '''
    workbook = Workbook()
    data = workbook.active
    data.title = 'Datos'
    headers = [column.header for column in ENTRY_COLUMNS]
    data.append(headers)
    for sample in _SAMPLE_ROWS:
        data.append([sample.get(column.field) for column in ENTRY_COLUMNS])

    for position, column in enumerate(ENTRY_COLUMNS, start = 1):
        letter = data.cell(row = 1, column = position).column_letter
        data.column_dimensions[letter].width = max(14, len(column.header) + 4)
        cells = f'{letter}2:{letter}{_FILLABLE_ROWS}'
        if column.field == 'date':
            for row in data[cells]:
                row[0].number_format = '@'
        if column.field in _LISTS:
            choice = DataValidation(type = 'list', formula1 = _LISTS[column.field],
                                    allow_blank = True)
            data.add_data_validation(choice)
            choice.add(cells)

    guide = workbook.create_sheet('Instrucciones')
    guide.append(['Columna', 'Obligatoria', 'Formato', 'Valores admitidos'])
    for column in ENTRY_COLUMNS:
        guide.append([column.header, *_GUIDE[column.field]])
    for letter, width in zip('ABCD', (20, 22, 60, 60)):
        guide.column_dimensions[letter].width = width

    workbook.save(path)
    return headers


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 0 on success.
    '''
    parser = argparse.ArgumentParser(
        description = 'Construye la plantilla del análisis financiero.'
    )
    parser.add_argument('--out', type = Path, default = DEFAULT_OUT, help = 'Dónde escribirla.')
    args = parser.parse_args()
    headers = build(args.out)
    print(f'{len(headers)} columnas ({", ".join(headers)}) · '
          f'{args.out.stat().st_size:,} bytes → {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
