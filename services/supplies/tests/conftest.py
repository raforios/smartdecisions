'''
    Shared pytest fixtures for the Supplies service.

    Provides an isolated in-memory SQLite session so domain logic (PEPS/FIFO
    consumption, entry registration) can be exercised without a real MySQL
    instance. The environment bootstrap lives in tests/__init__.py, which runs
    before this module is imported.
'''
import asyncio
from decimal import Decimal
from typing import Optional

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from controllers.entry import create_entry_controller
# Imported from models (not from db_connection) so that loading Base also
# registers every mapped class on its metadata — otherwise create_all would
# find an empty schema.
from models.supplies import Base, Category, Item, Unit
from schemas.entry import EntryCreateSchema, EntryDetailCreateSchema
from schemas.enums import EntryTypeEnum


@pytest.fixture()
def db_session():
    '''
        Yields a session bound to a fresh in-memory SQLite database with the
        full schema created. The database is discarded after each test.
    '''
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(bind = engine)
    session_factory = sessionmaker(bind = engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def make_catalog_item(session: Session, code: str = 'IT-1', min_stock: int = 0) -> Item:
    '''
        Creates a minimal active catalog (group + unit + item) and returns the
        item. Shared by every suite that needs something to move around.

        Args:
            session (Session): Active test session.
            code (str): Item code. Defaults to 'IT-1'.
            min_stock (int): Minimum the warehouse keeps. Defaults to 0.

        Returns:
            Item: The persisted item, with zero stock.
    '''
    category = Category(code = 'G-1', name = 'GRUPO', is_active = True)
    unit = Unit(code = 'PZA', name = 'PIEZA', abbreviation = 'pza', is_active = True)
    session.add_all([category, unit])
    session.flush()
    item = Item(
        code = code, name = 'Item de prueba',
        category_id = category.id, unit_id = unit.id,
        min_stock = Decimal(min_stock), current_stock = 0, reserved_stock = 0,
        default_replenishment_qty = 0, is_active = True,
    )
    session.add(item)
    session.commit()
    return item


def register_entry(
    session: Session,
    item: Item,
    quantity: int | str,
    unit_cost: int | str = 1,
    supplier_id: Optional[int] = None,
):
    '''
        Registers a one-line Nota de Ingreso, creating a single cost layer.

        Args:
            session (Session): Active test session.
            item (Item): Item being received.
            quantity (int | str): Units entering the warehouse.
            unit_cost (int | str): Cost of the layer. Defaults to 1.
            supplier_id (Optional[int]): Registered vendor, when the test
                exercises the supplier link.

        Returns:
            EntryDetailedResponseSchema: The registered note.
    '''
    payload = EntryCreateSchema(
        entry_type = EntryTypeEnum.COMPRA,
        supplier_id = supplier_id,
        details = [EntryDetailCreateSchema(
            item_id = item.id,
            quantity = Decimal(quantity),
            unit_cost = Decimal(unit_cost),
        )],
    )
    return asyncio.run(create_entry_controller(session, payload, created_by = 'almacen'))
