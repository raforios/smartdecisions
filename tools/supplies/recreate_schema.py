'''
    Recreates the Supplies schema from the SQLAlchemy models.

    SQLAlchemy's create_all() only creates *missing* tables: it never alters an
    existing one. So a table that predates a model change (the kardex gaining
    its PEPS/FIFO valuation columns, for example) stays stale forever and the
    service fails at runtime with "Unknown column".

    This tool drops every t_supplies_* table — including ones no longer in the
    models — and recreates the schema exactly as the models declare it.

    DESTRUCTIVE: every row is lost. Intended for demo/test databases that are
    reseeded afterwards with tools/supplies + the catalog importer.

    Usage:
        python tools/supplies/recreate_schema.py --yes
        python tools/supplies/recreate_schema.py            # dry run
'''
import argparse
import os
import sys
from typing import List

from sqlalchemy import text

_SERVICE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'services', 'supplies')
)
# The service reads its own .env relative to the working directory, and its
# modules import each other by top-level name, so both have to be in place
# before importing anything from it.
os.chdir(_SERVICE_DIR)
sys.path.insert(0, _SERVICE_DIR)

# pylint: disable=wrong-import-position
from models.supplies import Base            # noqa: E402
from services.db_connection import ENGINE   # noqa: E402

_TABLE_PREFIX = 't_supplies_'


def list_live_tables() -> List[str]:
    '''
        Returns the Supplies tables currently present in the database.

        Returns:
            list[str]: Table names, alphabetically sorted.
    '''
    with ENGINE.connect() as connection:
        rows = connection.execute(text('SHOW TABLES')).fetchall()
    return sorted(row[0] for row in rows if row[0].startswith(_TABLE_PREFIX))


def drop_tables(tables: List[str]) -> None:
    '''
        Drops the given tables, ignoring foreign keys during the operation.

        Dropping in dependency order is not enough here: obsolete tables that
        are no longer in the models still hold foreign keys to the live ones,
        so the constraint checks are disabled for the duration.

        Args:
            tables (list[str]): Table names to drop.
    '''
    with ENGINE.begin() as connection:
        connection.execute(text('SET FOREIGN_KEY_CHECKS = 0'))
        for table in tables:
            connection.execute(text(f'DROP TABLE IF EXISTS `{table}`'))
            print(f'   - {table}')
        connection.execute(text('SET FOREIGN_KEY_CHECKS = 1'))


def main() -> int:
    '''
        Parses the CLI arguments and recreates the schema.

        Returns:
            int: Process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--yes', action = 'store_true',
                        help = 'Confirm the destructive drop. Without it, only reports.')
    args = parser.parse_args()

    live = list_live_tables()
    model_tables = sorted(Base.metadata.tables)
    obsolete = sorted(set(live) - set(model_tables))

    print(f'Base de datos : {ENGINE.url.database} @ {ENGINE.url.host}:{ENGINE.url.port}')
    print(f'Tablas vivas  : {len(live)}')
    print(f'Tablas modelo : {len(model_tables)}')
    if obsolete:
        print(f'Obsoletas     : {", ".join(obsolete)}')

    if not args.yes:
        print('\nDry run: nada fue modificado. Vuelve a ejecutar con --yes para aplicar.')
        return 0

    print('\n-- Eliminando tablas')
    drop_tables(live)

    print('\n-- Recreando el esquema desde los modelos')
    Base.metadata.create_all(bind = ENGINE)
    for table in model_tables:
        print(f'   + {table}')

    remaining = list_live_tables()
    missing = sorted(set(model_tables) - set(remaining))
    if missing:
        print(f'\nERROR: no se crearon {missing}')
        return 1

    print(f'\nEsquema recreado: {len(remaining)} tablas, 0 filas. '
          'Siembra el catálogo con scripts/import_catalog.py.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
