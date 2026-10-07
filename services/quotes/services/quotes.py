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
import re
from datetime import date as date_type, timedelta
from typing import Any

from models.quotes import USD, ExchangeRateItem
from schemas.quotes import ForecastMethod, QuotesError
from services.bcb_source import SOURCE_NAME, fetch_official_rate
from services.environment import load_and_validate_env_vars
from services.exceptions import (
    InvalidInputError,
    ResourceNotFoundError,
    ServiceUnavailableError
)
from services.logger_config import custom_logger as logger
from services.quotes_utils import get_rate, put_rate, query_rates
from services.forecast_models import MODELS
from services.rate_forecast import (
    backtest_windows,
    confidence_for,
    project as project_rate,
    run_bench
)
from services.usdt_source import SOURCE_NAME as USDT_SOURCE_NAME, fetch_usdt_rate
from services.utils import get_current_time_gmt, handle_service_errors


# Every business decision below is read from the environment and **required**.
# A fallback in code is still a number living in code: the day the service is
# deployed without one of these it must say so, not run quietly on a value
# nobody chose.
ENV_VARS = load_and_validate_env_vars({
    'FLOAT_REGIME_START': str,
    'FIXED_REGIME_RATE': float,
    'SYNC_MAX_DAYS': int,
    'SYNC_DEFAULT_DAYS': int,
    'SCENARIO_MAX_DAYS': int,
    'SCENARIO_DEFAULT_DAYS': int,
    'SCHEDULED_SYNC_DAYS': int,
    'PARALLEL_CURRENCY': str,
    'RATE_BLOCK_WEEKDAYS': str,
    'AMOUNT_DECIMALS': int,
    'RATE_DECIMALS': int,
    'HISTORY_FLOAT_REGIME_ONLY': int,
})

# The day the rate stopped being fixed. Series fitted for projection must start
# here: the years of 6.86 before it belong to a different regime and would
# flatten any trend. A second regime change must not require a release.
FLOAT_REGIME_START: date_type = date_type.fromisoformat(ENV_VARS['FLOAT_REGIME_START'])
# What the rate was worth while it was fixed. A figure of the regime, not of
# the market, so it is declared and not looked up — and not written into the
# code either, because the day somebody analyses another country it changes.
FIXED_REGIME_RATE: float = ENV_VARS['FIXED_REGIME_RATE']

# Weekdays the BCB publishes as a single block, as Python numbers them (Monday
# is 0). Today it is Saturday-Sunday-Monday: the rate published on Friday night
# governs the three. It is a decision of the central bank, not an invariant —
# the day they move to a five-day block, this is one line of `.env`.
#
# Any non-digit separates: the value must not carry commas, because the deploy
# hands the whole `.env` to `--environment Variables={...}` and a comma there
# ends one variable and starts the next. Reading it this way means the file can
# use `5-6-0`, `5 6 0` or anything else legible without the parser caring.
RATE_BLOCK_WEEKDAYS = tuple(
    int(found) for found in re.findall(r'\d+', ENV_VARS['RATE_BLOCK_WEEKDAYS'])
)

# Upper bound for a single sync, so one call cannot spend an hour hitting the
# BCB one date at a time, and the window a caller gets without asking.
SYNC_MAX_DAYS = ENV_VARS['SYNC_MAX_DAYS']
SYNC_DEFAULT_DAYS = ENV_VARS['SYNC_DEFAULT_DAYS']

# Days each scheduled run covers. More than one on purpose: a run that failed
# yesterday must be repaired by the next one instead of leaving a hole in the
# series forever. Re-reading a stored date costs nothing — the sync skips it
# without asking the source.
SCHEDULED_SYNC_DAYS = ENV_VARS['SCHEDULED_SYNC_DAYS']
# The code the USDT series is stored under, next to the official USD.
PARALLEL_CURRENCY = ENV_VARS['PARALLEL_CURRENCY']

# Longest horizon a projection may reach, and the one used when none is asked
# for. Beyond a quarter the projection says more about the model than about the
# market.
SCENARIO_MAX_DAYS = ENV_VARS['SCENARIO_MAX_DAYS']
SCENARIO_DEFAULT_DAYS = ENV_VARS['SCENARIO_DEFAULT_DAYS']

# How many decimals a settled amount and a quoted rate carry. Money and
# quotation are not the same precision, and neither is ours to assume.
AMOUNT_DECIMALS = ENV_VARS['AMOUNT_DECIMALS']

# Whether a history request without a lower bound starts at the float regime.
# It is the sane default, but it is a decision about what a chart should show,
# not an invariant of the code.
HISTORY_FLOAT_REGIME_ONLY = bool(ENV_VARS['HISTORY_FLOAT_REGIME_ONLY'])
RATE_DECIMALS = ENV_VARS['RATE_DECIMALS']


def validity_of(day: date_type) -> tuple[date_type, date_type]:
    '''
    Returns the window a published rate governs.

    The BCB publishes the rate the night before, and the one it publishes for a
    **Saturday covers Saturday, Sunday and Monday** — the page says so in
    letters: "vigente para el sábado 5, domingo 6 y lunes 7". Every other day
    governs only itself.

    This matters more than it looks. Reading the series as one value per day
    suggests the rate of Monday is news on Monday, when in fact it was known and
    fixed since Friday night. A miner closing a sale on Saturday is settling at a
    figure that will not move until Tuesday, and that is a fact worth stating
    rather than leaving the reader to notice three equal numbers in a row.

    Args:
        day (date): Date the rate was published for.

    Returns:
        tuple[date, date]: First and last day the rate is in force.
    '''
    if day.weekday() not in RATE_BLOCK_WEEKDAYS:
        return day, day

    first, last = day, day
    while (first - timedelta(days = 1)).weekday() in RATE_BLOCK_WEEKDAYS:
        first -= timedelta(days = 1)
    while (last + timedelta(days = 1)).weekday() in RATE_BLOCK_WEEKDAYS:
        last += timedelta(days = 1)
    return first, last


@handle_service_errors('QUOTES')
async def sync_rates_service(
    days_back: int = SYNC_DEFAULT_DAYS,
    currency: str = USD
) -> dict[str, Any]:
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
        dict[str, Any]: Payload matching SyncResult shape.

    Raises:
        InvalidInputError: If the requested window is out of bounds.
    '''
    if days_back < 1 or days_back > SYNC_MAX_DAYS:
        raise InvalidInputError(detail = QuotesError.INVALID_DATE_RANGE.value)

    today = get_current_time_gmt().date()
    # The window reaches the END of the block today belongs to, not today.
    # The BCB publishes on Friday night a rate valid Saturday, Sunday and
    # Monday: all three are already published on Saturday, and stopping at
    # "today" left Monday missing until Monday — so the screen showed it as
    # projected when it had been a published figure since Friday.
    last_day = validity_of(today)[1]
    first_day = today - timedelta(days = days_back - 1)
    window = [
        first_day + timedelta(days = offset)
        for offset in range((last_day - first_day).days + 1)
    ]

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
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    currency: str = USD,
    float_regime_only: bool = HISTORY_FLOAT_REGIME_ONLY
) -> dict[str, Any]:
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
        dict[str, Any]: Payload matching ExchangeRateHistory shape.

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
    start: date_type | None = None,
    end: date_type | None = None
) -> list[ExchangeRateItem]:
    '''
    Reads the stored series directly, for callers inside the service.

    Args:
        currency (str): ISO 4217 code.
        start (date | None): First date to include.
        end (date | None): Last date to include.

    Returns:
        list[ExchangeRateItem]: Rates ordered by date.
    '''
    return query_rates(currency, start or FLOAT_REGIME_START, end)


@handle_service_errors('QUOTES')
async def sale_scenario_service(
    quantity: float,
    unit_price_usd: float,
    days_ahead: int = SCENARIO_DEFAULT_DAYS,
    mineral_change_percent: float | None = None
) -> dict[str, Any]:
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
        dict[str, Any]: Payload matching SaleScenario shape.

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
    amount_usd_today = round(quantity * unit_price_usd, AMOUNT_DECIMALS)
    today = {
        'exchange_rate': today_rate,
        'mineral_price': unit_price_usd,
        'amount_usd': amount_usd_today,
        'amount_bob': round(amount_usd_today * today_rate, AMOUNT_DECIMALS),
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
    amount_usd_future = round(quantity * future_price, AMOUNT_DECIMALS)
    projected = {
        'exchange_rate': round(projection.final_rate, RATE_DECIMALS),
        'mineral_price': round(future_price, RATE_DECIMALS),
        'amount_usd': amount_usd_future,
        'amount_bob': round(amount_usd_future * projection.final_rate, AMOUNT_DECIMALS),
    }

    difference = round(projected['amount_bob'] - today['amount_bob'], AMOUNT_DECIMALS)
    difference_percent = (
        round(difference / today['amount_bob'] * 100, AMOUNT_DECIMALS)
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
    days_ahead: int = SCENARIO_DEFAULT_DAYS,
    currency: str = USD
) -> dict[str, Any]:
    '''
    Projects the exchange rate forward on its own.

    The sale scenario answers "today or in a month" for a given sale; this
    answers the narrower question of where the rate itself is heading, which is
    what a chart of the dollar needs.

    Args:
        days_ahead (int): How far ahead to project.
        currency (str): ISO 4217 code.

    Returns:
        dict[str, Any]: Payload matching RateForecast shape.

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
        'valid_from': validity_of(history[-1].date)[0],
        'valid_to': validity_of(history[-1].date)[1],
        'final_rate': (
            None if projection.final_rate is None else round(projection.final_rate, RATE_DECIMALS)
        ),
        'history': [
            {'date': item.date, 'rate': item.official_rate} for item in history
        ],
        'projected': [
            {'date': day, 'rate': round(rate, RATE_DECIMALS)} for day, rate in projection.points
        ],
    }


@handle_service_errors('QUOTES')
async def scheduled_sync_service(currency: str = USD) -> dict[str, Any]:
    '''
    Runs the sync the way the daily schedule needs it.

    Exists apart from `sync_rates_service` so the window the schedule uses is a
    decision of the domain and not of whoever wrote the cron expression: the
    trigger says *when*, this says *how much to repair*.

    Args:
        currency (str): ISO 4217 code.

    Returns:
        dict[str, Any]: Payload matching SyncResult shape.
    '''
    message = f'Scheduled {currency} sync over {SCHEDULED_SYNC_DAYS} day(s).'
    logger.info(message)
    result = await sync_rates_service(
        days_back = SCHEDULED_SYNC_DAYS, currency = currency
    )
    store_today_usdt()
    return result


def store_today_usdt() -> bool:
    '''
        Keeps today's USDT price, once. Binance only answers the price of now,
        so the series is the readings we keep.

        A failure is logged and swallowed on purpose: the parallel reference
        going dark for a day must never cost the official rate of that day,
        which was stored before this runs.

        Returns:
            bool: True when a reading was stored.
    '''
    today = get_current_time_gmt().date()
    if get_rate(PARALLEL_CURRENCY, today) is not None:
        return False
    try:
        price = fetch_usdt_rate()
    except ServiceUnavailableError as error:
        error_msg = f'USDT reading of {today} skipped: {error.detail}.'
        logger.warning(error_msg)
        return False
    if price is None:
        return False
    put_rate(ExchangeRateItem(
        currency = PARALLEL_CURRENCY, date = today, official_rate = price,
        source = USDT_SOURCE_NAME, retrieved_at = get_current_time_gmt().isoformat()
    ))
    message = f'USDT reading of {today}: {price} BOB.'
    logger.info(message)
    return True


@handle_service_errors('QUOTES')
async def get_bench_service(
    days_ahead: int = SCENARIO_DEFAULT_DAYS,
    currency: str = USD,
    models: list[str] | None = None
) -> dict[str, Any]:
    '''
    Runs several models over the same series and returns them measured.

    Without `models` it runs the whole bench. Each one comes with its projection
    and with the error it made when replaying the series, ordered from the one
    that missed least to the one that missed most — including the default when
    it loses, which is exactly what has to be visible.

    Args:
        days_ahead (int): Days to project.
        currency (str): ISO 4217 code.
        models (list[str] | None): Models to run. None runs them all.

    Returns:
        dict[str, Any]: Payload matching the ModelBench shape.

    Raises:
        InvalidInputError: If the horizon is out of range.
        ServiceUnavailableError: If no quotations are stored yet.
    '''
    if days_ahead < 1 or days_ahead > SCENARIO_MAX_DAYS:
        raise InvalidInputError(detail = QuotesError.INVALID_DATE_RANGE.value)

    history = stored_rates(currency)
    if not history:
        raise ServiceUnavailableError(detail = QuotesError.NO_RATE_PUBLISHED.value)

    chosen = [name for name in (models or list(MODELS)) if name in MODELS]
    if not chosen:
        raise InvalidInputError(detail = QuotesError.UNKNOWN_MODEL.value)

    runs = run_bench(history, days_ahead, chosen)
    values = [item.official_rate for item in history]

    message = (
        f'{currency} bench over {len(history)} observation(s): '
        f'{len(runs)} model(s) at {days_ahead} day(s).'
    )
    logger.info(message)
    return {
        'currency': currency,
        'days_ahead': days_ahead,
        'confidence': confidence_for(len(history)),
        'last_rate': history[-1].official_rate,
        'last_date': history[-1].date,
        'valid_from': validity_of(history[-1].date)[0],
        'valid_to': validity_of(history[-1].date)[1],
        'windows': backtest_windows(values, days_ahead),
        'history': [
            {'date': item.date, 'rate': item.official_rate} for item in history
        ],
        'runs': runs,
    }


@handle_service_errors('QUOTES')
async def rate_on_service(
    day: date_type,
    currency: str = USD
) -> dict[str, Any]:
    '''
    The rate in force on a day, and where it comes from.

    This is what lets a report be read in dollars: every transaction is
    converted at the rate of ITS OWN day, not at today's. A sale of March and
    a sale of September are not the same dollars, and averaging them at one
    rate is the mistake this exists to prevent.

    The BCB does not publish every day, so the rate in force is the latest one
    published on or before the day asked about — the same rule `validity_of`
    states from the other side. Before the float began the rate was fixed, and
    a day from then answers with that figure and says so, instead of pretending
    there is a market quote for it.

    Args:
        day (date): The day being asked about.
        currency (str): ISO 4217 code.

    Returns:
        dict[str, Any]: The rate, the day it was published, and its regime.

    Raises:
        ResourceNotFoundError: When nothing was published on or before the day
            and the day is inside the float regime.
    '''
    if day < FLOAT_REGIME_START:
        return {
            'date': day.isoformat(),
            'currency': currency,
            'rate': FIXED_REGIME_RATE,
            'published_on': None,
            'regime': 'FIXED'
        }

    published = query_rates(currency, None, day)
    if not published:
        error_msg = f'No {currency} rate published on or before {day}.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = QuotesError.NO_RATE_FOR_DATE.value)

    latest = published[-1]
    return {
        'date': day.isoformat(),
        'currency': currency,
        'rate': round(float(latest.official_rate), RATE_DECIMALS),
        'published_on': latest.date.isoformat(),
        'regime': 'FLOAT'
    }
