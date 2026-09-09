'''
    Brings an existing Supplies database up to the suppliers + reservations
    model without losing data.

    create_all() only creates missing tables, so the columns added to live
    tables (Item.reserved_stock, Entry.supplier_id, the requester identity on
    Request) never appear on a database that already exists. This tool adds
    exactly what is missing and then rebuilds the reservations from the open
    requests, so the numbers are right from the first screen.

    Idempotent: running it twice is a no-op.

    Usage:
        python tools/supplies/migrate_suppliers_and_reservations.py            # dry run
        python tools/supplies/migrate_suppliers_and_reservations.py --yes
'''
import argparse
import os
import sys
from typing import List, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker

_SERVICE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'services', 'supplies')
)
# The service reads its own .env relative to the working directory, and its
# modules import each other by top-level name, so both have to be in place
# before importing anything from it.
os.chdir(_SERVICE_DIR)
sys.path.insert(0, _SERVICE_DIR)

# pylint: disable=wrong-import-position,import-error
from models.supplies import Base                                 # noqa: E402
from services.db_connection import ENGINE                        # noqa: E402
from services.supplies_logic import recalculate_reserved_stock   # noqa: E402

# (table, column, DDL) triples applied only when the column is absent.
_COLUMNS: List[Tuple[str, str, str]] = [
    ('t_supplies_item', 'reserved_stock',
     'ADD COLUMN reserved_stock DECIMAL(14,4) NOT NULL DEFAULT 0'),
    ('t_supplies_entry', 'supplier_id',
     'ADD COLUMN supplier_id INT NULL, '
     'ADD INDEX ix_t_supplies_entry_supplier_id (supplier_id), '
     'ADD CONSTRAINT fk_t_supplies_entry_supplier '
     'FOREIGN KEY (supplier_id) REFERENCES t_supplies_supplier(id)'),
    ('t_supplies_request', 'requester_name',
     'ADD COLUMN requester_name VARCHAR(200) NULL'),
    ('t_supplies_request', 'requester_position',
     'ADD COLUMN requester_position VARCHAR(200) NULL'),
    ('t_supplies_request', 'requester_unit',
     'ADD COLUMN requester_unit VARCHAR(200) NULL'),
]


def pending_columns() -> List[Tuple[str, str, str]]:
    '''
        Returns the column additions this database still needs.

        Returns:
            list[tuple[str, str, str]]: (table, column, DDL) still missing.
    '''
    inspector = inspect(ENGINE)
    live_tables = set(inspector.get_table_names())
    pending = []
    for table, column, ddl in _COLUMNS:
        if table not in live_tables:
            continue
        existing = {col['name'] for col in inspector.get_columns(table)}
        if column not in existing:
            pending.append((table, column, ddl))
    return pending


def create_missing_tables() -> List[str]:
    '''
        Creates tables declared by the models but absent from the database
        (t_supplies_supplier on an older install).

        Returns:
            list[str]: Names of the tables that were created.
    '''
    before = set(inspect(ENGINE).get_table_names())
    Base.metadata.create_all(bind = ENGINE)
    after = set(inspect(ENGINE).get_table_names())
    return sorted(after - before)


def apply_columns(pending: List[Tuple[str, str, str]]) -> None:
    '''
        Runs the ALTER TABLE statements for the missing columns.

        Args:
            pending (list[tuple[str, str, str]]): Additions to apply.
    '''
    with ENGINE.begin() as connection:
        for table, column, ddl in pending:
            connection.execute(text(f'ALTER TABLE {table} {ddl}'))
            print(f'   + {table}.{column}')


def main() -> None:
    '''
        Reports what is missing and, with --yes, applies it and rebuilds the
        materialized reservations.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--yes', action = 'store_true',
                        help = 'Apply the changes (otherwise only reports them).')
    args = parser.parse_args()

    pending = pending_columns()
    print('-- Columnas faltantes:', len(pending))
    for table, column, _ in pending:
        print(f'   . {table}.{column}')

    if not args.yes:
        print('\nDry run. Vuelve a ejecutar con --yes para aplicar.')
        return

    created = create_missing_tables()
    for table in created:
        print(f'   + tabla {table}')
    if pending:
        apply_columns(pending)

    session = sessionmaker(bind = ENGINE)()
    try:
        changed = recalculate_reserved_stock(session)
        session.commit()
        print(f'-- Reservas recalculadas: {changed} item(s) actualizados.')
    finally:
        session.close()

    print('Listo.')


if __name__ == '__main__':
    main()
