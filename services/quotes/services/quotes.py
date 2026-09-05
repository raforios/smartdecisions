'''
    QUOTES domain — main module.

    Keeps our own history of the official exchange rate and serves it. The rate
    comes from outside (the Banco Central de Bolivia), so the service does two
    things: pulls what the source publishes into our store, and answers with the
    series we hold.

    Why keep a copy at all. The BCB serves one date per request, so building a
    series from it live would mean one call per day of history on every screen.
    Storing it also means the series survives the source being down, which for a
    figure a sale is settled at is the difference between a stale answer and no
    answer.

    A note that shapes everything built on this series: **on 27 June 2026 the
    regime changed**. Before that date the rate had been fixed at 6.86 for
    years; since then it floats, and it moved more in two months than in the
    previous decade. Any projection fitted over the whole history would conclude
    the rate stays at 6.86. Callers that project must start from the float.
'''
from datetime import date as date_type, timedelta
from typing import Any, Dict, List, Optional

from models.quotes import USD, ExchangeRateItem
from schemas.quotes import ForecastMethod, QuotesError
from services.bcb_source import SOURCE_NAME, fetch_official_rate
from services.environment import load_and_validate_env_vars
from services.exceptions import InvalidInputError, ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.quotes_utils import get_rate, put_rate, query_rates
from services.rate_forecast import (
    backtest_windows,
    project as project_rate
)
from services.utils import get_current_time_gmt, handle_service_errors


ENV_VARS = load_and_validate_env_vars({}, optional_env_vars = {
    'FLOAT_REGIME_START': str,
    'SYNC_MAX_DAYS': int,
    'SCENARIO_MAX_DAYS': int,
    'SCHEDULED_SYNC_DAYS': int,
})

# The day the rate stopped being fixed. Series fitted for projection must start
# here: the years of 6.86 before it belong to a different regime and would flatten
# any trend. Configurable because it is a fact about the country, not about the
# code, and a second regime change must not require a release.
FLOAT_REGIME_START: date_type = date_type.fromisoformat(
    ENV_VARS['FLOAT_REGIME_START'] or '2026-06-27'
)

# Upper bound for a single sync, so one call cannot spend an hour hitting the
# BCB one date at a time.
SYNC_MAX_DAYS = ENV_VARS['SYNC_MAX_DAYS'] or 400

# Days each scheduled run covers. More than one on purpose: the BCB publishes
# nothing on weekends and holidays, and a run that failed yesterday must be
# repaired by the next one instead of leaving a hole in the series forever.
# Re-reading a stored date costs nothing — the sync skips it without asking the
# source.
SCHEDULED_SYNC_DAYS = ENV_VARS['SCHEDULED_SYNC_DAYS'] or 7

# Longest horizon a sale scenario may compare. Beyond a quarter the
# projection says more about the fitted line than about the market.
SCENARIO_MAX_DAYS = ENV_VARS['SCENARIO_MAX_DAYS'] or 90


@handle_service_errors('QUOTES')
async def sync_rates_service(
    days_back: int = 30,
    currency: str = USD
) -> Dict[str, Any]:
    '''
    Pulls the published rate for the recent dates into our own history.

    Dates already stored are not fetched again: the BCB never revises a
    published rate, so re-reading them would only spend requests. Dates the
    source publishes nothing for — weekends, holidays — are counted apart and
    are not an error.

    Args:
        days_back (int): How many days back from today to cover.
        currency (str): ISO 4217 code; only USD is published today.

    Returns:
        Dict[str, Any]: Payload matching SyncResult shape.

    Raises:
        InvalidInputError: If the requested window is out of bounds.
    '''
    if days_back < 1 or days_back > SYNC_MAX_DAYS:
        raise InvalidInputError(detail = QuotesError.INVALID_DATE_RANGE.value)

    today = get_current_time_gmt().date()
    window = [today - timedelta(days = offset) for offset in range(days_back)]

    stored, already_present, without_publication = 0, 0, 0
    for day in sorted(window):
        if get_rate(currency, day) is not None:
            already_present += 1
            continue
        rate = fetch_official_rate(day)
        if rate is None:
            without_publication += 1
            continue
        put_rate(ExchangeRateItem(
            currency = currency,
            date = day,
            official_rate = rate,
            source = SOURCE_NAME,
            retrieved_at = get_current_time_gmt().isoformat()
        ))
        stored += 1

    message = (
        f'Exchange-rate sync for {currency}: {stored} stored, '
        f'{already_present} already present, {without_publication} not published.'
    )
    logger.info(message)
    return {
        'currency': currency,
        'requested_days': days_back,
        'stored': stored,
        'already_present': already_present,
        'without_publication': without_publication,
        'date_from': min(window),
        'date_to': max(window),
    }


@handle_service_errors('QUOTES')
async def get_history_service(
    date_from: Optional[date_type] = None,
    date_to: Optional[date_type] = None,
    currency: str = USD,
    float_regime_only: bool = True
) -> Dict[str, Any]:
    '''
    Returns the stored series for a currency.

    Args:
        date_from (date | None): First date to include.
        date_to (date | None): Last date to include.
        currency (str): ISO 4217 code.
        float_regime_only (bool): When True and no lower bound is given, the
            series starts at the float regime. That is the default because the
            fixed years are not comparable with what came after, and a chart
            spanning both reads as a cliff rather than as two regimes.

    Returns:
        Dict[str, Any]: Payload matching ExchangeRateHistory shape.

    Raises:
        InvalidInputError: If the window is inverted.
    '''
    if date_from and date_to and date_from > date_to:
        raise InvalidInputError(detail = QuotesError.INVALID_DATE_RANGE.value)

    start = date_from or (FLOAT_REGIME_START if float_regime_only else None)
    rates = query_rates(currency, start, date_to)

    message = f'Exchange-rate history for {currency}: {len(rates)} day(s).'
    logger.info(message)
    return {
        'currency': currency,
        'days': len(rates),
        'date_from': rates[0].date if rates else None,
        'date_to': rates[-1].date if rates else None,
        'rates': [
            {'date': item.date, 'rate': item.official_rate} for item in rates
        ],
    }


def stored_rates(
    currency: str = USD,
    start: Optional[date_type] = None,
    end: Optional[date_type] = None
) -> List[ExchangeRateItem]:
    '''
    Reads the stored series directly, for callers inside the service.

    Args:
        currency (str): ISO 4217 code.
        start (date | None): First date to include.
        end (date | None): Last date to include.

    Returns:
        List[ExchangeRateItem]: Rates ordered by date.
    '''
    return query_rates(currency, start or FLOAT_REGIME_START, end)


@handle_service_errors('QUOTES')
async def sale_scenario_service(
    quantity: float,
    unit_price_usd: float,
    days_ahead: int = 30,
    mineral_change_percent: Optional[float] = None
) -> Dict[str, Any]:
    '''
    Compares settling a sale today against settling it after a wait.

    Both sides of the price move: the mineral is quoted in dollars and the
    dollar is quoted in bolivianos. Waiting can gain on one and lose on the
    other, and what the seller actually decides on is the difference in
    bolivianos, which is what this returns.

    The mineral's expected change is supplied by the caller rather than fetched:
    it comes from the MINING_ANALYSIS projection, and keeping it as an input
    means this service answers with whatever assumption the seller wants to
    test — including none, which prices the currency move alone.

    Args:
        quantity (float): Units being sold.
        unit_price_usd (float): Price per unit today, in dollars.
        days_ahead (int): How far ahead to compare.
        mineral_change_percent (float | None): Expected change of the unit
            price over the horizon. None prices the currency move alone.

    Returns:
        Dict[str, Any]: Payload matching SaleScenario shape.

    Raises:
        InvalidInputError: If the horizon is out of bounds.
        ServiceUnavailableError: If no rate has been published yet.
    '''
    if days_ahead < 1 or days_ahead > SCENARIO_MAX_DAYS:
        raise InvalidInputError(detail = QuotesError.INVALID_DATE_RANGE.value)

    history = stored_rates()
    if not history:
        raise ServiceUnavailableError(detail = QuotesError.NO_RATE_PUBLISHED.value)

    today_rate = history[-1].official_rate
    amount_usd_today = round(quantity * unit_price_usd, 2)
    today = {
        'exchange_rate': today_rate,
        'mineral_price': unit_price_usd,
        'amount_usd': amount_usd_today,
        'amount_bob': round(amount_usd_today * today_rate, 2),
    }

    projection = project_rate(history, days_ahead)
    if projection.final_rate is None:
        message = (
            f'Sale scenario over {days_ahead} day(s) priced today only: the rate '
            f'history does not support a projection ({projection.confidence.value}).'
        )
        logger.info(message)
        return {
            'days_ahead': days_ahead,
            'rate_confidence': projection.confidence,
            'rate_change_percent': None,
            'mineral_change_percent': mineral_change_percent,
            'today': today,
            'projected': None,
            'difference_bob': None,
            'difference_percent': None,
        }

    future_price = unit_price_usd * (1 + (mineral_change_percent or 0.0) / 100)
    amount_usd_future = round(quantity * future_price, 2)
    projected = {
        'exchange_rate': round(projection.final_rate, 4),
        'mineral_price': round(future_price, 4),
        'amount_usd': amount_usd_future,
        'amount_bob': round(amount_usd_future * projection.final_rate, 2),
    }

    difference = round(projected['amount_bob'] - today['amount_bob'], 2)
    difference_percent = (
        round(difference / today['amount_bob'] * 100, 2)
        if today['amount_bob'] else None
    )

    message = (
        f'Sale scenario over {days_ahead} day(s): {difference:+.2f} Bs '
        f'({difference_percent:+.2f}%).'
    )
    logger.info(message)
    return {
        'days_ahead': days_ahead,
        'rate_confidence': projection.confidence,
        'rate_change_percent': projection.change_percent,
        'mineral_change_percent': mineral_change_percent,
        'today': today,
        'projected': projected,
        'difference_bob': difference,
        'difference_percent': difference_percent,
    }


@handle_service_errors('QUOTES')
async def get_forecast_service(
    days_ahead: int = 30,
    currency: str = USD
) -> Dict[str, Any]:
    '''
    Projects the exchange rate forward on its own.

    The sale scenario answers "today or in a month" for a given sale; this
    answers the narrower question of where the rate itself is heading, which is
    what a chart of the dollar needs.

    Args:
        days_ahead (int): How far ahead to project.
        currency (str): ISO 4217 code.

    Returns:
        Dict[str, Any]: Payload matching RateForecast shape.

    Raises:
        InvalidInputError: If the horizon is out of bounds.
        ServiceUnavailableError: If no rate has been published yet.
    '''
    if days_ahead < 1 or days_ahead > SCENARIO_MAX_DAYS:
        raise InvalidInputError(detail = QuotesError.INVALID_DATE_RANGE.value)

    history = stored_rates(currency)
    if not history:
        raise ServiceUnavailableError(detail = QuotesError.NO_RATE_PUBLISHED.value)

    projection = project_rate(history, days_ahead)
    message = (
        f'{currency} projected {days_ahead} day(s) over {len(history)} observation(s); '
        f'confidence {projection.confidence.value}.'
    )
    logger.info(message)
    return {
        'currency': currency,
        'days_ahead': days_ahead,
        'confidence': projection.confidence,
        'change_percent': projection.change_percent,
        'accuracy': {
            'method': ForecastMethod.DAMPED_TREND,
            'mean_absolute_error': projection.expected_error,
            'baseline_method': ForecastMethod.NAIVE,
            'baseline_error': projection.baseline_error,
            'windows': backtest_windows(
                [item.official_rate for item in history], days_ahead
            ),
        },
        'last_rate': history[-1].official_rate,
        'last_date': history[-1].date,
        'final_rate': (
            None if projection.final_rate is None else round(projection.final_rate, 4)
        ),
        'history': [
            {'date': item.date, 'rate': item.official_rate} for item in history
        ],
        'projected': [
            {'date': day, 'rate': round(rate, 4)} for day, rate in projection.points
        ],
    }


@handle_service_errors('QUOTES')
async def scheduled_sync_service(currency: str = USD) -> Dict[str, Any]:
    '''
    Runs the sync the way the daily schedule needs it.

    Exists apart from `sync_rates_service` so the window the schedule uses is a
    decision of the domain and not of whoever wrote the cron expression: the
    trigger says *when*, this says *how much to repair*.

    Args:
        currency (str): ISO 4217 code.

    Returns:
        Dict[str, Any]: Payload matching SyncResult shape.
    '''
    message = f'Scheduled {currency} sync over {SCHEDULED_SYNC_DAYS} day(s).'
    logger.info(message)
    return await sync_rates_service(
        days_back = SCHEDULED_SYNC_DAYS, currency = currency
    )


__all__ = [
    'FLOAT_REGIME_START',
    'get_forecast_service',
    'get_history_service',
    'scheduled_sync_service',
    'sale_scenario_service',
    'stored_rates',
    'sync_rates_service',
]
