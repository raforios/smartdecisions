'''
    Import the official Supplies catalog from the source CSV files.

    Loads the accounting groups (grupo-contable.csv) as categories and the
    articles (articulos.csv) as items, deriving the units of measure on the
    fly. The legacy 'Codel old' column is intentionally ignored: it carries
    no meaning in the new system, so it is never read here.

    Drives the Supplies API over HTTP (same approach as seed_test_data.py) so
    it works regardless of where the database lives (local Docker, RDS, etc.).

    Usage examples:
        python import_catalog.py \
            --admin-email raforios@gmail.com \
            --admin-password '***'

        # Custom endpoints / csv location
        python import_catalog.py --admin-email ... --admin-password ... \
            --auth-url https://32652ile50.execute-api.us-east-1.amazonaws.com/v1/auth \
            --base-url http://localhost:3004/v1/supplies \
            --docs-dir ../docs

    Idempotency:
        Groups, units and items use `code` as the natural key; 409 Conflict
        responses are tolerated, so re-running does not create duplicates.
        Items are created with stock 0 — opening balances arrive later via
        the kardex / notas de ingreso, not through this importer.
'''
import argparse
import csv
import os
import sys
from typing import Dict, List, Optional, Tuple

import requests

# Reuse the HTTP helpers already shipped with the seed script (DRY). The path
# has to be set before the import, so the position is deliberate.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# pylint: disable=wrong-import-position,import-error
from seed_test_data import ApiError, _get_list, _post, login  # noqa: E402


# Items start empty; opening balances enter through the kardex, not here.
DEFAULT_MIN_STOCK = 0
DEFAULT_REPLENISHMENT_QTY = 0


def _read_csv(path: str) -> List[Dict[str, str]]:
    '''
        Reads a UTF-8 (BOM-tolerant) CSV into a list of row dicts.

        Args:
            path (str): Absolute path to the CSV file.

        Returns:
            list[dict[str, str]]: One dict per data row, keyed by header.

        Raises:
            FileNotFoundError: If the file does not exist.
    '''
    with open(path, encoding = 'utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def is_active(estado: str) -> bool:
    '''
        Maps the CSV 'Estado' column to a boolean flag.
    '''
    return estado.strip().upper() == 'ACTIVO'


def build_item_payload(row: Dict[str, str], category_id: int, unit_id: int) -> Dict[str, object]:
    '''
        Builds the /items create payload for a single article row.

        Only the meaningful columns are mapped; the legacy 'Codel old' column
        is never referenced, so it cannot leak into the new catalog.

        Args:
            row (dict): One row from articulos.csv.
            category_id (int): Resolved accounting group id.
            unit_id (int): Resolved unit of measure id.

        Returns:
            dict: Payload accepted by POST /v1/supplies/items.
    '''
    return {
        'code': row['Código'].strip(),
        'name': row['Descripción'].strip(),
        'category_id': category_id,
        'unit_id': unit_id,
        'min_stock': DEFAULT_MIN_STOCK,
        'default_replenishment_qty': DEFAULT_REPLENISHMENT_QTY,
        'is_active': is_active(row['Estado']),
    }


def import_groups(base_url: str, token: str, docs_dir: str) -> Dict[str, int]:
    '''
        Imports accounting groups (grupo-contable.csv) as categories.

        Args:
            base_url (str): Supplies API base URL.
            token (str): Bearer token of an ADMIN user.
            docs_dir (str): Directory holding the source CSV files.

        Returns:
            dict[str, int]: Map of upper-cased group name -> category id, used
            to resolve each item's 'Cuenta contable' foreign key.
    '''
    print('-- Grupos contables')
    rows = _read_csv(os.path.join(docs_dir, 'grupo-contable.csv'))
    for row in rows:
        payload = {
            'code': row['Código'].strip(),
            'name': row['Descripción'].strip(),
            'is_active': is_active(row['Estado']),
        }
        created = _post(base_url, '/categories', token, payload)
        marker = '+' if created else '='
        print(f'   {marker} {payload["code"]} {payload["name"]}')

    name_to_id: Dict[str, int] = {}
    for row in _get_list(base_url, '/categories?limit=500', token):
        name_to_id[row['name'].strip().upper()] = row['id']
    return name_to_id


def import_units(base_url: str, token: str, item_rows: List[Dict[str, str]]) -> Dict[str, int]:
    '''
        Creates the distinct units of measure referenced by the articles.

        Args:
            base_url (str): Supplies API base URL.
            token (str): Bearer token of an ADMIN user.
            item_rows (list[dict]): Article rows from articulos.csv.

        Returns:
            dict[str, int]: Map of upper-cased unit name -> unit id.
    '''
    print('-- Unidades de medida')
    names = sorted({
        row['Unidad de Medida'].strip()
        for row in item_rows if row['Unidad de Medida'].strip()
    })
    for name in names:
        payload = {
            'code': name,
            'name': name,
            'abbreviation': name[:10].lower(),
        }
        created = _post(base_url, '/units', token, payload)
        marker = '+' if created else '='
        print(f'   {marker} {name}')

    name_to_id: Dict[str, int] = {}
    for row in _get_list(base_url, '/units?limit=500', token):
        name_to_id[row['name'].strip().upper()] = row['id']
    return name_to_id


def _resolve_foreign_keys(
    row: Dict[str, str], lookups: Dict[str, Dict[str, int]]
) -> Optional[Tuple[int, int]]:
    '''
        Resolves an article row's accounting group and unit of measure.

        A row whose group or unit is unknown is reported and skipped rather
        than aborting the whole import, because a single bad line should not
        block a 382-article catalog.

        Args:
            row (dict): One row from articulos.csv.
            lookups (dict): {'groups': name->id, 'units': name->id} maps.

        Returns:
            tuple[int, int] | None: (category_id, unit_id), or None when either
                cannot be resolved.
    '''
    category_id = lookups['groups'].get(row['Cuenta contable'].strip().upper())
    unit_id = lookups['units'].get(row['Unidad de Medida'].strip().upper())
    if category_id is not None and unit_id is not None:
        return category_id, unit_id

    missing = 'grupo contable' if category_id is None else 'unidad'
    code = row['Código'].strip()
    print(f'   ! {code} omitido: {missing} no encontrado ({row["Cuenta contable"]})')
    return None


def import_items(
    base_url: str,
    token: str,
    item_rows: List[Dict[str, str]],
    lookups: Dict[str, Dict[str, int]],
) -> None:
    '''
        Imports the articles as items, resolving group and unit foreign keys.

        The 'Codel old' column is deliberately not read. Rows whose accounting
        group or unit cannot be resolved are skipped with a warning instead of
        aborting the whole import.

        Args:
            base_url (str): Supplies API base URL.
            token (str): Bearer token of an ADMIN user.
            item_rows (list[dict]): Article rows from articulos.csv.
            lookups (dict): {'groups': name->id, 'units': name->id} maps.
    '''
    print('-- Artículos')
    created_count = 0
    skipped_count = 0

    for row in item_rows:
        resolved = _resolve_foreign_keys(row, lookups)
        if resolved is None:
            skipped_count += 1
            continue

        category_id, unit_id = resolved
        if _post(base_url, '/items', token, build_item_payload(row, category_id, unit_id)):
            created_count += 1
        else:
            skipped_count += 1

    print(f'   Artículos creados: {created_count} | omitidos/existentes: {skipped_count}')


def main() -> int:
    '''
        Parses the CLI arguments and runs the full catalog import.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--admin-email', required = True)
    parser.add_argument('--admin-password', required = True)
    parser.add_argument('--auth-url', default = 'http://localhost:3000/v1/auth',
                        help = 'Base URL of the AUTH service (default local).')
    parser.add_argument('--base-url', default = 'http://localhost:3004/v1/supplies',
                        help = 'Base URL of the SUPPLIES service (default local).')
    parser.add_argument('--docs-dir',
                        default = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                               '..', 'docs'),
                        help = 'Directory holding grupo-contable.csv and articulos.csv.')
    args = parser.parse_args()

    docs_dir = os.path.abspath(args.docs_dir)
    try:
        print(f'Login en {args.auth_url} ...')
        token = login(args.auth_url, args.admin_email, args.admin_password)
        print('Login OK')

        item_rows = _read_csv(os.path.join(docs_dir, 'articulos.csv'))
        group_ids = import_groups(args.base_url, token, docs_dir)
        unit_ids = import_units(args.base_url, token, item_rows)
        import_items(args.base_url, token, item_rows,
                     {'groups': group_ids, 'units': unit_ids})
    except FileNotFoundError as exc:
        print(f'ERROR: archivo CSV no encontrado: {exc}', file = sys.stderr)
        return 3
    except ApiError as exc:
        print(f'ERROR: {exc}', file = sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(f'ERROR de red: {exc}', file = sys.stderr)
        return 2

    print('\nImportación de catálogo completada.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
