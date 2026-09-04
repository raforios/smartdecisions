'''
    Tests for the quotations store, the layer that lets the service run on a
    relational database or on DynamoDB.

    The point of these tests is equivalence: the same quotations must produce
    the same average whichever backend answers. A discrepancy here would mean
    the published bulletin changes depending on where the data is stored, which
    is the failure mode this layer exists to prevent.
'''
from datetime import date
from unittest.mock import patch

import pytest

from models.mining_analysis_dyb import MineralItem, MiningPriceItem
from services import crud_dyb, prices_store


# The Bismuto case from the September bulletin: four days averaging 12.825.
QUOTES = [
    (date(2026, 8, 17), 12.80),
    (date(2026, 8, 20), 12.85),
    (date(2026, 8, 24), 12.83),
    (date(2026, 8, 27), 12.82),
]
EXPECTED_AVERAGE = sum(price for _, price in QUOTES) / len(QUOTES)


@pytest.fixture(name = 'dynamo_backend')
def _dynamo_backend():
    '''
        Runs the store on DynamoDB with the quotations above in place of boto3.

        Returns:
            None: The patches are active for the duration of the test.
    '''
    items = [
        MiningPriceItem(mineral_id = '7', date = day, price_low = price)
        for day, price in QUOTES
    ]

    def _query(mineral_id, start = None, end = None, descending = False):
        found = [
            item for item in items
            if item.mineral_id == mineral_id
            and (start is None or item.date >= start)
            and (end is None or item.date <= end)
        ]
        return sorted(found, key = lambda item: item.date, reverse = descending)

    with patch.object(prices_store, 'uses_dynamodb', lambda: True), \
         patch('services.crud_dyb.query_prices', _query):
        yield


def test_dynamodb_average_matches_the_documented_rule(dynamo_backend): # pylint: disable=unused-argument
    '''
        DynamoDB cannot average, so the store does it: the mean must divide by
        the number of distinct days with a price, not by the days in the window.
    '''
    average, days = prices_store.average_low('7', date(2026, 8, 16), date(2026, 8, 31))

    assert days == len(QUOTES)
    assert average == pytest.approx(EXPECTED_AVERAGE)


def test_dynamodb_window_excludes_dates_outside_the_period(dynamo_backend): # pylint: disable=unused-argument
    '''A window covering only part of the month averages only those days.'''
    average, days = prices_store.average_low('7', date(2026, 8, 17), date(2026, 8, 20))

    assert days == 2
    assert average == pytest.approx((12.80 + 12.85) / 2)


def test_dynamodb_empty_window_returns_none(dynamo_backend): # pylint: disable=unused-argument
    '''A period with no quotations reports nothing, never a zero.'''
    assert prices_store.average_low('7', date(2026, 7, 1), date(2026, 7, 15)) is None


def test_sql_backend_is_the_default():
    '''
        Without PERSISTENCE_BACKEND the service keeps using the relational
        models, so an existing deployment does not change behaviour.
    '''
    assert prices_store.BACKEND == prices_store.SQL_BACKEND
    assert prices_store.uses_dynamodb() is False


def test_both_backends_agree_on_the_same_quotations(db_session, dynamo_backend): # pylint: disable=unused-argument
    '''
        The equivalence that matters: relational and DynamoDB must return the
        same average for the same data.
    '''
    dynamo_average, dynamo_days = prices_store.average_low(
        '7', date(2026, 8, 16), date(2026, 8, 31)
    )

    with patch.object(prices_store, 'uses_dynamodb', lambda: False):
        _seed_relational(db_session)
        sql_result = prices_store.average_low(
            '7', date(2026, 8, 16), date(2026, 8, 31), db = db_session
        )

    assert sql_result is not None
    sql_average, sql_days = sql_result
    assert sql_days == dynamo_days
    assert sql_average == pytest.approx(dynamo_average)


def _seed_relational(db_session) -> None:
    '''
        Writes the same quotations into the relational test database.

        Args:
            db_session: Session provided by the test fixtures.
    '''
    from models.mining_analysis import Mineral, MiningPrice # pylint: disable=import-outside-toplevel

    mineral = db_session.get(Mineral, 7)
    if mineral is None:
        db_session.add(Mineral(id = 7, name = 'Bismuto', unit = 'LF'))
    for day, price in QUOTES:
        db_session.add(MiningPrice(mineral_id = 7, date = day, price_low = price))
    db_session.commit()


def test_batch_write_sends_every_quotation_once():
    '''
        The batch writer must hand DynamoDB each quotation exactly once.

        The migration leans on this: if the writer dropped or duplicated rows,
        the copy would still report success while the deployed service answered
        over an incomplete history.
    '''
    written = []

    class _Batch:
        '''Captures what the batch writer receives.'''

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def put_item(self, Item): # pylint: disable=invalid-name
            '''Records one item, mirroring the boto3 keyword.'''
            written.append(Item)

    class _Table:
        '''Stands in for the DynamoDB table resource.'''

        def batch_writer(self):
            '''Returns the capturing batch.'''
            return _Batch()

    prices = [
        MiningPriceItem(mineral_id = '1', date = date(2026, 4, 1),
                        price_low = 30.0, price_high = 31.0),
        MiningPriceItem(mineral_id = '1', date = date(2026, 4, 2),
                        price_low = 32.5, price_high = 33.5),
    ]

    with patch('services.crud_dyb._table', lambda name: _Table()):
        count = crud_dyb.put_prices_batch(prices)

    assert count == 2
    assert [item['mineral_id'] for item in written] == ['1', '1']
    assert [item['date'] for item in written] == ['2026-04-01', '2026-04-02']
    # DynamoDB rejects floats: the writer must hand over Decimal.
    assert all(not isinstance(item['price_low'], float) for item in written)


def test_batch_write_of_nothing_writes_nothing():
    '''An empty migration must not reach DynamoDB at all.'''
    with patch('services.crud_dyb._table') as table:
        assert crud_dyb.put_prices_batch([]) == 0

    table.assert_not_called()


def test_latest_prices_before_returns_newest_first(dynamo_backend): # pylint: disable=unused-argument
    '''
        The daily report needs the last quotation and the one before it.

        Order is the whole point: reversing it would report the change with the
        wrong sign, which is a number a reader would believe.
    '''
    found = prices_store.latest_prices_before('7', date(2026, 8, 27), 2)

    assert [record.date for record in found] == [date(2026, 8, 27), date(2026, 8, 24)]
    assert found[0].price_low == 12.82


def test_latest_prices_before_ignores_dates_after_the_reference(dynamo_backend): # pylint: disable=unused-argument
    '''
        Asking for an older date must answer with what was known back then, not
        with the latest quotation on file.
    '''
    found = prices_store.latest_prices_before('7', date(2026, 8, 20), 2)

    assert [record.date for record in found] == [date(2026, 8, 20), date(2026, 8, 17)]


def test_latest_prices_before_of_an_unknown_mineral_is_empty(dynamo_backend): # pylint: disable=unused-argument
    '''A mineral with no quotations yields nothing, not an error.'''
    assert prices_store.latest_prices_before('999', date(2026, 8, 27), 2) == []


def test_date_bounds_spans_the_stored_history():
    '''
        The history screen asks storage how far back it can go.

        DynamoDB has no MIN/MAX, so the reduction happens in Python; the test
        pins that it reduces over everything and not over one partition.
    '''
    items = [
        MiningPriceItem(mineral_id = '7', date = day, price_low = price)
        for day, price in QUOTES
    ] + [
        MiningPriceItem(mineral_id = '1', date = date(2026, 4, 1), price_low = 22.0)
    ]

    with patch.object(prices_store, 'uses_dynamodb', lambda: True), \
         patch('services.crud_dyb.scan_prices', lambda: items):
        assert prices_store.date_bounds() == (date(2026, 4, 1), date(2026, 8, 27))


def test_date_bounds_of_an_empty_table_is_undefined():
    '''With nothing stored there is no range to report, and None says so.'''
    with patch.object(prices_store, 'uses_dynamodb', lambda: True), \
         patch('services.crud_dyb.scan_prices', list):
        assert prices_store.date_bounds() == (None, None)


def test_all_quotations_carries_the_mineral_name(dynamo_backend): # pylint: disable=unused-argument
    '''
        The full export publishes the quotation with its mineral.

        On DynamoDB there is no join: the name is resolved against the catalogue
        read, and a quotation whose mineral is missing must still travel rather
        than disappear from an export.
    '''
    catalogue = [
        MineralItem(mineral_id = '7', name = 'Bismuto', unit = 'LF'),
    ]

    with patch('services.crud_dyb.list_minerals', lambda: catalogue), \
         patch('services.crud_dyb.scan_prices', lambda: [
             MiningPriceItem(mineral_id = '7', date = date(2026, 8, 27), price_low = 12.82),
             MiningPriceItem(mineral_id = '99', date = date(2026, 8, 27), price_low = 1.0),
         ]):
        records = prices_store.all_quotations()

    assert len(records) == 2
    named = {record.mineral_id: record.mineral_name for record in records}
    assert named['7'] == 'Bismuto'
    assert named['99'] == ''


def test_all_quotations_comes_back_in_date_order(dynamo_backend): # pylint: disable=unused-argument
    '''
        The export is read as a series, so the order is part of the contract:
        the Streamlit report sorts by date and takes the last row per mineral.
    '''
    with patch('services.crud_dyb.list_minerals', lambda: []), \
         patch('services.crud_dyb.scan_prices', lambda: [
             MiningPriceItem(mineral_id = '1', date = date(2026, 8, 27), price_low = 3.0),
             MiningPriceItem(mineral_id = '1', date = date(2026, 8, 17), price_low = 1.0),
             MiningPriceItem(mineral_id = '1', date = date(2026, 8, 20), price_low = 2.0),
         ]):
        records = prices_store.all_quotations()

    assert [record.date for record in records] == [
        date(2026, 8, 17), date(2026, 8, 20), date(2026, 8, 27)
    ]
