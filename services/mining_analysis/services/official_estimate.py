'''
    The official quotation the fortnight in progress is heading to.

    The Ministry publishes, after each fortnight closes, the arithmetic mean of
    that fortnight's daily quotes; that mean rules the *next* fortnight. So on
    any day the market already knows most of the number: the running mean of
    the days quoted so far. This module computes it per mineral from the market
    series, puts it next to the quotation in force, and applies the Art. 227
    scale to say what royalty rate it implies.
'''
from datetime import date as date_type
from typing import Dict, List, Optional

from boto3.resources.base import ServiceResource

from schemas.market import (
    EstimateConfidence,
    EstimateResponse,
    EstimateRow,
    MarketError,
    MarketPriceRow,
    MarketPricesResponse,
    MarketSource
)
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError, RegisterNotFoundError
from services.logger_config import custom_logger as logger
from services.market_sources import source_for
from services.prices_dyb import query_market_prices
from services.mining_analysis import OFFICIAL_MINERALS, normalize_name
from services.official_reports import (
    biweekly_period_bounds,
    next_biweekly_period,
    period_of,
    prev_biweekly_period
)
from services.price_forecast import official_round
from services.prices_store import average_low, list_minerals
from services.royalty_rules import apply_rule, rules_by_mineral
from services.utils import get_current_time_gmt

ENV_VARS = load_and_validate_env_vars({
    'ESTIMATE_HIGH_CONFIDENCE_DAYS': int,
    'ESTIMATE_MEDIUM_CONFIDENCE_DAYS': int,
    'CHANGE_DECIMALS': int
})
HIGH_CONFIDENCE_DAYS = ENV_VARS['ESTIMATE_HIGH_CONFIDENCE_DAYS']
MEDIUM_CONFIDENCE_DAYS = ENV_VARS['ESTIMATE_MEDIUM_CONFIDENCE_DAYS']
CHANGE_DECIMALS = ENV_VARS['CHANGE_DECIMALS']


def confidence_for(days_quoted: int) -> EstimateConfidence:
    '''
        How much to trust a running mean, by how many trading days feed it.

        Args:
            days_quoted (int): Days with a market quote in the fortnight so far.

        Returns:
            EstimateConfidence: The band.
    '''
    if days_quoted <= 0:
        return EstimateConfidence.NONE
    if days_quoted >= HIGH_CONFIDENCE_DAYS:
        return EstimateConfidence.HIGH
    if days_quoted >= MEDIUM_CONFIDENCE_DAYS:
        return EstimateConfidence.MEDIUM
    return EstimateConfidence.LOW


def _catalogue_entry(name: str) -> Dict[str, str]:
    '''
        Published metadata (symbol, unit) of a catalogue mineral.
    '''
    return next((item for item in OFFICIAL_MINERALS
                 if normalize_name(item['name']) == normalize_name(name)), {})


def _previous_official(
    dynamodb_resource: ServiceResource,
    mineral_id: str,
    as_of: date_type
) -> Optional[float]:
    '''
        The quotation in force on `as_of`: the official mean of the fortnight
        before the one in progress, from the official daily series.
    '''
    year, month, half = prev_biweekly_period(*period_of(as_of))
    start, end = biweekly_period_bounds(year, month, half)
    average = average_low(dynamodb_resource, mineral_id, (start, end))
    return official_round(average[0]) if average is not None else None


def estimate_row(
    dynamodb_resource: ServiceResource,
    mineral_id: str,
    name: str,
    as_of: date_type
) -> EstimateRow:
    '''
        The anticipated quotation of one mineral on `as_of`.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            mineral_id (str): Catalogue id.
            name (str): Mineral name.
            as_of (date): The day the estimate is made.

        Returns:
            EstimateRow: Running mean, quotation in force, implied rates.
    '''
    entry = _catalogue_entry(name)
    resolved = source_for(name)
    start, _ = biweekly_period_bounds(*period_of(as_of))
    previous = _previous_official(dynamodb_resource, mineral_id, as_of)
    row = EstimateRow(
        mineral_id = mineral_id, name = name,
        chemical_symbol = entry.get('chemical_symbol', ''), unit = entry.get('unit', ''),
        source = resolved[0] if resolved else None,
        days_quoted = 0, calendar_days_elapsed = (as_of - start).days + 1,
        previous_official = previous, confidence = EstimateConfidence.NONE
    )
    if resolved is None:
        return row
    prices = query_market_prices(dynamodb_resource, mineral_id, {'from': start, 'to': as_of})
    if not prices:
        return row
    running = official_round(sum(item.price for item in prices) / len(prices))
    rule = rules_by_mineral(dynamodb_resource).get(mineral_id)
    rates = apply_rule(rule, running) if rule else None
    return row.model_copy(update = {
        'days_quoted': len(prices),
        'running_average': running,
        'latest_price': prices[-1].price,
        'latest_date': prices[-1].date,
        'change_percent': (round(100.0 * (running - previous) / previous, CHANGE_DECIMALS)
                           if previous else None),
        'export_rate': rates[0] if rates else None,
        'internal_rate': rates[1] if rates else None,
        'rate_basis': rates[2] if rates else None,
        'confidence': confidence_for(len(prices))
    })


def estimate_all(
    dynamodb_resource: ServiceResource,
    as_of: Optional[date_type] = None
) -> EstimateResponse:
    '''
        The anticipated official quotation of every catalogue mineral.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            as_of (date | None): The day of the estimate; today by default.

        Returns:
            EstimateResponse: One row per mineral plus the periods involved.
    '''
    day = as_of or get_current_time_gmt().date()
    year, month, half = period_of(day)
    start, end = biweekly_period_bounds(year, month, half)
    valid_from, valid_to = biweekly_period_bounds(*next_biweekly_period(year, month, half))
    rows = [estimate_row(dynamodb_resource, mineral.mineral_id, mineral.name, day)
            for mineral in list_minerals(dynamodb_resource)]
    quoted = sum(1 for row in rows if row.days_quoted)
    message = f'Estimate as of {day}: {quoted} mineral(s) with market days.'
    logger.info(message)
    return EstimateResponse(
        as_of = day, period_year = year, period_month = month, period_half = half,
        period_start = start, period_end = end, valid_from = valid_from, valid_to = valid_to,
        rows = sorted(rows, key = lambda row: (int(row.mineral_id) if row.mineral_id.isdigit()
                                                else 0))
    )


def market_series(
    dynamodb_resource: ServiceResource,
    mineral_id: str,
    date_from: Optional[date_type],
    date_to: Optional[date_type]
) -> MarketPricesResponse:
    '''
        The stored market series of one mineral, for the chart.

        Args:
            dynamodb_resource (ServiceResource): The boto3 DynamoDB resource.
            mineral_id (str): Catalogue id.
            date_from (date | None): First day.
            date_to (date | None): Last day.

        Returns:
            MarketPricesResponse: Rows oldest first.
    '''
    if date_from and date_to and date_from > date_to:
        raise InvalidInputError(detail = MarketError.INVALID_DATE_RANGE.value)
    mineral = next((item for item in list_minerals(dynamodb_resource)
                    if item.mineral_id == mineral_id), None)
    if mineral is None:
        raise RegisterNotFoundError(detail = MarketError.UNKNOWN_MINERAL.value)
    if source_for(mineral.name) is None:
        raise InvalidInputError(detail = MarketError.MINERAL_NOT_MARKET_QUOTED.value)
    entry = _catalogue_entry(mineral.name)
    rows: List[MarketPriceRow] = [
        MarketPriceRow(date = item.date, price = item.price, source = MarketSource(item.source))
        for item in query_market_prices(
            dynamodb_resource, mineral_id, {'from': date_from, 'to': date_to}
        )
    ]
    return MarketPricesResponse(
        mineral_id = mineral_id, name = mineral.name, unit = entry.get('unit', ''), items = rows
    )
