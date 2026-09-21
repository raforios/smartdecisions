'''
    Tests for the daily stock: the opening load, its replacement, and the
    all-or-nothing draw-down that a sale on a visit triggers.
'''
import pytest
from moto import mock_aws

from schemas.daily_stock import (
    DailyStockLoadSchema,
    SaleItemSchema,
    StockError,
    StockItemLoadSchema
)
from schemas.localization import ExecutedPointCreateSchema, ExecutedRouteCreateSchema
from services import daily_stock, localization, localization_executed as executed
from services.exceptions import InvalidInputError
from services.utils import get_current_time_gmt
from tests.dynamo_helpers import build_resource

OWNER = 'yo@miempresa.com'
OTHER = 'otra@empresa.com'


def _today() -> str:
    '''
        Today, YYYY-MM-DD, service timezone.
    '''
    return get_current_time_gmt().date().isoformat()


def _load(
    day: str,
    **quantities
) -> DailyStockLoadSchema:
    '''
        A load of `day` with one item per keyword: sku = units.
    '''
    return DailyStockLoadSchema(date = day, items = [
        StockItemLoadSchema(sku = sku, quantity = units, product_name = f'Producto {sku}')
        for sku, units in quantities.items()
    ])


@pytest.fixture(name = 'dynamodb')
def dynamodb_fixture():
    '''The stock table plus both tracking tables (a sale travels on a visit).'''
    with mock_aws():
        yield build_resource([
            (daily_stock.DAILY_STOCK_TABLE, 'owner_email', 'stock_key'),
            (localization.PLANNED_ROUTES_TABLE, 'owner_email', 'id'),
            (executed.EXECUTED_ROUTES_TABLE, 'owner_email', 'id')
        ])


def test_load_daily_stock_stores_rows_and_refuses_repeated_skus(dynamodb):
    '''One row per SKU with nothing sold yet; a repeated SKU refuses the load.'''
    day = _today()
    rows = daily_stock.load_daily_stock(dynamodb, OWNER, _load(day, A = 10, B = 3))
    assert [(row['sku'], row['opening_quantity'], row['sold_quantity']) for row in rows] == [
        ('A', 10, 0), ('B', 3, 0)
    ]
    stored = daily_stock.get_daily_stock(dynamodb, OWNER, day)
    assert {row['sku'] for row in stored} == {'A', 'B'}
    assert daily_stock.get_daily_stock(dynamodb, OTHER, day) == []

    twice = DailyStockLoadSchema(date = day, items = [
        StockItemLoadSchema(sku = 'A', quantity = 1), StockItemLoadSchema(sku = 'A', quantity = 2)
    ])
    with pytest.raises(InvalidInputError) as failure:
        daily_stock.load_daily_stock(dynamodb, OWNER, twice)
    assert failure.value.detail == StockError.DUPLICATE_SKU.value


def test_load_daily_stock_again_replaces_the_day_but_keeps_sales(dynamodb):
    '''A dropped SKU disappears, a new one appears, sales of kept SKUs survive.'''
    day = _today()
    daily_stock.load_daily_stock(dynamodb, OWNER, _load(day, A = 10, B = 3))
    daily_stock.draw_down_stock(dynamodb, OWNER, day, [SaleItemSchema(sku = 'A', quantity = 4)])

    daily_stock.load_daily_stock(dynamodb, OWNER, _load(day, A = 12, C = 5))
    by_sku = {row['sku']: row for row in daily_stock.get_daily_stock(dynamodb, OWNER, day)}
    assert set(by_sku) == {'A', 'C'}
    assert (by_sku['A']['opening_quantity'], by_sku['A']['sold_quantity']) == (12, 4)
    assert by_sku['C']['sold_quantity'] == 0


def test_draw_down_stock_is_all_or_nothing(dynamodb):
    '''
        A sale that fits lowers every SKU; one that exceeds any SKU changes
        nothing; a SKU never loaded is named as such; repeated lines add up.
    '''
    day = _today()
    daily_stock.load_daily_stock(dynamodb, OWNER, _load(day, A = 10, B = 3))

    daily_stock.draw_down_stock(dynamodb, OWNER, day, [
        SaleItemSchema(sku = 'A', quantity = 2), SaleItemSchema(sku = 'A', quantity = 3),
        SaleItemSchema(sku = 'B', quantity = 1)
    ])
    by_sku = {row['sku']: row['sold_quantity']
              for row in daily_stock.get_daily_stock(dynamodb, OWNER, day)}
    assert by_sku == {'A': 5, 'B': 1}

    with pytest.raises(InvalidInputError) as failure:
        daily_stock.draw_down_stock(dynamodb, OWNER, day, [
            SaleItemSchema(sku = 'A', quantity = 1), SaleItemSchema(sku = 'B', quantity = 3)
        ])
    assert failure.value.detail == StockError.INSUFFICIENT_STOCK.value
    by_sku = {row['sku']: row['sold_quantity']
              for row in daily_stock.get_daily_stock(dynamodb, OWNER, day)}
    assert by_sku == {'A': 5, 'B': 1}

    with pytest.raises(InvalidInputError) as failure:
        daily_stock.draw_down_stock(dynamodb, OWNER, day, [SaleItemSchema(sku = 'Z', quantity = 1)])
    assert failure.value.detail == StockError.STOCK_NOT_LOADED.value

    daily_stock.draw_down_stock(dynamodb, OWNER, day, [])


def test_draw_down_stock_is_scoped_to_the_owner(dynamodb):
    '''My stock is not somebody else's stock, even for the same SKU and day.'''
    day = _today()
    daily_stock.load_daily_stock(dynamodb, OWNER, _load(day, A = 10))
    with pytest.raises(InvalidInputError) as failure:
        daily_stock.draw_down_stock(dynamodb, OTHER, day, [SaleItemSchema(sku = 'A', quantity = 1)])
    assert failure.value.detail == StockError.STOCK_NOT_LOADED.value


def test_to_daily_stock_response_counts_what_ran_out(dynamodb):
    '''Available is opening minus sold; the out-of-stock count sees the zeros.'''
    day = _today()
    daily_stock.load_daily_stock(dynamodb, OWNER, _load(day, A = 2, B = 5))
    daily_stock.draw_down_stock(dynamodb, OWNER, day, [SaleItemSchema(sku = 'A', quantity = 2)])
    response = daily_stock.to_daily_stock_response(
        day, daily_stock.get_daily_stock(dynamodb, OWNER, day)
    )
    assert response.skus_loaded == 2 and response.skus_out_of_stock == 1
    assert [(row.sku, row.available_quantity) for row in response.items] == [('A', 0), ('B', 5)]


def test_a_sale_on_a_visit_draws_from_the_stock_or_is_not_recorded(dynamodb):
    '''The visit with lines lowers the stock; without units the visit is refused.'''
    day = _today()
    stamp = get_current_time_gmt().replace(hour = 10, minute = 0, second = 0, microsecond = 0)
    daily_stock.load_daily_stock(dynamodb, OWNER, _load(day, A = 3))
    route = executed.create_executed_route(dynamodb, OWNER, ExecutedRouteCreateSchema(
        seller = 'Ana', start_time = stamp.replace(hour = 8).isoformat(),
        start_latitude = -16.5, start_longitude = -68.1, max_distance_start_point = 100
    ))

    route, point = executed.register_executed_point(dynamodb, OWNER, ExecutedPointCreateSchema(
        executed_route_id = route['id'], timestamp = stamp.isoformat(),
        latitude = -16.5, longitude = -68.1, client_id = 'PDV-1', outcome = 'VENTA',
        items = [SaleItemSchema(sku = 'A', quantity = 2)]
    ))
    assert point['items'] == [{'sku': 'A', 'quantity': 2.0}]
    assert daily_stock.get_daily_stock(dynamodb, OWNER, day)[0]['sold_quantity'] == 2

    with pytest.raises(InvalidInputError) as failure:
        executed.register_executed_point(dynamodb, OWNER, ExecutedPointCreateSchema(
            executed_route_id = route['id'], timestamp = stamp.replace(hour = 11).isoformat(),
            latitude = -16.5, longitude = -68.1, client_id = 'PDV-2', outcome = 'VENTA',
            items = [SaleItemSchema(sku = 'A', quantity = 2)]
        ))
    assert failure.value.detail == StockError.INSUFFICIENT_STOCK.value
    assert len(executed.get_executed_route(dynamodb, OWNER, route['id'])['points']) == 1
