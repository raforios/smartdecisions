'''
    Gives every catalog item an opening stock, above its minimum.

    Written for end-to-end testing: a freshly imported catalog has no stock at
    all, so requests cannot be created and the whole delivery flow is
    untestable.

    The stock is created through a real Nota de Ingreso, using the same
    controller the API uses. That is the point: a plain UPDATE of
    Item.current_stock would leave balances with no PEPS/FIFO cost layer
    behind them, and the first delivery would fail with "Insufficient cost
    layers" — the exact inconsistency that broke the previous database.

    Quantities and costs vary deterministically per item code, so reports show
    a realistic spread while every run stays reproducible.

    There is deliberately no dry-run: the entry controller owns its transaction
    and commits internally, so anything this tool did afterwards could not undo
    it. `--preview` reports what would be written without calling the controller
    at all, which is the only honest way to look before leaping here.

    Usage:
        python tools/supplies/seed_opening_stock.py
        python tools/supplies/seed_opening_stock.py --min-stock 5 --quantity 200
        python tools/supplies/seed_opening_stock.py --preview
'''
import argparse
import asyncio
import os
import sys
from decimal import Decimal
from typing import List

_SERVICE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'services', 'supplies')
)
# The service reads its .env relative to the working directory and its modules
# import each other by top-level name, so both must be set before importing it.
os.chdir(_SERVICE_DIR)
sys.path.insert(0, _SERVICE_DIR)

# pylint: disable=wrong-import-position
from sqlalchemy.orm import Session                                  # noqa: E402

from controllers.entry import create_entry_controller               # noqa: E402
from models.supplies import Item                                    # noqa: E402
from schemas.entry import EntryCreateSchema, EntryDetailCreateSchema  # noqa: E402
from schemas.enums import EntryTypeEnum                             # noqa: E402
from services.db_connection import ENGINE                           # noqa: E402

# Spread factors applied per item so the reports are not a flat line. Picked by
# the item code, which keeps every run identical.
_QUANTITY_SPREAD = (1.0, 1.5, 2.0, 0.75, 1.25)
_COST_SPREAD = (Decimal('1'), Decimal('2.5'), Decimal('7.4'), Decimal('15'), Decimal('48.9'))


def _variation(code: str, options: tuple):
    '''
        Picks one of the spread options deterministically from an item code.

        Args:
            code (str): Item code.
            options (tuple): Candidate values.

        Returns:
            The chosen option, stable across runs for the same code.
    '''
    return options[sum(ord(char) for char in code) % len(options)]


def _build_lines(items: List[Item], quantity: int) -> List[EntryDetailCreateSchema]:
    '''
        Builds one entry line per item, with its varied quantity and cost.

        Args:
            items (list[Item]): Items to stock.
            quantity (int): Base quantity before the per-item variation.

        Returns:
            list[EntryDetailCreateSchema]: Lines of the opening Nota de Ingreso.
    '''
    lines = []
    for item in items:
        factor = _variation(item.code, _QUANTITY_SPREAD)
        lines.append(EntryDetailCreateSchema(
            item_id = item.id,
            quantity = Decimal(str(round(quantity * factor))),
            unit_cost = _variation(item.code, _COST_SPREAD),
        ))
    return lines


def main() -> int:
    '''
        Sets the minimum stock and registers the opening Nota de Ingreso.

        Returns:
            int: Process exit code.
    '''
    parser = argparse.ArgumentParser(description = __doc__)
    parser.add_argument('--min-stock', type = int, default = 10,
                        help = 'Minimum stock assigned to every item (default 10).')
    parser.add_argument('--quantity', type = int, default = 100,
                        help = 'Base opening quantity before the per-item spread.')
    parser.add_argument('--created-by', default = 'almacen@bearsoft.com.bo',
                        help = 'Actor recorded on the entry and the kardex rows.')
    parser.add_argument('--preview', action = 'store_true',
                        help = 'Report what would be written, without writing it.')
    args = parser.parse_args()

    print(f'Base de datos: {ENGINE.url.database} @ {ENGINE.url.host}:{ENGINE.url.port}')

    with Session(ENGINE) as session:
        items = session.query(Item).filter(Item.is_active.is_(True)).order_by(Item.code).all()
        if not items:
            print('No hay ítems activos. Carga el catálogo primero con load_catalog.py.')
            return 1

        lines = _build_lines(items, args.quantity)
        if args.preview:
            total = sum(line.quantity * line.unit_cost for line in lines)
            print(f'\nPreview: {len(lines)} ítems, mínimo {args.min_stock}, '
                  f'total valorado {total}. Nada fue escrito.')
            return 0

        # A meaningful minimum is what makes "above the minimum" testable: with
        # min_stock 0 every request passes and the stock guard is never exercised.
        for item in items:
            item.min_stock = args.min_stock
        session.flush()

        payload = EntryCreateSchema(
            entry_type = EntryTypeEnum.REINGRESO,
            supplier = 'CARGA INICIAL DE INVENTARIO',
            observations = 'Stock de apertura generado para pruebas end-to-end.',
            details = lines,
        )
        record = asyncio.run(create_entry_controller(session, payload, args.created_by))

        below = session.query(Item).filter(Item.current_stock <= Item.min_stock).count()
        print(f'\nNota de Ingreso {record.code}: {len(items)} ítems, total {record.total}.')
        print(f'Stock mínimo fijado en {args.min_stock}. '
              f'Ítems en o por debajo del mínimo: {below}.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
