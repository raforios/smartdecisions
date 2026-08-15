'''
    Tests for the PEPS/FIFO valuation logic.

    Cover both entry registration (cost-layer creation + valued kardex IN) and
    the oldest-first consumption that splits a delivery across layers, tagging
    each OUT row with its own cost and source Nota de Ingreso.
'''
from decimal import Decimal

import pytest

from models.supplies import EntryDetail, Item, KardexMovement
from schemas.enums import MovementTypeEnum, ReferenceTypeEnum
from services.exceptions import InvalidInputError
from services.supplies_logic import MovementReference, OutflowSpec, consume_stock_fifo
from tests.conftest import make_catalog_item, register_entry


def _make_item(session, code = 'IT-1') -> Item:
    '''
        Creates a minimal active catalog (group + unit + item) and returns it.
    '''
    return make_catalog_item(session, code = code)


def _register_layer(session, item, quantity, unit_cost) -> None:
    '''
        Registers a one-line Nota de Ingreso creating a single cost layer.
    '''
    register_entry(session, item, quantity, unit_cost)


def _kardex(session, item, movement_type = None):
    query = session.query(KardexMovement).filter(KardexMovement.item_id == item.id)
    if movement_type is not None:
        query = query.filter(KardexMovement.movement_type == movement_type)
    return query.order_by(KardexMovement.id.asc()).all()


def test_entry_creates_cost_layer_and_valued_in(db_session):
    '''A Nota de Ingreso creates its cost layer and a valued kardex IN row.'''
    item = _make_item(db_session)
    _register_layer(db_session, item, quantity = 10, unit_cost = 2)

    layers = db_session.query(EntryDetail).filter(EntryDetail.item_id == item.id).all()
    assert len(layers) == 1
    assert layers[0].qty_remaining == Decimal('10')
    assert layers[0].unit_cost == Decimal('2')

    ins = _kardex(db_session, item, MovementTypeEnum.IN)
    assert len(ins) == 1
    assert ins[0].unit_cost == Decimal('2')
    assert ins[0].total_cost == Decimal('20')
    assert ins[0].source_entry_id is not None
    assert item.current_stock == Decimal('10')


def test_fifo_consumes_oldest_first_across_layers(db_session):
    '''A delivery spanning two layers drains the oldest one first (PEPS).'''
    item = _make_item(db_session)
    _register_layer(db_session, item, quantity = 10, unit_cost = 2)     # layer 1 (older)
    _register_layer(db_session, item, quantity = 10, unit_cost = Decimal('2.5'))  # layer 2

    layers = (
        db_session.query(EntryDetail)
        .filter(EntryDetail.item_id == item.id)
        .order_by(EntryDetail.id.asc())
        .all()
    )

    movements = consume_stock_fifo(
        db_session, item, Decimal('15'),
        OutflowSpec(created_by = 'admin', reference = MovementReference(
            kind = ReferenceTypeEnum.REQUEST, identifier = 999)),
    )
    db_session.commit()

    # A 15-unit delivery drains the 10-unit older layer then takes 5 from the
    # next, producing two valued OUT rows.
    assert len(movements) == 2
    assert movements[0].quantity == Decimal('10')
    assert movements[0].unit_cost == Decimal('2')
    assert movements[0].source_entry_id == layers[0].entry_id
    assert movements[0].source_entry_detail_id == layers[0].id
    assert movements[1].quantity == Decimal('5')
    assert movements[1].unit_cost == Decimal('2.5')
    assert movements[1].source_entry_id == layers[1].entry_id

    # Balances chain correctly and layers are decremented.
    assert movements[0].balance_before == Decimal('20')
    assert movements[0].balance_after == Decimal('10')
    assert movements[1].balance_after == Decimal('5')
    db_session.refresh(layers[0])
    db_session.refresh(layers[1])
    assert layers[0].qty_remaining == Decimal('0')
    assert layers[1].qty_remaining == Decimal('5')
    assert item.current_stock == Decimal('5')


def test_fifo_within_single_layer_yields_one_row(db_session):
    '''A delivery covered by one layer produces a single valued OUT row.'''
    item = _make_item(db_session)
    _register_layer(db_session, item, quantity = 10, unit_cost = 3)

    movements = consume_stock_fifo(
        db_session, item, Decimal('4'),
        OutflowSpec(created_by = 'admin', reference = MovementReference(
            kind = ReferenceTypeEnum.REQUEST, identifier = 1)),
    )
    db_session.commit()

    assert len(movements) == 1
    assert movements[0].quantity == Decimal('4')
    assert movements[0].unit_cost == Decimal('3')
    assert item.current_stock == Decimal('6')


def test_fifo_insufficient_layers_raises(db_session):
    '''Consuming more than the layers hold is rejected, not silently partial.'''
    item = _make_item(db_session)
    _register_layer(db_session, item, quantity = 5, unit_cost = 1)

    with pytest.raises(InvalidInputError):
        consume_stock_fifo(
            db_session, item, Decimal('10'),
            OutflowSpec(created_by = 'admin', reference = MovementReference(
                kind = ReferenceTypeEnum.REQUEST, identifier = 1)),
        )
