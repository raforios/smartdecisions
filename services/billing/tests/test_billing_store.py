'''
    BILLING's data access on PostgreSQL: the records the services know turn
    into rows and back unchanged, the owner bounds every read, counters and
    lots cannot be taken twice, and no field is ever dropped in silence.
'''
import pytest

from core.db_connection import ENGINE, GET_DB_DEPENDENCY, Base
from models.billing import CUSTOMERS_TABLE, LOTS_TABLE, SALES_TABLE, SETTINGS_TABLE
from models.billing_tables import TABLES
from services import billing_store as store

SHOP, OTHER = 'shop@farmacia.bo', 'other@farmacia.bo'


@pytest.fixture(name = 'db')
def fixture_db():
    '''A session on empty tables; dropped after the test.'''
    Base.metadata.create_all(ENGINE, tables = TABLES)
    source = GET_DB_DEPENDENCY()
    session = next(source, None)
    yield session
    session.rollback()
    source.close()
    Base.metadata.drop_all(ENGINE, tables = TABLES)


def _lot(lot_id: str, remaining: float = 10) -> dict:
    '''A lot record as the stock service writes it.'''
    return {'owner': SHOP, 'lot_key': f'PARA500#{lot_id}', 'sku': 'PARA500',
            'lot_id': lot_id, 'unit_cost': 3.5, 'sale_price': 6.0,
            'quantity_received': 10, 'quantity_remaining': remaining,
            'received_at': '2026-11-10T09:00:00-04:00', 'expiry_date': '2027-05-31'}


def test_a_record_comes_back_as_it_went_in(db):
    '''Times as ISO strings, money as numbers, the joined lot key rebuilt.'''
    store.write_item(db, LOTS_TABLE, _lot('L1'))
    lot = store.get_item(db, LOTS_TABLE, SHOP, 'PARA500#L1')
    assert lot['lot_key'] == 'PARA500#L1'
    assert (lot['sale_price'], lot['quantity_remaining']) == (6.0, 10)
    assert lot['received_at'].startswith('2026-11-10T09:00:00')
    assert lot['expiry_date'] == '2027-05-31'


def test_another_shop_reads_nothing(db):
    '''The owner is part of every query.'''
    store.write_item(db, LOTS_TABLE, _lot('L1'))
    assert store.get_item(db, LOTS_TABLE, OTHER, 'PARA500#L1') is None
    assert not store.read_partition(db, LOTS_TABLE, OTHER)


def test_a_field_the_table_lacks_is_rejected(db):
    '''Nothing is dropped in silence.'''
    with pytest.raises(ValueError, match = 'unexpected_field'):
        store.write_item(db, LOTS_TABLE, {**_lot('L1'), 'unexpected_field': 1})


def test_writing_again_replaces_the_record(db):
    '''As a put did: the record stored is the one written last.'''
    store.write_item(db, LOTS_TABLE, _lot('L1'))
    store.write_item(db, LOTS_TABLE, {**_lot('L1'), 'sale_price': 7.5})
    assert store.get_item(db, LOTS_TABLE, SHOP, 'PARA500#L1')['sale_price'] == 7.5
    assert len(store.read_partition(db, LOTS_TABLE, SHOP)) == 1


def test_a_setting_keeps_every_field_it_carries(db):
    '''Settings are documents: whatever they hold comes back.'''
    store.write_item(db, SETTINGS_TABLE, {'owner': SHOP, 'setting_key': 'config',
                                          'trade_name': 'The Pharma', 'nit': '4746720010'})
    config = store.get_item(db, SETTINGS_TABLE, SHOP, 'config')
    assert (config['trade_name'], config['nit']) == ('The Pharma', '4746720010')
    store.delete_item(db, SETTINGS_TABLE, SHOP, 'config')
    assert store.get_item(db, SETTINGS_TABLE, SHOP, 'config') is None


def test_reads_narrow_by_prefix_and_by_range(db):
    '''A SKU's lots by prefix; a day's sales by the time their id starts with.'''
    store.write_item(db, LOTS_TABLE, _lot('L1'))
    store.write_item(db, LOTS_TABLE, {**_lot('L2'), 'lot_key': 'IBU400#L2', 'sku': 'IBU400'})
    lots = store.read_partition(db, LOTS_TABLE, SHOP, store.SortBounds('lot_key', 'PARA500#'))
    assert [lot['lot_id'] for lot in lots] == ['L1']
    for stamp in ('2026-11-09T10:00:00', '2026-11-10T10:00:00', '2026-11-11T10:00:00'):
        store.write_item(db, SALES_TABLE, {
            'owner': SHOP, 'sale_id': f'{stamp}#x', 'number': 'A-1', 'status': 'ISSUED',
            'payment_method': 'CASH', 'lines': [], 'subtotal': 1, 'discount': 0, 'total': 1,
            'cost': 0.5, 'created_by': 'cajero', 'created_at': f'{stamp}-04:00'})
    window = store.SortBounds('sale_id', between = {'from': '2026-11-10',
                                                   'to': '2026-11-10T23:59:59￿'})
    sales = store.read_partition(db, SALES_TABLE, SHOP, window)
    assert [sale['sale_id'][:10] for sale in sales] == ['2026-11-10']
    newest = store.read_partition(db, SALES_TABLE, SHOP, descending = True)
    assert newest[0]['sale_id'].startswith('2026-11-11')


def test_a_counter_hands_out_each_number_once(db):
    '''1, 2, 3 for one shop; another shop starts at 1.'''
    assert [store.take_counter(db, SHOP, 'counter#sale') for _ in range(3)] == [1, 2, 3]
    assert store.take_counter(db, OTHER, 'counter#sale') == 1


def test_a_lot_never_gives_units_it_does_not_hold(db):
    '''Taking more than remains fails and leaves the lot as it was.'''
    store.write_item(db, LOTS_TABLE, _lot('L1', remaining = 3))
    assert store.add_to_lot(db, SHOP, 'PARA500#L1', -2)
    assert not store.add_to_lot(db, SHOP, 'PARA500#L1', -2)
    assert store.add_to_lot(db, SHOP, 'PARA500#L1', 5)
    db.expire_all()
    assert store.get_item(db, LOTS_TABLE, SHOP, 'PARA500#L1')['quantity_remaining'] == 6


def test_ensure_creates_once_and_keeps_what_exists(db):
    '''A second creation does not overwrite the first.'''
    store.ensure_item(db, CUSTOMERS_TABLE, {'owner': SHOP, 'document': '123', 'name': 'Ana'})
    store.ensure_item(db, CUSTOMERS_TABLE, {'owner': SHOP, 'document': '123', 'name': 'Otra'})
    assert store.get_item(db, CUSTOMERS_TABLE, SHOP, '123')['name'] == 'Ana'
