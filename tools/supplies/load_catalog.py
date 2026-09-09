'''
    Loads the official Supplies catalog straight into the database.

    Same source of truth as scripts/import_catalog.py (docs/grupo-contable.csv
    and docs/articulos.csv, with the legacy 'Codel old' column ignored), but it
    writes through SQLAlchemy instead of the HTTP API. That makes it usable on
    a local database without an AUTH token, which is what a developer setting
    up their environment actually needs. The HTTP importer stays the right tool
    for remote environments, where the database is not reachable directly.

    The row mapping itself is imported from scripts/import_catalog.py so both
    paths cannot drift apart.

    Idempotent: `code` is the natural key, existing rows are left untouched.
    Items are created with stock 0 — opening balances arrive through a Nota de
    Ingreso, never through this loader.

    Usage:
        python tools/supplies/load_catalog.py
        python tools/supplies/load_catalog.py --dry-run
'''
import argparse
import os
import sys
from typing import Dict, List

_SERVICE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'services', 'supplies')
)
# The service reads its .env relative to the working directory and its modules
# import each other by top-level name, so both must be set before importing it.
os.chdir(_SERVICE_DIR)
sys.path.insert(0, _SERVICE_DIR)
sys.path.insert(0, os.path.join(_SERVICE_DIR, 'scripts'))

# pylint: disable=wrong-import-position
from sqlalchemy.orm import Session                          # noqa: E402

from import_catalog import (                                # noqa: E402  pylint: disable=import-error
    build_item_payload,
    is_active,
)
from models.supplies import Category, Item, Unit            # noqa: E402
from services.db_connection import ENGINE                   # noqa: E402

_DOCS_DIR = os.path.join(_SERVICE_DIR, 'docs')


def _read_csv(name: str) -> List[Dict[str, str]]:
    '''
        Reads one of the source CSV files under docs/ into row dicts.

        Args:
            name (str): File name inside docs/.

        Returns:
            list[dict[str, str]]: One dict per data row, keyed by header.
    '''
    import csv  # pylint: disable=import-outside-toplevel
    with open(os.path.join(_DOCS_DIR, name), encoding = 'utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def load_groups(session: Session) -> Dict[str, int]:
    '''
        Creates the accounting groups and returns their name -> id map.

        Args:
            session (Session): Active database session.

        Returns:
            dict[str, int]: Upper-cased group name -> category id, used to
                resolve each article's 'Cuenta contable'.
    '''
    existing = {row.code: row for row in session.query(Category).all()}
    created = 0
    for row in _read_csv('grupo-contable.csv'):
        code = row['Código'].strip()
        if code in existing:
            continue
        session.add(Category(
            code = code,
            name = row['Descripción'].strip(),
            is_active = is_active(row['Estado']),
        ))
        created += 1
    session.flush()
    print(f'   Grupos contables: {created} creados')
    return {row.name.strip().upper(): row.id for row in session.query(Category).all()}


def load_units(session: Session, article_rows: List[Dict[str, str]]) -> Dict[str, int]:
    '''
        Creates the distinct units of measure referenced by the articles.

        Args:
            session (Session): Active database session.
            article_rows (list[dict]): Rows from articulos.csv.

        Returns:
            dict[str, int]: Upper-cased unit name -> unit id.
    '''
    existing = {row.code for row in session.query(Unit).all()}
    names = sorted({
        row['Unidad de Medida'].strip()
        for row in article_rows if row['Unidad de Medida'].strip()
    })
    created = 0
    for name in names:
        if name in existing:
            continue
        session.add(Unit(
            code = name, name = name, abbreviation = name[:10].lower(), is_active = True,
        ))
        created += 1
    session.flush()
    print(f'   Unidades de medida: {created} creadas')
    return {row.name.strip().upper(): row.id for row in session.query(Unit).all()}


def load_items(session: Session, article_rows: List[Dict[str, str]],
               lookups: Dict[str, Dict[str, int]]) -> None:
    '''
        Creates the articles as items, resolving group and unit foreign keys.

        Rows whose accounting group or unit cannot be resolved are reported and
        skipped, so one bad line never blocks the whole catalog.

        Args:
            session (Session): Active database session.
            article_rows (list[dict]): Rows from articulos.csv.
            lookups (dict): {'groups': name->id, 'units': name->id} maps.
    '''
    existing = {row.code for row in session.query(Item).all()}
    created = skipped = unresolved = 0

    for row in article_rows:
        code = row['Código'].strip()
        if code in existing:
            skipped += 1
            continue
        category_id = lookups['groups'].get(row['Cuenta contable'].strip().upper())
        unit_id = lookups['units'].get(row['Unidad de Medida'].strip().upper())
        if category_id is None or unit_id is None:
            missing = 'grupo contable' if category_id is None else 'unidad'
            print(f'   ! {code} omitido: {missing} no encontrado')
            unresolved += 1
            continue
        session.add(Item(**build_item_payload(row, category_id, unit_id), current_stock = 0))
        created += 1

    print(f'   Artículos: {created} creados | {skipped} ya existían | {unresolved} sin resolver')


def main() -> int:
    '''
        Parses the CLI arguments and loads the whole catalog in one transaction.

        Returns:
            int: Process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--dry-run', action = 'store_true',
                        help = 'Roll back instead of committing.')
    args = parser.parse_args()

    print(f'Base de datos: {ENGINE.url.database} @ {ENGINE.url.host}:{ENGINE.url.port}')
    article_rows = _read_csv('articulos.csv')

    with Session(ENGINE) as session:
        groups = load_groups(session)
        units = load_units(session, article_rows)
        load_items(session, article_rows, {'groups': groups, 'units': units})

        if args.dry_run:
            session.rollback()
            print('\nDry run: se revirtió todo.')
            return 0

        session.commit()
        print(f'\nCatálogo cargado: {session.query(Category).count()} grupos, '
              f'{session.query(Unit).count()} unidades, {session.query(Item).count()} artículos.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
