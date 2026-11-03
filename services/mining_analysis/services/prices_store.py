'''
    Quotations store: the single door the business logic uses to reach the
    minerals and their prices.

    Why this layer exists. DynamoDB has no AVG, no COUNT(DISTINCT) and no JOIN,
    so a CRUD that only exposed get/query would push those operations back into
    the services. The functions here are phrased as questions the business asks
    — "the average of this mineral between these two dates" — and answer them
    by reading the partition and aggregating in Python.

    The relational backend was removed on 02-11-2026: the fortnightly load runs
    from `tools/etl_minerals/`, which owns its own MySQL, and the service only
    reads DynamoDB.
'''
from dataclasses import dataclass
from datetime import date as date_type

from boto3.resources.base import ServiceResource

from services import prices_dyb


@dataclass(frozen = True)
class MineralRecord:
    '''
        A mineral of the catalogue.

        Only what the business actually reads from storage: the identifier and
        the name. Unit, chemical symbol and market live in OFFICIAL_MINERALS,
        the published catalogue the bulletins are built from, not in the table.
    '''
    mineral_id: str
    name: str


@dataclass(frozen = True)
class PriceRecord:
    '''One daily quotation.'''
    mineral_id: str
    date: date_type
    price_low: float | None = None
    price_high: float | None = None


def list_minerals(dynamodb_resource: ServiceResource) -> list[MineralRecord]:
    '''
        Returns the mineral catalogue.

        Args:
            dynamodb_resource (ServiceResource): Resource the route resolved.

        Returns:
            list[MineralRecord]: Every mineral on record.
    '''
    return [
        MineralRecord(mineral_id = item.mineral_id, name = item.name)
        for item in prices_dyb.list_minerals(dynamodb_resource)
    ]


def prices_in_window(
    dynamodb_resource: ServiceResource,
    mineral_id: str,
    window: tuple[date_type, date_type]
) -> list[PriceRecord]:
    '''
        Returns the quotations of one mineral inside a date window.

        Args:
            dynamodb_resource (ServiceResource): Resource the route resolved.
            mineral_id (str): Mineral identifier.
            window (tuple[date, date]): First and last date, inclusive.

        Returns:
            list[PriceRecord]: Quotations with a price, ordered by date.
    '''
    start, end = window
    items = prices_dyb.query_prices(dynamodb_resource, mineral_id, {'from': start, 'to': end})
    return [
        PriceRecord(item.mineral_id, item.date, item.price_low, item.price_high)
        for item in items if item.price_low is not None
    ]


def average_low(
    dynamodb_resource: ServiceResource,
    mineral_id: str,
    window: tuple[date_type, date_type]
) -> tuple[float, int] | None:
    '''
        Returns the mean of price_low over the days with data in the window.

        The mean divides by the number of distinct days that actually carry a
        price, matching the published rule "se aplica el promedio para ese
        número de días". DynamoDB cannot average, so the partition is read and
        aggregated here.

        Args:
            dynamodb_resource (ServiceResource): Resource the route resolved.
            mineral_id (str): Mineral identifier.
            window (tuple[date, date]): First and last date, inclusive.

        Returns:
            tuple[float, int] | None: (average, days with data), or None when the
                window holds no data.
    '''
    prices = prices_in_window(dynamodb_resource, mineral_id, window)
    by_day = {price.date: price.price_low for price in prices}
    if not by_day:
        return None
    return sum(by_day.values()) / len(by_day), len(by_day)


def latest_prices_before(
    dynamodb_resource: ServiceResource,
    mineral_id: str,
    ref_date: date_type,
    limit: int = 2
) -> list[PriceRecord]:
    '''
        Returns the most recent quotations of one mineral up to a date.

        The daily report needs the last quotation and the one before it, to
        report the change between them. DynamoDB orders only by the sort key,
        which here is exactly the date, so the query walks the partition
        backwards and stops at the limit.

        Args:
            dynamodb_resource (ServiceResource): Resource the route resolved.
            mineral_id (str): Mineral identifier.
            ref_date (date): Latest date to consider, inclusive.
            limit (int): How many quotations to return, newest first.

        Returns:
            list[PriceRecord]: Quotations newest first, at most `limit` of them.
    '''
    items = prices_dyb.query_prices(dynamodb_resource, mineral_id,
                                    {'to': ref_date}, descending = True)
    return [
        PriceRecord(item.mineral_id, item.date, item.price_low, item.price_high)
        for item in items
    ][:limit]


@dataclass(frozen = True)
class QuotationRecord:
    '''
    One quotation together with the mineral it belongs to.

    The full-catalogue endpoint publishes both, and DynamoDB has no join to
    lean on: the name comes from the catalogue table and the rest of the
    metadata from OFFICIAL_MINERALS, the published catalogue the bulletins are
    built from.
    '''
    mineral_id: str
    mineral_name: str
    date: date_type
    price_low: float | None = None
    price_high: float | None = None


def all_quotations(dynamodb_resource: ServiceResource) -> list[QuotationRecord]:
    '''
        Returns every stored quotation with its mineral.

        Scans the table and resolves the names against the catalogue read
        once. It is the one access pattern the table was not keyed for, which
        is why it belongs to a full export and not to a screen that refreshes.

        Args:
            dynamodb_resource (ServiceResource): Resource the route resolved.

        Returns:
            list[QuotationRecord]: Quotations ordered by date, then mineral.
    '''
    names = {item.mineral_id: item.name for item in prices_dyb.list_minerals(dynamodb_resource)}
    return sorted(
        (
            QuotationRecord(
                item.mineral_id, names.get(item.mineral_id, ''),
                item.date, item.price_low, item.price_high
            )
            for item in prices_dyb.scan_prices(dynamodb_resource)
        ),
        key = lambda record: (record.date, record.mineral_name)
    )
