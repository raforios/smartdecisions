'''
    Builds the chart of accounts the client downloads, as a static Excel.

    The client fills the data template with account codes; this file is how it
    knows them. It is static (Rafael, 17-oct: no library from a CDN in the
    portal), so it is built **from the catalog in force** —FINANCE's own
    table, read through FINANCE's own function— and published with the
    portal. Whenever the ADMIN changes the catalog, run this and deploy the
    portal again.

        python -m tools.templates.build_finance_catalog
        python -m tools.templates.build_finance_catalog --out /ruta/catalogo.xlsx
'''
import argparse
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv
from openpyxl import Workbook
from openpyxl.styles import Font

ROOT = Path(__file__).resolve().parents[2]
FINANCE_PATH = ROOT / 'services' / 'finance'
sys.path.insert(0, str(FINANCE_PATH))
# The service validates its environment on import, so it is loaded first.
load_dotenv(FINANCE_PATH / '.env')

# pylint: disable=wrong-import-position
from schemas.finance import AccountType  # noqa: E402
from services.finance import list_accounts  # noqa: E402
# pylint: enable=wrong-import-position

PROFILE = 'deploy_ml'
REGION = 'us-east-1'
DEFAULT_OUT = ROOT / 'portal' / 'demo' / 'plantillas' / 'catalogo_cuentas.xlsx'

# The client reads the type by its name, never by its digit.
TYPE_NAMES = {
    AccountType.ASSET: 'Activo', AccountType.LIABILITY: 'Pasivo',
    AccountType.EQUITY: 'Patrimonio', AccountType.INCOME: 'Ingresos',
    AccountType.COST: 'Costos', AccountType.EXPENSE: 'Gastos',
}
YES_NO = {True: 'Sí', False: 'No', None: ''}
HEADERS = ['Código', 'Cuenta', 'Tipo', 'Grupo', 'Factura', 'Resta']
WIDTHS = (12, 55, 14, 10, 10, 8)


def build(path: Path) -> int:
    '''
        Writes the catalog: one row per group and account, groups in bold.

        Args:
            path (Path): Where to write it.

        Returns:
            int: How many rows it wrote.
    '''
    resource = boto3.Session(profile_name = PROFILE, region_name = REGION).resource('dynamodb')
    accounts = list_accounts(resource).accounts
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Catálogo'
    sheet.append(HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold = True)
    for account in accounts:
        sheet.append([account.account_code, account.name, TYPE_NAMES[account.account_type],
                      account.group_code or '', YES_NO[account.invoiced],
                      YES_NO[account.subtracts] if account.subtracts else ''])
        if account.group_code is None:
            for cell in sheet[sheet.max_row]:
                cell.font = Font(bold = True)
    for column, width in zip('ABCDEF', WIDTHS):
        sheet.column_dimensions[column].width = width
    workbook.save(path)
    return len(accounts)


def main() -> int:
    '''
        Entry point.

        Returns:
            int: 0 on success.
    '''
    parser = argparse.ArgumentParser(
        description = 'Construye el catálogo de cuentas en Excel desde el catálogo vigente.'
    )
    parser.add_argument('--out', type = Path, default = DEFAULT_OUT, help = 'Dónde escribirlo.')
    args = parser.parse_args()
    rows = build(args.out)
    print(f'{rows} cuentas y grupos · {args.out.stat().st_size:,} bytes → {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
