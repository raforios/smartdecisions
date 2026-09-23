'''
    Official quotation reports: the daily table, the biweekly official price
    and its history.

    The official price of a fortnight is the arithmetic mean of the previous
    fortnight's daily quotations — the mean of the 1st–15th rules the 16th–30th.
    Everything here reads the quotations through `prices_store`, so it works
    the same over the relational store and over DynamoDB.
'''
import calendar
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Iterator, List, Optional, Tuple

from boto3.resources.base import ServiceResource
from sqlalchemy.orm import Session

from models.mining_analysis import Mineral
from schemas.mining_analysis import MiningResult, MiningStatus
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError
from services.mining_analysis import CHANGE_DECIMALS, OFFICIAL_MINERALS, normalize_name
from services.prices_store import (
    average_low,
    date_bounds,
    latest_prices_before,
    list_minerals
)
from services.utils import handle_service_errors

# Required, not optional: a fallback written in code is still a number the
# code chose.
ENV_VARS = load_and_validate_env_vars({'MAX_FALLBACK_PERIODS': int})

def biweekly_period_bounds(
    year: int,
    month: int,
    half: int
) -> Tuple[date, date]:
    '''
    Returns (period_start, period_end) for the requested half of the month.
    Half 1 covers days 1-15, half 2 covers day 16 through month end.
    '''
    if half not in (1, 2):
        raise InvalidInputError(detail = 'half must be 1 (days 1-15) or 2 (16-end).')
    if half == 1:
        return date(year, month, 1), date(year, month, 15)
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 16), date(year, month, last_day)


def period_of(day: date) -> Tuple[int, int, int]:
    '''
    Returns the biweekly period a date falls into.

    Args:
        day (date): Any calendar date.

    Returns:
        Tuple[int, int, int]: Its (year, month, half).
    '''
    return day.year, day.month, 1 if day.day <= 15 else 2


def next_biweekly_period(
    year: int,
    month: int,
    half: int
) -> Tuple[int, int, int]:
    '''
    Returns the biweekly period immediately after the one given.

    Args:
        year (int): Year of the period.
        month (int): Month of the period.
        half (int): 1 for days 1-15, 2 for 16-end.

    Returns:
        Tuple[int, int, int]: The following (year, month, half).
    '''
    if half == 1:
        return year, month, 2
    if month == 12:
        return year + 1, 1, 1
    return year, month + 1, 1


def prev_biweekly_period(
    year: int,
    month: int,
    half: int
) -> Tuple[int, int, int]:
    '''
    Returns (prev_year, prev_month, prev_half) — the period immediately before
    the requested one. Wraps to December of the previous year when needed.
    '''
    if half == 2:
        return year, month, 1
    if month == 1:
        return year - 1, 12, 2
    return year, month - 1, 2


def resolve_mineral_id_map(
    dynamodb_resource: Optional[ServiceResource],
    db: Optional[Session] = None
) -> Dict[str, str]:
    '''
    Builds {normalized_name: mineral_id} for the official catalog. Minerals
    missing from the catalog are simply absent from the map; callers must
    handle that case by emitting a fallback row.
    '''
    return {
        normalize_name(record.name): record.mineral_id
        for record in list_minerals(dynamodb_resource, db = db)
    }


def _empty_daily_row(
    catalog: Dict[str, str],
    ref_date: date
) -> Dict[str, Any]:
    '''
    Returns a placeholder row used when no price exists for the mineral at all.
    '''
    return {
        'mineral': catalog['name'],
        'chemical_symbol': catalog['chemical_symbol'],
        'unit': catalog['unit'],
        'quoted_in': catalog['quoted_in'],
        'price_low': 0.0,
        'price_high': 0.0,
        'price_date': ref_date,
        'previous_price_low': 0.0,
        'previous_price_date': None,
        'change_pct': 0.0,
        'is_fallback': True,
    }


@handle_service_errors('MINING_ANALYSIS')
async def get_daily_report_service(
    dynamodb_resource: Optional[ServiceResource],
    ref_date: date,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    '''
    Builds the daily mineral report (template Minerales_01).

    For every mineral in OFFICIAL_MINERALS, picks the most recent t_mining_prices
    row whose date is <= ref_date. `is_fallback` is True when no entry exists on
    ref_date itself and an older record was used.

    Args:
        db (Session): Database session.
        ref_date (date): Reference date for the report (typically "today").

    Returns:
        Dict[str, Any]: Payload matching DailyReportResponse shape.
    '''
    mineral_ids = resolve_mineral_id_map(dynamodb_resource, db = db)
    rows: List[Dict[str, Any]] = []

    for catalog in OFFICIAL_MINERALS:
        normalized = normalize_name(catalog['name'])
        mineral_id = mineral_ids.get(normalized)
        if mineral_id is None:
            rows.append(_empty_daily_row(catalog, ref_date))
            continue

        # Through the store, so the report reads the same on either backend.
        latest_two = latest_prices_before(dynamodb_resource, str(mineral_id), ref_date, 2, db = db)
        if not latest_two:
            rows.append(_empty_daily_row(catalog, ref_date))
            continue

        price = latest_two[0]
        prev = latest_two[1] if len(latest_two) > 1 else None
        price_low = float(price.price_low or 0)
        prev_low = float(prev.price_low or 0) if prev is not None else 0.0
        change_pct = (
            ((price_low - prev_low) / prev_low) * 100
            if prev is not None and prev_low > 0
            else 0.0
        )

        rows.append({
            'mineral': catalog['name'],
            'chemical_symbol': catalog['chemical_symbol'],
            'unit': catalog['unit'],
            'quoted_in': catalog['quoted_in'],
            'price_low': price_low,
            'price_high': float(price.price_high or price.price_low or 0),
            'price_date': price.date,
            'previous_price_low': prev_low,
            'previous_price_date': prev.date if prev is not None else None,
            'change_pct': round(change_pct, CHANGE_DECIMALS),
            'is_fallback': price.date != ref_date,
        })

    return {
        'status': MiningStatus.SUCCESS,
        'result': MiningResult.DAILY_REPORT_GENERATED,
        'ref_date': ref_date,
        'rows': rows,
    }


def _compute_biweekly_average(
    dynamodb_resource: Optional[ServiceResource],
    mineral_id: int,
    window: Tuple[date, date],
    db: Optional[Session] = None
) -> Optional[Tuple[float, int]]:
    '''
    Returns (avg_price_low, sample_size) for the mineral within the window,
    or None when no day has data inside the period.

    sample_size is the number of distinct days with a non-null price_low; the
    mean divides by that exact count, matching the spec "se aplica el promedio
    para ese número de días".
    '''
    # Delegated to the store so the same rule holds on either backend: the
    # relational one aggregates with SQL, DynamoDB reads the partition and
    # averages in Python. This function no longer knows which is active.
    return average_low(dynamodb_resource, str(mineral_id), window, db = db)


# How far back the report looks for the last published quotation of a mineral,
# in biweekly periods. Two years is generous for "el del periodo anterior que se
# tenga" and still bounds the search on a mineral that was never quoted.
_MAX_FALLBACK_PERIODS: int = ENV_VARS['MAX_FALLBACK_PERIODS']


@dataclass(frozen = True)
class _BiweeklyAverage:
    '''
    One mineral's figure for a biweekly report, and which window produced it.

    `is_fallback` is True when the number does not belong to the requested
    period: either the mineral is absent from the catalogue, or the report had
    to walk back to an earlier period to find a quotation. The UI marks those
    rows so a reader never takes an old price for a current one.
    '''
    avg_price_low: float
    sample_size: int
    period_start: date
    period_end: date
    is_fallback: bool

    def as_row(self) -> Dict[str, Any]:
        '''
        Renders the figure as the keys the report payload carries.

        Returns:
            Dict[str, Any]: Fields merged into the mineral's row.
        '''
        return {
            'avg_price_low': self.avg_price_low,
            'sample_size': self.sample_size,
            'period_start': self.period_start,
            'period_end': self.period_end,
            'is_fallback': self.is_fallback,
        }


def _average_with_fallback(
    dynamodb_resource: Optional[ServiceResource],
    mineral_id: Optional[str],
    period: Tuple[int, int, int],
    db: Optional[Session] = None
) -> _BiweeklyAverage:
    '''
    Returns the mineral's average for the requested period, or the most recent
    earlier one when that period has no data.

    Args:
        db (Session): Database session.
        mineral_id (str | None): Mineral identifier, None when the catalogue
            has no such mineral.
        period (tuple[int, int, int]): Requested (year, month, half).

    Returns:
        _BiweeklyAverage: The figure and the window it actually came from.
    '''
    year, month, half = period
    start, end = biweekly_period_bounds(year, month, half)

    if mineral_id is None:
        return _BiweeklyAverage(0.0, 0, start, end, is_fallback = True)

    calc = _compute_biweekly_average(dynamodb_resource, mineral_id, (start, end), db = db)
    if calc is not None:
        return _BiweeklyAverage(calc[0], calc[1], start, end, is_fallback = False)

    current = period
    for _ in range(_MAX_FALLBACK_PERIODS):
        current = prev_biweekly_period(*current)
        past_start, past_end = biweekly_period_bounds(*current)
        calc = _compute_biweekly_average(
            dynamodb_resource, mineral_id, (past_start, past_end), db = db
        )
        if calc is not None:
            return _BiweeklyAverage(
                calc[0], calc[1], past_start, past_end, is_fallback = True
            )

    return _BiweeklyAverage(0.0, 0, start, end, is_fallback = True)


@handle_service_errors('MINING_ANALYSIS')
async def get_biweekly_report_service(
    dynamodb_resource: Optional[ServiceResource],
    period: Tuple[int, int, int],
    db: Optional[Session] = None
) -> Dict[str, Any]:
    '''
    Builds the biweekly official report (template Minerales_02).

    Period halves are fixed: half=1 → days 1-15, half=2 → days 16-end. Returns
    the simple mean of price_low over the days that have data inside the
    window. When a mineral has no data in the requested period, walks back one
    biweekly period at a time looking for the most recent value (matching
    "se muestra el del periodo anterior que se tenga"). The lookback is capped
    at 24 periods (~1 year) to avoid pathological scans.

    Args:
        db (Session): Database session.
        year (int): Calendar year of the report.
        month (int): Month (1-12) of the report.
        half (int): 1 for days 1-15, 2 for 16-end.

    Returns:
        Dict[str, Any]: Payload matching BiweeklyReportResponse shape.
    '''
    year, month, half = period
    period_start, period_end = biweekly_period_bounds(year, month, half)
    mineral_ids = resolve_mineral_id_map(dynamodb_resource, db = db)
    rows: List[Dict[str, Any]] = [
        {
            'mineral': catalog['name'],
            'chemical_symbol': catalog['chemical_symbol'],
            'unit': catalog['unit'],
            'quoted_in': catalog['quoted_in'],
            **_average_with_fallback(
                dynamodb_resource,
                mineral_ids.get(normalize_name(catalog['name'])),
                (year, month, half),
                db = db
            ).as_row()
        }
        for catalog in OFFICIAL_MINERALS
    ]

    return {
        'status': MiningStatus.SUCCESS,
        'result': MiningResult.BIWEEKLY_REPORT_GENERATED,
        'year': year,
        'month': month,
        'half': half,
        'period_start': period_start,
        'period_end': period_end,
        'rows': rows,
    }


def _iter_biweekly_periods(
    period_from: date,
    period_to: date
) -> Iterator[Tuple[int, int, int]]:
    '''
    Yields (year, month, half) tuples covering every biweekly period between
    `period_from` and `period_to` (inclusive) in chronological order.
    '''
    year, month = period_from.year, period_from.month
    half = 1 if period_from.day <= 15 else 2
    end_year, end_month = period_to.year, period_to.month
    end_half = 1 if period_to.day <= 15 else 2

    while (year, month, half) <= (end_year, end_month, end_half):
        yield year, month, half
        if half == 1:
            half = 2
        else:
            half = 1
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1


@handle_service_errors('MINING_ANALYSIS')
async def get_biweekly_history_service(
    dynamodb_resource: Optional[ServiceResource],
    period_from: Optional[date] = None,
    period_to: Optional[date] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    '''
    Returns every biweekly period inside the requested window that has at
    least one cotización for any official mineral.

    When `period_from`/`period_to` are omitted, the bounds are derived from
    the MIN/MAX dates in t_mining_prices so the caller automatically sees the
    full history.

    Args:
        db (Session): Database session.
        period_from (Optional[date]): Inclusive lower bound. Defaults to the
            earliest cotización in storage.
        period_to (Optional[date]): Inclusive upper bound. Defaults to the
            latest cotización in storage.

    Returns:
        Dict[str, Any]: Payload matching BiweeklyHistoryResponse shape.
    '''
    oldest, newest = date_bounds(dynamodb_resource, db = db)
    if oldest is None:
        today = date.today()
        return {
            'status': MiningStatus.SUCCESS,
            'result': MiningResult.BIWEEKLY_HISTORY_GENERATED,
            'period_from': period_from or today,
            'period_to': period_to or today,
            'periods': [],
        }

    period_from = period_from or oldest
    period_to = period_to or newest
    if period_from > period_to:
        raise InvalidInputError(detail = 'period_from must be <= period_to.')

    periods: List[Dict[str, Any]] = []
    for year, month, half in _iter_biweekly_periods(period_from, period_to):
        snapshot = await get_biweekly_report_service(
            dynamodb_resource, (year, month, half), db = db
        )
        # Skip purely-fallback snapshots — they carry no information about
        # the requested period itself, only about a recovered prior one.
        if all(row['is_fallback'] for row in snapshot['rows']):
            continue
        periods.append({
            'year': year,
            'month': month,
            'half': half,
            'period_start': snapshot['period_start'],
            'period_end': snapshot['period_end'],
            'rows': snapshot['rows'],
        })

    return {
        'status': MiningStatus.SUCCESS,
        'result': MiningResult.BIWEEKLY_HISTORY_GENERATED,
        'period_from': period_from,
        'period_to': period_to,
        'periods': periods,
    }


def ensure_official_minerals(db: Session) -> int:
    '''
    Idempotent seed: inserts any official mineral missing from t_minerals.

    Returns the number of rows actually inserted. Existing rows are left
    untouched to preserve any operator-curated metadata.
    '''
    existing = {normalize_name(r.name) for r in db.query(Mineral.name).all()}
    inserted = 0
    for catalog in OFFICIAL_MINERALS:
        if normalize_name(catalog['name']) in existing:
            continue
        db.add(Mineral(
            name = catalog['name'],
            unit = catalog['unit'],
            chemical_symbol = catalog['chemical_symbol'],
            quoted_in = catalog['quoted_in'],
            method = None,
        ))
        inserted += 1
    if inserted:
        db.commit()
    return inserted
