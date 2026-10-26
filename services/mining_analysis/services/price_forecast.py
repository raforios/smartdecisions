'''
    Price projection for the mineral quotations.

    Answers one question: given what a mineral has been quoted at, what is it
    likely to be quoted at over the coming weeks. It is a projection of the
    observed trend, not a market prediction — no external signal enters here,
    only the series the Ministry hands us.

    Two methods, both deliberately simple:

      LINEAR          Least-squares fit over the whole window. Reads the
                      direction of the series and extends it. This is the
                      default because a quotation that has been climbing for
                      weeks is best described by that climb.
      MOVING_AVERAGE  Mean of the most recent days, projected flat. Useful for
                      a series that oscillates without direction, where a fitted
                      line would invent a trend that is not there.

    The arithmetic is asked of ML_FUNCTIONS, the base service of calculations
    (Rafael, 17-oct and 23-oct-2026); what stays here is what belongs to the
    minerals: the confidence, the fallback when the line sinks, the floor at
    zero and the official quotation. Nothing heavier is used on purpose: with
    roughly a hundred daily points, a fitted line and a moving average are as
    much as the data supports. A model
    with more parameters would produce a more confident-looking curve without
    being any more right, which on a bulletin that reaches a mining association
    is worse than useless.

    Confidence is reported alongside every projection and derives from how much
    history backs it, because the same arithmetic over three weeks and over four
    months does not deserve the same weight.
'''
from dataclasses import dataclass
from datetime import date as date_type, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import requests
from boto3.resources.base import ServiceResource
from sqlalchemy.orm import Session

from schemas.market import MarketError
from schemas.mining_analysis import (
    ForecastConfidence,
    ForecastMethod,
    MiningResult,
    MiningStatus
)
from services.utils import load_parameters
from services.logger_config import custom_logger as logger
from services.mining_analysis import OFFICIAL_MINERALS
from services.official_reports import (
    biweekly_period_bounds,
    next_biweekly_period,
    normalize_name,
    period_of,
    prev_biweekly_period,
    resolve_mineral_id_map
)
from services.prices_store import PriceRecord, prices_in_window
from services.exceptions import ServiceUnavailableError
from services.utils import (
    API_URL,
    REQUEST_TIMEOUT_SECONDS,
    get_current_time_gmt,
    handle_service_errors
)


# Required, not optional: a fallback in code is still a number the code chose.
ENV_VARS = load_parameters({
    'FORECAST_MIN_DAYS': int,
    'FORECAST_HIGH_CONFIDENCE_DAYS': int,
    'FORECAST_MEDIUM_CONFIDENCE_DAYS': int,
    'FORECAST_MOVING_AVERAGE_WINDOW': int,
    'FORECAST_HISTORY_POINTS': int,
    'OFFICIAL_HISTORY_PERIODS': int,
    'BACKTEST_MIN_TRAIN': int,
    'BACKTEST_MIN_WINDOWS': int,
    'FORECAST_COLLAPSE_FLOOR_RATIO': float,
    'ERROR_DECIMALS': int,
    'CHANGE_DECIMALS': int,
    'PRICE_DECIMALS': int,
    'PUBLISHED_PRICE_DECIMALS': int
})

# Decimals a published error, a published percentage and a published price
# carry. Stored prices keep four; a bulletin publishes two.
ERROR_DECIMALS = ENV_VARS['ERROR_DECIMALS']
CHANGE_DECIMALS = ENV_VARS['CHANGE_DECIMALS']
PRICE_DECIMALS = ENV_VARS['PRICE_DECIMALS']
PUBLISHED_PRICE_DECIMALS = ENV_VARS['PUBLISHED_PRICE_DECIMALS']

# How much history each replay needs, and how many replays make a published
# average honest.
BACKTEST_MIN_TRAIN = ENV_VARS['BACKTEST_MIN_TRAIN']
BACKTEST_MIN_WINDOWS = ENV_VARS['BACKTEST_MIN_WINDOWS']

# How many closed fortnights travel with the projection so the reader can
# check it against what actually happened. Six is a quarter of a year.
OFFICIAL_HISTORY_PERIODS = ENV_VARS['OFFICIAL_HISTORY_PERIODS']

# Below this, a projection says more about the noise than about the mineral.
MIN_DAYS = ENV_VARS['FORECAST_MIN_DAYS']
# Thresholds for how much weight the projection deserves.
HIGH_CONFIDENCE_DAYS = ENV_VARS['FORECAST_HIGH_CONFIDENCE_DAYS']
MEDIUM_CONFIDENCE_DAYS = ENV_VARS['FORECAST_MEDIUM_CONFIDENCE_DAYS']
# Days averaged by the moving-average method.
MOVING_AVERAGE_WINDOW = ENV_VARS['FORECAST_MOVING_AVERAGE_WINDOW']

# A linear projection that drops to this fraction of the lowest observed price
# has stopped describing the mineral and started describing the fitted line.
# Wolfram, with three weeks of steeply falling quotations, reached zero inside a
# 30-day horizon: the arithmetic was right and the answer was nonsense.
_COLLAPSE_FLOOR_RATIO: float = ENV_VARS['FORECAST_COLLAPSE_FLOOR_RATIO']

# How many observed points travel back with each mineral. The UI draws the
# trend behind the projection; a couple of hundred points is plenty for that
# and keeps the payload from growing with the archive.
HISTORY_POINTS = ENV_VARS['FORECAST_HISTORY_POINTS']

# Earliest date the store is asked for. The quotations start in 2026; this is
# simply a lower bound for the range query.
_HISTORY_FLOOR: date_type = date_type(2000, 1, 1)


@dataclass(frozen = True)
class Projection:
    '''
        The outcome of projecting one mineral.

        `method` is the method that actually produced the numbers, which is not
        always the one requested: a linear fit that collapses falls back, and
        the caller has to be able to say which one it published.
    '''
    points: list[tuple[date_type, float]]
    method: ForecastMethod
    confidence: ForecastConfidence
    change_percent: float | None
    mean_absolute_error: float | None = None
    baseline_error: float | None = None

def confidence_for(sample_size: int) -> ForecastConfidence:
    '''
        Grades a projection by how much history backs it.

        Args:
            sample_size (int): Days of observed quotations.

        Returns:
            ForecastConfidence: The grade the caller must surface.
    '''
    if sample_size < MIN_DAYS:
        return ForecastConfidence.INSUFFICIENT
    if sample_size >= HIGH_CONFIDENCE_DAYS:
        return ForecastConfidence.HIGH
    if sample_size >= MEDIUM_CONFIDENCE_DAYS:
        return ForecastConfidence.MEDIUM
    return ForecastConfidence.LOW


def _ml_projection(
    prices: list[float],
    days_ahead: int,
    method: ForecastMethod,
    auth_token: str
) -> dict[str, Any]:
    '''
        One method run over a mineral's series in ML_FUNCTIONS, measured by
        replaying the series from every point that leaves enough history.

        Args:
            prices (list[float]): Observed quotations in chronological order.
            days_ahead (int): How many days to project.
            method (ForecastMethod): The method to run.
            auth_token (str): The caller's Authorization header.

        Returns:
            dict[str, Any]: `forecast`, `mean_absolute_error` and the naive
                guess's `baseline_error`.

        Raises:
            ServiceUnavailableError: SOURCE_UNAVAILABLE when ML_FUNCTIONS cannot answer.
    '''
    body = {'values': prices, 'horizon': days_ahead, 'models': [method.value],
            'min_train': BACKTEST_MIN_TRAIN, 'min_windows': BACKTEST_MIN_WINDOWS,
            'window': MOVING_AVERAGE_WINDOW}
    try:
        response = requests.post(f'{API_URL}/v1/prediction/forecast/compare', json = body,
                                 headers = {'Authorization': auth_token},
                                 timeout = REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as error:
        error_msg = f'Network error asking ML_FUNCTIONS for a {method.value} projection: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = MarketError.SOURCE_UNAVAILABLE.value) from error
    if not response.ok:
        error_msg = (f'ML_FUNCTIONS refused the {method.value} projection: '
                     f'status={response.status_code} body={response.text[:200]}')
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = MarketError.SOURCE_UNAVAILABLE.value)
    answer = response.json()
    run = answer['runs'][0]
    errors = {'mean_absolute_error': run.get('mean_absolute_error'),
              'baseline_error': answer.get('naive_mean_absolute_error')}
    return {'forecast': [float(value) for value in run['forecast']],
            **{key: None if value is None else round(float(value), ERROR_DECIMALS)
               for key, value in errors.items()}}


def _future_dates(
    last_day: date_type,
    days_ahead: int
) -> list[date_type]:
    '''
        Builds the calendar dates a projection covers.

        Args:
            last_day (date): Last observed quotation date.
            days_ahead (int): How many days to project.

        Returns:
            list[date]: Consecutive dates after the last observed one.
    '''
    return [last_day + timedelta(days = offset) for offset in range(1, days_ahead + 1)]


def project(
    prices: list[PriceRecord],
    days_ahead: int,
    method: ForecastMethod = ForecastMethod.DAMPED_TREND,
    auth_token: str = ''
) -> Projection:
    '''
        Projects one mineral's quotations forward.

        A fitted line that sinks below the floor inside the horizon is not
        published as "this mineral will be worth nothing": the projection falls
        back to the level of the recent days and reports the method that
        actually produced the number. A moving average never goes below zero.

        Args:
            prices (list[PriceRecord]): Observed quotations, any order.
            days_ahead (int): How many days to project.
            method (ForecastMethod): Which projection to apply.
            auth_token (str): The caller's Authorization header, for ML_FUNCTIONS.

        Returns:
            Projection: The projected points, the method actually used, the
                confidence the sample earns, the change against the last
                observed price and the measured errors. Empty when the history
                cannot support a projection.
    '''
    observed = sorted(
        (record for record in prices if record.price_low is not None),
        key = lambda record: record.date
    )
    confidence = confidence_for(len(observed))
    if confidence is ForecastConfidence.INSUFFICIENT or days_ahead < 1:
        return Projection([], method, confidence, None)

    values = [float(record.price_low) for record in observed]
    used_method = method
    run = _ml_projection(values, days_ahead, used_method, auth_token)
    if used_method is ForecastMethod.LINEAR and any(
            value <= min(values) * _COLLAPSE_FLOOR_RATIO for value in run['forecast']):
        used_method = ForecastMethod.MOVING_AVERAGE
        error_msg = (f'{method.value} projection collapses over {len(observed)} '
                     f'observations; fell back to {used_method.value}.')
        logger.warning(error_msg)
        run = _ml_projection(values, days_ahead, used_method, auth_token)
    projected = ([max(value, 0.0) for value in run['forecast']]
                 if used_method is ForecastMethod.MOVING_AVERAGE else run['forecast'])

    change = (round((projected[-1] - values[-1]) / values[-1] * 100, CHANGE_DECIMALS)
              if values[-1] else None)
    message = (f'Projected {days_ahead} day(s) with {used_method.value} over '
               f'{len(observed)} observations; confidence {confidence.value}.')
    logger.info(message)
    return Projection(list(zip(_future_dates(observed[-1].date, days_ahead), projected)),
                      used_method, confidence, change,
                      run['mean_absolute_error'], run['baseline_error'])


# The official quotation is published with two decimals, so that is the figure
# the service returns: rounding it later, in the browser, would let the API and
# the bulletin disagree on the number a sale is settled at.
_OFFICIAL_QUANTUM: Decimal = Decimal(1).scaleb(-PUBLISHED_PRICE_DECIMALS)


def official_round(value: float) -> float:
    '''
    Rounds an official average to two decimals, HALF_UP.

    Never with float formatting: the price is stored with four decimals and
    `f'{12.825:.2f}'` yields 12.82, because the binary float behind that literal
    is 12.8249999…. A published quotation cannot round a half down, and
    `reports_renderer` already rounds this way for the same reason.

    Args:
        value (float): Average to round.

    Returns:
        float: The same figure with two decimals.
    '''
    return float(Decimal(str(value)).quantize(_OFFICIAL_QUANTUM, rounding = ROUND_HALF_UP))


def _official_average(
    window: tuple[date_type, date_type],
    observed: dict[date_type, float],
    projected: dict[date_type, float]
) -> dict[str, Any] | None:
    '''
    Averages one biweekly window, using observations first and the projection
    only for the days still to come.

    Quotations are published on working days — of 104 observations in the
    series, 104 fall on weekdays — so the projection is read on weekdays only.
    Averaging over calendar days instead would put a denominator of 15 against a
    real one of 10 and quietly lower every projected official price.

    Args:
        window (tuple[date, date]): Period start and end, inclusive.
        observed (dict[date, float]): Quotations already published.
        projected (dict[date, float]): Projected daily values.

    Returns:
        dict[str, Any] | None: The average and how it was composed, or None
            when no day of the window has a value at all.
    '''
    start, end = window
    values: list[float] = []
    observed_days, projected_days, working_days = 0, 0, 0

    day = start
    while day <= end:
        if day.weekday() < 5:
            working_days += 1
        if day in observed:
            values.append(observed[day])
            observed_days += 1
        elif day.weekday() < 5 and day in projected:
            values.append(projected[day])
            projected_days += 1
        day += timedelta(days = 1)

    if not values:
        return None

    return {
        'period_start': start,
        'period_end': end,
        'avg_price_low': official_round(sum(values) / len(values)),
        'sample_size': len(values),
        'observed_days': observed_days,
        'projected_days': projected_days,
        # A window the horizon only half reaches still averages, but the reader
        # has to know the mean is missing days before treating it as the price.
        'is_complete': len(values) >= working_days,
    }


def _validity_of(period: tuple[int, int, int]) -> tuple[date_type, date_type]:
    '''
    Returns the window a period's average rules over.

    The Bolivian official quotation of a fortnight is the average of the
    fortnight before it: the mean of 1-15 September is the price every mining
    company settles on from 16 to 30 September. The number and the days it
    governs are therefore never the same window, and reporting one without the
    other is what makes a reader take an old price for a current one.

    Args:
        period (tuple[int, int, int]): The averaged (year, month, half).

    Returns:
        tuple[date, date]: First and last day the average is in force.
    '''
    return biweekly_period_bounds(*next_biweekly_period(*period))


def _projected_officials(
    reference: date_type,
    horizon_end: date_type,
    observed: dict[date_type, float],
    projected: dict[date_type, float]
) -> list[dict[str, Any]]:
    '''
    Builds the upcoming official quotations the horizon reaches.

    Starts at the period in course, whose average is part observed and part
    projected — the days already quoted are facts, and mixing them in is what
    makes the first projected official worth reading at all.

    Args:
        reference (date): Today.
        horizon_end (date): Last projected date.
        observed (dict[date, float]): Quotations already published.
        projected (dict[date, float]): Projected daily values.

    Returns:
        list[dict[str, Any]]: One entry per period, chronologically.
    '''
    entries: list[dict[str, Any]] = []
    period = period_of(reference)
    while True:
        entry = _official_average(biweekly_period_bounds(*period), observed, projected)
        if entry is None:
            break
        entry['valid_from'], entry['valid_to'] = _validity_of(period)
        entries.append(entry)
        period = next_biweekly_period(*period)
        # Stop once the projection no longer reaches the next window.
        if biweekly_period_bounds(*period)[0] > horizon_end:
            break
    return entries


def _official_history(
    reference: date_type,
    observed: dict[date_type, float],
    periods: int
) -> list[dict[str, Any]]:
    '''
    Returns the official quotations already published, newest first.

    The projected price is only worth as much as the reader's ability to check
    it against what actually happened, so the closed fortnights travel with the
    projection instead of forcing a second call to the report endpoint.

    Args:
        reference (date): Today.
        observed (dict[date, float]): Quotations already published.
        periods (int): How many closed fortnights to walk back.

    Returns:
        list[dict[str, Any]]: One entry per period that had quotations.
    '''
    entries: list[dict[str, Any]] = []
    # Two steps back: one lands on the period in force, which already travels
    # as `official_current` and would only repeat itself here.
    period = prev_biweekly_period(*prev_biweekly_period(*period_of(reference)))
    for _ in range(periods):
        entry = _official_average(biweekly_period_bounds(*period), observed, {})
        if entry is not None:
            entry['valid_from'], entry['valid_to'] = _validity_of(period)
            entries.append(entry)
        period = prev_biweekly_period(*period)
    return entries


def _official_block(
    mineral_id: str | None,
    projection: Projection,
    reference: date_type,
    dynamodb_resource: ServiceResource | None = None,
    db: Session | None = None
) -> dict[str, Any]:
    '''
    Builds the official-quotation view of one mineral.

    Args:
        mineral_id (str | None): Mineral identifier, None when uncatalogued.
        projection (Projection): The daily projection already computed.
        reference (date): Today, which decides which period is in force.
        db (Session | None): Relational session; ignored on DynamoDB.

    Returns:
        dict[str, Any]: `official_current`, `official_forecast` and the change
            between the price in force and the next one.
    '''
    empty: dict[str, Any] = {
        'official_current': None,
        'official_history': [],
        'official_forecast': [],
        'official_change_percent': None,
    }
    if mineral_id is None:
        return empty

    projected = dict(projection.points)
    horizon_end = max(projected) if projected else reference

    # The average in force today is the one of the period that already closed.
    current_period = prev_biweekly_period(*period_of(reference))
    # Read from the oldest fortnight the history shows through the horizon:
    # everything the averages below may need, in a single pass over storage.
    oldest = current_period
    for _ in range(OFFICIAL_HISTORY_PERIODS):
        oldest = prev_biweekly_period(*oldest)
    read_from = biweekly_period_bounds(*oldest)[0]
    observed = {
        record.date: record.price_low
        for record in prices_in_window(
            dynamodb_resource, mineral_id, (read_from, horizon_end), db = db
        )
        if record.price_low is not None
    }

    current = _official_average(
        biweekly_period_bounds(*current_period), observed, {}
    )
    if current is not None:
        current['valid_from'], current['valid_to'] = _validity_of(current_period)

    forecast = _projected_officials(reference, horizon_end, observed, projected)

    change = None
    if current and forecast and current['avg_price_low']:
        change = round(
            (forecast[0]['avg_price_low'] - current['avg_price_low'])
            / current['avg_price_low'] * 100, CHANGE_DECIMALS
        )

    return {
        'official_current': current,
        'official_history': _official_history(
            reference, observed, OFFICIAL_HISTORY_PERIODS
        ),
        'official_forecast': forecast,
        'official_change_percent': change,
    }


@handle_service_errors('MINING_ANALYSIS')
async def get_price_forecast_service(
    dynamodb_resource: ServiceResource | None,
    days_ahead: int = 30,
    method: ForecastMethod = ForecastMethod.DAMPED_TREND,
    db: Session | None = None,
    auth_token: str = ''
) -> dict[str, Any]:
    '''
    Projects every official mineral forward and returns the payload the API
    publishes.

    Minerals absent from the catalogue, or with too little history, still
    appear: they carry their confidence and an empty projection instead of
    being dropped, so the reader sees that the mineral exists and why there is
    no number rather than wondering where it went.

    Args:
        db (Session): Database session; ignored when running on DynamoDB.
        days_ahead (int): How many days to project.
        method (ForecastMethod): Requested projection method.
        auth_token (str): The caller's Authorization header, for ML_FUNCTIONS.

    Returns:
        dict[str, Any]: Payload matching PriceForecastResponse shape.
    '''
    mineral_ids = resolve_mineral_id_map(dynamodb_resource, db = db)
    minerals: list[dict[str, Any]] = []
    observed_dates: list[date_type] = []
    # One reference for every mineral, so the whole payload agrees on which
    # fortnight is in force even if the request straddles midnight.
    reference = get_current_time_gmt().date()

    for catalog in OFFICIAL_MINERALS:
        mineral_id = mineral_ids.get(normalize_name(catalog['name']))
        history = (
            prices_in_window(
                dynamodb_resource, mineral_id, (_HISTORY_FLOOR, date_type.max), db = db
            )
            if mineral_id is not None else []
        )
        observed_dates.extend(record.date for record in history)
        minerals.append(_forecast_row(
            ForecastRequest(
                catalog = catalog,
                history = history[-HISTORY_POINTS:],
                days_ahead = days_ahead,
                method = method,
                mineral_id = mineral_id,
                reference = reference,
                auth_token = auth_token
            ),
            dynamodb_resource = dynamodb_resource,
            db = db
        ))

    message = f'Price forecast built for {len(minerals)} minerals, {days_ahead} day(s).'
    logger.info(message)
    return {
        'status': MiningStatus.SUCCESS,
        'result': MiningResult.PRICE_FORECAST_GENERATED,
        'days_ahead': days_ahead,
        'history_from': min(observed_dates) if observed_dates else None,
        'history_to': max(observed_dates) if observed_dates else None,
        'minerals': minerals,
    }


@dataclass(frozen = True)
class ForecastRequest:
    '''
    What one mineral's row needs to be built.

    Grouped rather than passed loose because the row needs the catalogue entry,
    the history, the horizon, the method and who to ask for the official
    average — more arguments than a function should carry.
    '''
    catalog: dict[str, str]
    history: list[PriceRecord]
    days_ahead: int
    method: ForecastMethod
    mineral_id: str | None = None
    reference: date_type | None = None
    auth_token: str = ''


def _forecast_row(
    request: ForecastRequest,
    dynamodb_resource: ServiceResource | None = None,
    db: Session | None = None
) -> dict[str, Any]:
    '''
    Builds one mineral's entry of the forecast payload.

    Args:
        request (ForecastRequest): Catalogue entry, history and horizon.
        db (Session | None): Relational session; ignored on DynamoDB.

    Returns:
        dict[str, Any]: The mineral's row, daily projection and official
            quotation included.
    '''
    catalog, history = request.catalog, request.history
    days_ahead, method = request.days_ahead, request.method
    result = project(history, days_ahead, method, request.auth_token)
    priced = [record for record in history if record.price_low is not None]
    return {
        'mineral': catalog['name'],
        'chemical_symbol': catalog['chemical_symbol'],
        'unit': catalog['unit'],
        'method': result.method,
        'confidence': result.confidence,
        'sample_size': len(priced),
        'last_price': priced[-1].price_low if priced else None,
        'change_percent': result.change_percent,
        'mean_absolute_error': result.mean_absolute_error,
        'baseline_error': result.baseline_error,
        'history': [
            {'date': record.date, 'price': record.price_low} for record in priced
        ],
        'forecast': [
            {'date': day, 'price': round(price, PRICE_DECIMALS)}
            for day, price in result.points
        ],
        **_official_block(
            request.mineral_id,
            result,
            request.reference or get_current_time_gmt().date(),
            dynamodb_resource = dynamodb_resource,
            db = db
        ),
    }
