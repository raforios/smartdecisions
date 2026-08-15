'''
    Tests for the valued warehouse report aggregations.

    Scenario: one item receives two PEPS layers (10 @ 2.0, then 10 @ 2.5) and
    then delivers 15 units, which FIFO drains the first layer (10) and takes 5
    from the second. Expected closing stock: 5 units valued at 12.50.
'''
import asyncio
from datetime import datetime
from decimal import Decimal

from controllers.entry import create_entry_controller
from controllers.reports import (
    in_out_by_group_report_controller,
    kardex_valued_report_controller,
    outflow_report_controller,
    physical_valued_report_controller,
    stock_on_hand_report_controller,
)
from models.supplies import Category, Item, Request, Unit
from schemas.entry import EntryCreateSchema, EntryDetailCreateSchema
from schemas.enums import EntryTypeEnum, ReferenceTypeEnum, RequestStatusEnum
from services.supplies_logic import MovementReference, OutflowSpec, consume_stock_fifo


def _build_scenario(session):
    category = Category(code = '32100', name = 'PAPEL', is_active = True)
    unit = Unit(code = 'PZA', name = 'PIEZA', abbreviation = 'pza', is_active = True)
    session.add_all([category, unit])
    session.flush()
    item = Item(
        code = '30001', name = 'Artículo de prueba',
        category_id = category.id, unit_id = unit.id,
        min_stock = 0, current_stock = 0, default_replenishment_qty = 0, is_active = True,
    )
    session.add(item)
    session.commit()

    for cost in (Decimal('2'), Decimal('2.5')):
        payload = EntryCreateSchema(
            entry_type = EntryTypeEnum.COMPRA,
            details = [EntryDetailCreateSchema(item_id = item.id, quantity = 10, unit_cost = cost)],
        )
        asyncio.run(create_entry_controller(session, payload, created_by = 'admin'))

    request = Request(code = 'SOL-1', requester_email = 'user@x.com',
                      status = RequestStatusEnum.CREATED)
    session.add(request)
    session.commit()

    consume_stock_fifo(
        session, item, Decimal('15'),
        OutflowSpec(created_by = 'almacen', reference = MovementReference(
            kind = ReferenceTypeEnum.REQUEST, identifier = request.id)),
    )
    session.commit()
    return item


def test_physical_valued_report(db_session):
    '''Inicio/ingreso/egreso/final add up, physically and valued.'''
    _build_scenario(db_session)
    report = asyncio.run(physical_valued_report_controller(db_session))

    assert len(report.groups) == 1
    group = report.groups[0]
    assert group.group_code == '32100'
    row = group.items[0]
    assert row.fisico_ingreso == Decimal('20')
    assert row.fisico_egreso == Decimal('15')
    assert row.fisico_final == Decimal('5')
    assert row.valorado_ingreso == Decimal('45')      # 10*2 + 10*2.5
    assert row.valorado_egreso == Decimal('32.5')     # 10*2 + 5*2.5
    assert row.valorado_final == Decimal('12.5')
    assert row.precio_unitario == Decimal('2.5')
    assert report.grand_total_valorado == Decimal('12.5')


def test_stock_on_hand_report(db_session):
    '''The remaining stock is valued at its own layer cost, not an average.'''
    _build_scenario(db_session)
    report = asyncio.run(stock_on_hand_report_controller(db_session))

    row = report.groups[0].items[0]
    assert row.saldo_existente == Decimal('5')
    assert row.total_valorado == Decimal('12.5')      # remaining 5 @ 2.5
    assert row.precio_unitario == Decimal('2.5')
    assert report.grand_total_valorado == Decimal('12.5')


def test_in_out_by_group_report(db_session):
    '''Valued ins minus outs give the balance of the accounting group.'''
    _build_scenario(db_session)
    report = asyncio.run(in_out_by_group_report_controller(db_session))

    row = report.rows[0]
    assert row.ingresos == Decimal('45')
    assert row.salidas == Decimal('32.5')
    assert row.saldo == Decimal('12.5')
    assert report.total_saldo == Decimal('12.5')


def test_kardex_valued_report(db_session):
    '''The ledger shows one line per layer touched, with running balances.'''
    _build_scenario(db_session)
    report = asyncio.run(kardex_valued_report_controller(db_session))

    item = report.items[0]
    # 2 IN layers + 2 OUT rows (delivery split across layers).
    assert len(item.lines) == 4
    assert item.saldo_inicial_qty == Decimal('0')
    assert item.saldo_final_qty == Decimal('5')
    assert item.saldo_final_val == Decimal('12.5')


def test_outflow_report(db_session):
    '''Each outflow line names the recipient and its source request.'''
    _build_scenario(db_session)
    report = asyncio.run(outflow_report_controller(db_session))

    item = report.items[0]
    assert item.total_salida == Decimal('15')
    assert len(item.lines) == 2                        # one per consumed layer
    assert all(line.recipient == 'user@x.com' for line in item.lines)
    assert all(line.request_code == 'SOL-1' for line in item.lines)
    assert report.grand_total_salida == Decimal('15')


def test_stock_on_hand_hides_zero_balance_by_default(db_session):
    '''An item drained to zero disappears from "stock existente" unless asked for.'''
    item = _build_scenario(db_session)
    consume_stock_fifo(
        db_session, item, Decimal('5'),
        OutflowSpec(created_by = 'almacen', reference = MovementReference(
            kind = ReferenceTypeEnum.REQUEST)),
    )
    db_session.commit()

    default_report = asyncio.run(stock_on_hand_report_controller(db_session))
    assert default_report.groups == []

    with_zero = asyncio.run(stock_on_hand_report_controller(db_session, include_zero = True))
    assert with_zero.groups[0].items[0].saldo_existente == Decimal('0')


def test_stock_on_hand_cut_off_date_excludes_later_movements(db_session):
    '''A cut-off before any movement reports an empty warehouse, not today's stock.'''
    _build_scenario(db_session)
    report = asyncio.run(
        stock_on_hand_report_controller(db_session, date_to = datetime(2000, 1, 1))
    )
    assert report.groups == []
    assert report.grand_total_valorado == Decimal('0')


def test_kardex_valued_filters_by_accounting_group(db_session):
    '''The group filter narrows the kardex the same way the item filter does.'''
    _build_scenario(db_session)

    matching = asyncio.run(kardex_valued_report_controller(db_session, group_code = '32100'))
    assert len(matching.items) == 1

    other = asyncio.run(kardex_valued_report_controller(db_session, group_code = '99999'))
    assert other.items == []
