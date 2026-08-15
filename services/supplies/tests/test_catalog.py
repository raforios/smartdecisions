'''
    Tests for the catalog listing filters.

    The catalog screen is the entry point of the warehouse: staff find an item
    by typing part of its code or description, or by narrowing to one accounting
    group. These tests pin that behaviour, including the ordering by code the
    users rely on to scan the list.
'''
import asyncio

from controllers.catalog import list_items_controller
from models.supplies import Category, Item, Unit
from schemas.catalog import ItemFilterSchema


def _build_catalog(session):
    '''
        Seeds two accounting groups with two items each, deliberately inserted
        out of code order so the ordering assertion is meaningful.
    '''
    paper = Category(code = '32100', name = 'PAPEL', is_active = True)
    boots = Category(code = '34500', name = 'CALZADOS', is_active = True)
    unit = Unit(code = 'PZA', name = 'PIEZA', abbreviation = 'pza', is_active = True)
    session.add_all([paper, boots, unit])
    session.flush()

    definitions = (
        ('30002', 'BOTAS DE GOMA INDUSTRIAL', boots.id),
        ('30001', 'PAPEL BOND TAMANO CARTA', paper.id),
        ('30004', 'BOTINES DE CUERO', boots.id),
        ('30003', 'PAPEL HIGIENICO JUMBO', paper.id),
    )
    for code, name, category_id in definitions:
        session.add(Item(
            code = code, name = name, category_id = category_id, unit_id = unit.id,
            min_stock = 0, current_stock = 0, default_replenishment_qty = 0, is_active = True,
        ))
    session.commit()
    return paper, boots


def test_items_are_listed_ordered_by_code(db_session):
    '''The catalog always comes back in code order regardless of insertion order.'''
    _build_catalog(db_session)
    items = asyncio.run(list_items_controller(db_session, ItemFilterSchema()))
    assert [item.code for item in items] == ['30001', '30002', '30003', '30004']


def test_filter_by_accounting_group(db_session):
    '''The "TODOS / one group" selector narrows the list to that group only.'''
    paper, _ = _build_catalog(db_session)
    items = asyncio.run(
        list_items_controller(db_session, ItemFilterSchema(category_id = paper.id))
    )
    assert [item.code for item in items] == ['30001', '30003']


def test_search_matches_code_and_description(db_session):
    '''Free text hits either the code or the description, as the screen promises.'''
    _build_catalog(db_session)

    by_name = asyncio.run(list_items_controller(db_session, ItemFilterSchema(search = 'BOTAS')))
    assert [item.code for item in by_name] == ['30002']

    by_code = asyncio.run(list_items_controller(db_session, ItemFilterSchema(search = '30004')))
    assert [item.code for item in by_code] == ['30004']


def test_search_and_group_filters_combine(db_session):
    '''Both filters apply together instead of one overriding the other.'''
    _, boots = _build_catalog(db_session)
    items = asyncio.run(list_items_controller(
        db_session, ItemFilterSchema(search = 'BOT', category_id = boots.id)
    ))
    assert [item.code for item in items] == ['30002', '30004']
