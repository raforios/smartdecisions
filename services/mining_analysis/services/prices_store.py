'''
    Quotations store: the single door the business logic uses to reach the
    minerals and their prices, whichever database is configured.

    Why this layer exists. DynamoDB has no AVG, no COUNT(DISTINCT) and no JOIN,
    so a CRUD that only exposed get/query would push those operations back into
    the services, leaving one version of the same business rule per engine. The
    functions here are phrased as questions the business asks — "the average of
    this mineral between these two dates" — and each backend answers them its
    own way: the relational one with SQL aggregates, the DynamoDB one by reading
    the partition and aggregating in Python. The caller never knows which is
    active.

    Selected with PERSISTENCE_BACKEND in the .env: 'sql' (default, the relational
    models untouched) or 'dynamodb'. Royalties and the rest of the service are
    not covered here and keep running on the relational side.
'''
from dataclasses import dataclass
from datetime import date as date_type
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger


ENV_VARS = load_and_validate_env_vars({}, optional_env_vars = {
    'PERSISTENCE_BACKEND': str,
})
BACKEND = (ENV_VARS['PERSISTENCE_BACKEND'] or 'sql').strip().lower()
DYNAMODB_BACKEND = 'dynamodb'
SQL_BACKEND = 'sql'


@dataclass(frozen = True)
class MineralRecord:
    '''
        A mineral of the catalogue, independent of the storage engine.

        Only what the business actually reads from storage: the identifier and
        the name. Unit, chemical symbol and market live in OFFICIAL_MINERALS,
        the published catalogue the bulletins are built from, not in the table.
    '''
    mineral_id: str
    name: str


@dataclass(frozen = True)
class PriceRecord:
    '''One daily quotation, independent of the storage engine.'''
    mineral_id: str
    date: date_type
    price_low: Optional[float] = None
    price_high: Optional[float] = None


def uses_dynamodb() -> bool:
    '''
        Whether the quotations run on DynamoDB.

        Returns:
            bool: True when PERSISTENCE_BACKEND selects DynamoDB.
    '''
    return BACKEND == DYNAMODB_BACKEND


def list_minerals(db: Optional[Session] = None) -> List[MineralRecord]:
    '''
        Returns the mineral catalogue.

        Args:
            db (Session | None): Relational session; ignored on DynamoDB.

        Returns:
            List[MineralRecord]: Every mineral on record.
    '''
    if uses_dynamodb():
        from services import crud_dyb # pylint: disable=import-outside-toplevel
        return [
            MineralRecord(mineral_id = item.mineral_id, name = item.name)
            for item in crud_dyb.list_minerals()
        ]

    from models.mining_analysis import Mineral # pylint: disable=import-outside-toplevel
    return [
        MineralRecord(mineral_id = str(row.id), name = row.name)
        for row in db.query(Mineral.id, Mineral.name).all()
    ]


def prices_in_window(
    mineral_id: str,
    start: date_type,
    end: date_type,
    db: Optional[Session] = None
) -> List[PriceRecord]:
    '''
        Returns the quotations of one mineral inside a date window.

        Args:
            mineral_id (str): Mineral identifier.
            start (date): First date of the window.
            end (date): Last date of the window.
            db (Session | None): Relational session; ignored on DynamoDB.

        Returns:
            List[PriceRecord]: Quotations with a price, ordered by date.
    '''
    if uses_dynamodb():
        from services import crud_dyb # pylint: disable=import-outside-toplevel
        items = crud_dyb.query_prices(mineral_id, start, end)
        return [
            PriceRecord(item.mineral_id, item.date, item.price_low, item.price_high)
            for item in items if item.price_low is not None
        ]

    from models.mining_analysis import MiningPrice # pylint: disable=import-outside-toplevel
    rows = (
        db.query(MiningPrice)
        .filter(
            MiningPrice.mineral_id == int(mineral_id),
            MiningPrice.date >= start,
            MiningPrice.date <= end,
            MiningPrice.price_low.isnot(None)
        )
        .order_by(MiningPrice.date)
        .all()
    )
    return [
        PriceRecord(
            str(row.mineral_id), row.date,
            None if row.price_low is None else float(row.price_low),
            None if row.price_high is None else float(row.price_high)
        )
        for row in rows
    ]


def average_low(
    mineral_id: str,
    start: date_type,
    end: date_type,
    db: Optional[Session] = None
) -> Optional[Tuple[float, int]]:
    '''
        Returns the mean of price_low over the days with data in the window.

        The mean divides by the number of distinct days that actually carry a
        price, matching the published rule "se aplica el promedio para ese
        número de días".

        Args:
            mineral_id (str): Mineral identifier.
            start (date): First date of the window.
            end (date): Last date of the window.
            db (Session | None): Relational session; ignored on DynamoDB.

        Returns:
            tuple[float, int] | None: (average, days with data), or None when the
                window holds no data.
    '''
    if uses_dynamodb():
        # DynamoDB cannot average: read the partition and aggregate here.
        prices = prices_in_window(mineral_id, start, end)
        by_day = {price.date: price.price_low for price in prices}
        if not by_day:
            return None
        return sum(by_day.values()) / len(by_day), len(by_day)

    from sqlalchemy import func # pylint: disable=import-outside-toplevel
    from models.mining_analysis import MiningPrice # pylint: disable=import-outside-toplevel
    result = (
        db.query(
            func.avg(MiningPrice.price_low).label('avg_low'),
            # pylint reads SQLAlchemy's generic function factory as not callable.
            func.count(func.distinct(MiningPrice.date)).label('days') # pylint: disable=not-callable
        )
        .filter(
            MiningPrice.mineral_id == int(mineral_id),
            MiningPrice.date >= start,
            MiningPrice.date <= end,
            MiningPrice.price_low.isnot(None)
        )
        .one()
    )
    if not result.days or result.avg_low is None:
        return None
    return float(result.avg_low), int(result.days)



def latest_prices_before(
    mineral_id: str,
    ref_date: date_type,
    limit: int = 2,
    db: Optional[Session] = None
) -> List[PriceRecord]:
    '''
        Returns the most recent quotations of one mineral up to a date.

        The daily report needs the last quotation and the one before it, to
        report the change between them. On the relational side that is an
        ORDER BY ... LIMIT; DynamoDB cannot order by anything but the sort key,
        which here is exactly the date, so the query walks the partition
        backwards and stops at the limit.

        Args:
            mineral_id (str): Mineral identifier.
            ref_date (date): Latest date to consider, inclusive.
            limit (int): How many quotations to return, newest first.
            db (Session | None): Relational session; ignored on DynamoDB.

        Returns:
            List[PriceRecord]: Quotations newest first, at most `limit` of them.
    '''
    if uses_dynamodb():
        from services import crud_dyb # pylint: disable=import-outside-toplevel
        items = crud_dyb.query_prices(mineral_id, None, ref_date, descending = True)
        return [
            PriceRecord(item.mineral_id, item.date, item.price_low, item.price_high)
            for item in items
        ][:limit]

    from models.mining_analysis import MiningPrice # pylint: disable=import-outside-toplevel
    rows = (
        db.query(MiningPrice)
        .filter(
            MiningPrice.mineral_id == int(mineral_id),
            MiningPrice.date <= ref_date
        )
        .order_by(MiningPrice.date.desc())
        .limit(limit)
        .all()
    )
    return [
        PriceRecord(
            str(row.mineral_id), row.date,
            None if row.price_low is None else float(row.price_low),
            None if row.price_high is None else float(row.price_high)
        )
        for row in rows
    ]


def date_bounds(db: Optional[Session] = None) -> Tuple[Optional[date_type],
                                                       Optional[date_type]]:
    '''
        Returns the first and last dates with a stored quotation.

        The biweekly history uses them to know which periods exist at all. SQL
        answers with MIN/MAX; DynamoDB has no aggregates, so the whole table is
        scanned and reduced here. That is acceptable because the table holds one
        item per mineral per day and the history screen is not a hot path.

        Args:
            db (Session | None): Relational session; ignored on DynamoDB.

        Returns:
            Tuple[date | None, date | None]: Oldest and newest dates, or
                (None, None) when nothing is stored.
    '''
    if uses_dynamodb():
        from services import crud_dyb # pylint: disable=import-outside-toplevel
        dates = [item.date for item in crud_dyb.scan_prices()]
        return (min(dates), max(dates)) if dates else (None, None)

    from models.mining_analysis import MiningPrice # pylint: disable=import-outside-toplevel
    from sqlalchemy import func # pylint: disable=import-outside-toplevel
    bounds = db.query(
        func.min(MiningPrice.date), func.max(MiningPrice.date)
    ).one()
    return bounds[0], bounds[1]



@dataclass(frozen = True)
class QuotationRecord:
    '''
    One quotation together with the mineral it belongs to.

    The full-catalogue endpoint publishes both, and on DynamoDB there is no join
    to lean on: the name comes from the catalogue table and the rest of the
    metadata from OFFICIAL_MINERALS, the published catalogue the bulletins are
    built from.
    '''
    mineral_id: str
    mineral_name: str
    date: date_type
    price_low: Optional[float] = None
    price_high: Optional[float] = None


def all_quotations(db: Optional[Session] = None) -> List[QuotationRecord]:
    '''
        Returns every stored quotation with its mineral.

        SQL joins; DynamoDB scans the table and resolves the names against the
        catalogue read once. It is the one access pattern the table was not
        keyed for, which is why it belongs to a full export and not to a screen
        that refreshes.

        Args:
            db (Session | None): Relational session; ignored on DynamoDB.

        Returns:
            List[QuotationRecord]: Quotations ordered by date, then mineral.
    '''
    if uses_dynamodb():
        from services import crud_dyb # pylint: disable=import-outside-toplevel
        names = {item.mineral_id: item.name for item in crud_dyb.list_minerals()}
        return sorted(
            (
                QuotationRecord(
                    item.mineral_id, names.get(item.mineral_id, ''),
                    item.date, item.price_low, item.price_high
                )
                for item in crud_dyb.scan_prices()
            ),
            key = lambda record: (record.date, record.mineral_name)
        )

    from models.mining_analysis import ( # pylint: disable=import-outside-toplevel
        Mineral,
        MiningPrice
    )
    rows = (
        db.query(MiningPrice)
        .join(Mineral, Mineral.id == MiningPrice.mineral_id)
        .order_by(MiningPrice.date, Mineral.name)
        .all()
    )
    return [
        QuotationRecord(
            str(row.mineral_id), row.mineral.name, row.date,
            None if row.price_low is None else float(row.price_low),
            None if row.price_high is None else float(row.price_high)
        )
        for row in rows
    ]


def log_active_backend() -> None:
    '''
        Records which backend the quotations are being served from.

        Called at startup so a deployment states its persistence engine in the
        logs instead of leaving it to be guessed from a failure.
    '''
    message = f'Quotations store running on the "{BACKEND}" backend.'
    logger.info(message)
