'''
    Tests for the stock reservation rules.

    A request holds its quantities from the moment it is created so a second
    request cannot promise the same physical units. The hold is released when
    the request is rejected, cancelled or deleted, and it turns into a real
    outflow when the request is delivered.
'''
import asyncio
from decimal import Decimal

import pytest

from controllers.request import (
    cancel_request_controller,
    create_request_controller,
    deliver_request_controller,
    delete_request_controller,
    process_request_controller,
    reject_request_controller,
)
from models.supplies import Item, KardexMovement
from schemas.catalog import ItemResponseSchema
from schemas.enums import MovementTypeEnum, RequestStatusEnum, RoleEnum
from schemas.request import (
    RequestCreateSchema,
    RequestDeliverDetailSchema,
    RequestDeliverSchema,
    RequestDetailCreateSchema,
    RequestTransitionSchema,
)
from services.exceptions import InvalidInputError
from services.supplies_logic import available_stock, recalculate_reserved_stock
from tests.conftest import make_catalog_item, register_entry

ADMIN = RoleEnum.ADMIN.value
REQUESTER = 'solicitante@ministerio.gob.bo'


def _stock_item(session, quantity, min_stock = 0) -> Item:
    '''
        Item with `quantity` units in stock, entered through a Nota de Ingreso
        so the FIFO layers exist and deliveries can consume them.
    '''
    item = make_catalog_item(session, min_stock = min_stock)
    register_entry(session, item, quantity)
    session.refresh(item)
    return item


def _create_request(session, item, quantity, email = REQUESTER):
    '''
        Creates a one-line request for `quantity` units of `item`.
    '''
    payload = RequestCreateSchema(
        requester_name = 'Daniel Rivero Rocha',
        requester_position = 'Tecnico de Sistemas',
        requester_unit = 'Direccion General de Asuntos Administrativos',
        details = [RequestDetailCreateSchema(
            item_id = item.id, requested_qty = Decimal(quantity))],
    )
    return asyncio.run(create_request_controller(session, payload, email))


def test_creating_a_request_reserves_the_quantity(db_session):
    '''The requested units stop being available as soon as the request exists.'''
    item = _stock_item(db_session, 100)

    _create_request(db_session, item, 30)
    db_session.refresh(item)

    assert item.current_stock == Decimal('100')
    assert item.reserved_stock == Decimal('30')
    assert available_stock(item) == Decimal('70')


def test_second_request_cannot_take_reserved_units(db_session):
    '''A second request only sees what the first one left behind.'''
    item = _stock_item(db_session, 100)
    _create_request(db_session, item, 80)

    with pytest.raises(InvalidInputError) as excinfo:
        _create_request(db_session, item, 30, email = 'otro@ministerio.gob.bo')

    assert 'reserved' in str(excinfo.value.detail).lower()


def test_available_stock_also_subtracts_the_minimum(db_session):
    '''The minimum the warehouse keeps is not available to requesters.'''
    item = _stock_item(db_session, 100, min_stock = 25)

    _create_request(db_session, item, 10)
    db_session.refresh(item)

    assert available_stock(item) == Decimal('65')


def test_rejecting_a_request_releases_the_reservation(db_session):
    '''A rejected request gives its units back.'''
    item = _stock_item(db_session, 100)
    created = _create_request(db_session, item, 40)
    asyncio.run(process_request_controller(db_session, created.id, ADMIN, 'almacen'))

    asyncio.run(reject_request_controller(
        db_session, created.id,
        RequestTransitionSchema(reason = 'Sin presupuesto'), ADMIN, 'almacen'))
    db_session.refresh(item)

    assert item.reserved_stock == Decimal('0')
    assert available_stock(item) == Decimal('100')


def test_cancelling_a_request_releases_the_reservation(db_session):
    '''An annulled request gives its units back too.'''
    item = _stock_item(db_session, 100)
    created = _create_request(db_session, item, 40)
    asyncio.run(process_request_controller(db_session, created.id, ADMIN, 'almacen'))

    asyncio.run(cancel_request_controller(
        db_session, created.id,
        RequestTransitionSchema(reason = 'Duplicada'), ADMIN, 'almacen'))
    db_session.refresh(item)

    assert item.reserved_stock == Decimal('0')


def test_deleting_a_created_request_releases_the_reservation(db_session):
    '''Deleting a draft request must not leave its units held forever.'''
    item = _stock_item(db_session, 100)
    created = _create_request(db_session, item, 40)

    asyncio.run(delete_request_controller(db_session, created.id, ADMIN, REQUESTER))
    db_session.refresh(item)

    assert item.reserved_stock == Decimal('0')


def test_delivering_turns_the_reservation_into_an_outflow(db_session):
    '''Delivered units leave stock and stop being reserved.'''
    item = _stock_item(db_session, 100)
    created = _create_request(db_session, item, 40)
    asyncio.run(process_request_controller(db_session, created.id, ADMIN, 'almacen'))

    asyncio.run(deliver_request_controller(
        db_session, created.id, RequestDeliverSchema(), ADMIN, 'almacen'))
    db_session.refresh(item)

    assert item.current_stock == Decimal('60')
    assert item.reserved_stock == Decimal('0')
    assert available_stock(item) == Decimal('60')


def test_delivery_kardex_note_names_the_recipient(db_session):
    '''The valued kardex prints who received the material, as NSIAF did.'''
    item = _stock_item(db_session, 100)
    created = _create_request(db_session, item, 10)
    asyncio.run(process_request_controller(db_session, created.id, ADMIN, 'almacen'))
    asyncio.run(deliver_request_controller(
        db_session, created.id, RequestDeliverSchema(), ADMIN, 'almacen'))

    movement = (
        db_session.query(KardexMovement)
        .filter(KardexMovement.movement_type == MovementTypeEnum.OUT)
        .first()
    )

    assert created.code in movement.notes
    assert 'Daniel Rivero Rocha' in movement.notes
    assert 'Tecnico de Sistemas' in movement.notes


def test_partial_delivery_releases_the_undelivered_remainder(db_session):
    '''What was not handed over goes back to the available pool.'''
    item = _stock_item(db_session, 100)
    created = _create_request(db_session, item, 40)
    asyncio.run(process_request_controller(db_session, created.id, ADMIN, 'almacen'))

    asyncio.run(deliver_request_controller(
        db_session, created.id,
        RequestDeliverSchema(details = [RequestDeliverDetailSchema(
            item_id = item.id, delivered_qty = Decimal('15'))]),
        ADMIN, 'almacen'))
    db_session.refresh(item)

    assert item.current_stock == Decimal('85')
    assert item.reserved_stock == Decimal('0')


def test_two_requests_can_share_the_stock_they_fit_in(db_session):
    '''Reservations are additive; both requests can still be delivered.'''
    item = _stock_item(db_session, 100)
    first = _create_request(db_session, item, 60)
    second = _create_request(db_session, item, 40, email = 'otro@ministerio.gob.bo')
    db_session.refresh(item)
    assert item.reserved_stock == Decimal('100')
    assert available_stock(item) == Decimal('0')

    for request in (first, second):
        asyncio.run(process_request_controller(db_session, request.id, ADMIN, 'almacen'))
        asyncio.run(deliver_request_controller(
            db_session, request.id, RequestDeliverSchema(), ADMIN, 'almacen'))
    db_session.refresh(item)

    assert item.current_stock == Decimal('0')
    assert item.reserved_stock == Decimal('0')


def test_recalculate_rebuilds_a_stale_reservation(db_session):
    '''The maintenance helper restores the value from the open requests.'''
    item = _stock_item(db_session, 100)
    _create_request(db_session, item, 25)

    item.reserved_stock = Decimal('999')
    db_session.commit()

    changed = recalculate_reserved_stock(db_session)
    db_session.commit()
    db_session.refresh(item)

    assert changed == 1
    assert item.reserved_stock == Decimal('25')


def test_item_response_exposes_available_stock(db_session):
    '''The API answer carries availability so the UI never recomputes it.'''
    item = _stock_item(db_session, 100, min_stock = 10)
    _create_request(db_session, item, 20)
    db_session.refresh(item)

    payload = ItemResponseSchema.model_validate(item)

    assert payload.reserved_stock == Decimal('20')
    assert payload.available_stock == Decimal('70')


def test_request_starts_in_created_with_identity_fields(db_session):
    '''The identity printed on the paper forms travels with the request.'''
    item = _stock_item(db_session, 50)

    created = _create_request(db_session, item, 5)

    assert created.status == RequestStatusEnum.CREATED
    assert created.requester_name == 'Daniel Rivero Rocha'
    assert created.requester_position == 'Tecnico de Sistemas'
    assert created.details[0].item_code == 'IT-1'
    assert created.details[0].unit == 'pza'
