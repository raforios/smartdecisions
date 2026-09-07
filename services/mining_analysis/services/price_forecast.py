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

    Nothing heavier is used on purpose: with roughly a hundred daily points, a
    fitted line and a moving average are as much as the data supports. A model
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
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from schemas.mining_analysis import (
    ForecastConfidence,
    ForecastMethod,
    MiningResult,
    MiningStatus
)
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger
from services.mining_analysis import (
    OFFICIAL_MINERALS,
    _biweekly_period_bounds,
    _normalize_name,
    _prev_biweekly_period,
    _resolve_mineral_id_map
)
from services.prices_store import PriceRecord, prices_in_window
from services.utils import get_current_time_gmt, handle_service_errors


# Required, not optional: a fallback in code is still a number the code chose.
ENV_VARS = load_and_validate_env_vars({
    'FORECAST_MIN_DAYS': int,
    'FORECAST_HIGH_CONFIDENCE_DAYS': int,
    'FORECAST_MEDIUM_CONFIDENCE_DAYS': int,
    'FORECAST_MOVING_AVERAGE_WINDOW': int,
    'FORECAST_HISTORY_POINTS': int,
    'OFFICIAL_HISTORY_PERIODS': int,
    'HOLT_ALPHA': float,
    'HOLT_BETA': float,
    'HOLT_PHI': float,
    'BACKTEST_MIN_TRAIN': int,
    'BACKTEST_MIN_WINDOWS': int,
})

# Smoothing parameters, fitted by minimising the backtest error over the six
# minerals with enough history. Configurable because they belong to the data:
# refitting them as the series grows must not need a release.
HOLT_ALPHA = ENV_VARS['HOLT_ALPHA']
HOLT_BETA = ENV_VARS['HOLT_BETA']
HOLT_PHI = ENV_VARS['HOLT_PHI']

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
_COLLAPSE_FLOOR_RATIO: float = 0.25

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
    points: List[Tuple[date_type, float]]
    method: ForecastMethod
    confidence: ForecastConfidence
    change_percent: Optional[float]

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


def _project_damped(prices: List[float], days_ahead: int) -> List[float]:
    '''
        Extends the series with exponential smoothing and a damped trend.

        This replaced the least-squares line as the default. Measured over the
        six minerals with enough history, the line missed roughly twice as much
        as this at every horizon — 0.070 against 0.044 in normalised error at 30
        days — because a slope fitted over five months keeps being added forever,
        and a quotation does not work that way.

        The level follows the last observations and the trend **fades**: each
        further day inherits less of the recent drift, so the projection settles
        instead of running away. That is also why it cannot collapse through
        zero the way the line did with Wólfram.

        Args:
            prices (List[float]): Observed quotations in chronological order.
            days_ahead (int): How many days to project.

        Returns:
            List[float]: Projected values.
    '''
    level, trend = prices[0], prices[1] - prices[0]
    for price in prices[1:]:
        previous = level
        level = HOLT_ALPHA * price + (1 - HOLT_ALPHA) * (level + HOLT_PHI * trend)
        trend = HOLT_BETA * (level - previous) + (1 - HOLT_BETA) * HOLT_PHI * trend

    damping = np.cumsum(HOLT_PHI ** np.arange(1, days_ahead + 1))
    return [float(value) for value in level + damping * trend]


def _backtest(
    prices: List[float],
    days_ahead: int,
    naive: bool = False
) -> Optional[float]:
    '''
        Measures how far a model has missed on this very mineral.

        The series is replayed from every starting point that leaves room for
        the horizon. `naive` measures the benchmark instead — repeating the last
        quotation — which is what makes the published error judgeable rather
        than decorative.

        Args:
            prices (List[float]): Observed quotations in chronological order.
            days_ahead (int): Horizon to measure.
            naive (bool): Measure the benchmark instead of the model.

        Returns:
            float | None: Mean absolute error, or None with too few windows.
    '''
    errors: List[float] = []
    for cut in range(BACKTEST_MIN_TRAIN, len(prices) - days_ahead + 1):
        actual = np.array(prices[cut:cut + days_ahead])
        forecast = (np.full(days_ahead, prices[cut - 1]) if naive
                    else np.array(_project_damped(prices[:cut], days_ahead)))
        errors.append(float(np.mean(np.abs(forecast - actual))))

    if len(errors) < BACKTEST_MIN_WINDOWS:
        return None
    return round(float(np.mean(errors)), 4)


def _project_linear(prices: List[float], days_ahead: int) -> Optional[List[float]]:
    '''
        Extends the least-squares line fitted over the series.

        Args:
            prices (List[float]): Observed quotations in chronological order.
            days_ahead (int): How many days to project.

        Returns:
            List[float] | None: Projected values, or None when the fitted line
                runs into the floor. A steep decline over a short window sends
                the line below zero within the horizon, and clamping it at zero
                would publish "this mineral will be worth nothing" as if it were
                a finding. When that happens the series does not support a
                linear projection and the caller falls back.
    '''
    positions = np.arange(len(prices), dtype = float)
    slope, intercept = np.polyfit(positions, np.array(prices, dtype = float), 1)
    future = np.arange(len(prices), len(prices) + days_ahead, dtype = float)
    projected = [float(value) for value in slope * future + intercept]

    floor = min(prices) * _COLLAPSE_FLOOR_RATIO
    if any(value <= floor for value in projected):
        return None
    return projected


def _project_moving_average(prices: List[float], days_ahead: int) -> List[float]:
    '''
        Projects the mean of the most recent days as a flat line.

        Args:
            prices (List[float]): Observed quotations in chronological order.
            days_ahead (int): How many days to project.

        Returns:
            List[float]: The same value repeated; a moving average carries no
                direction of its own.
    '''
    window = prices[-MOVING_AVERAGE_WINDOW:]
    level = float(sum(window) / len(window))
    return [max(level, 0.0)] * days_ahead


def _future_dates(last_day: date_type, days_ahead: int) -> List[date_type]:
    '''
        Builds the calendar dates a projection covers.

        Args:
            last_day (date): Last observed quotation date.
            days_ahead (int): How many days to project.

        Returns:
            List[date]: Consecutive dates after the last observed one.
    '''
    return [last_day + timedelta(days = offset) for offset in range(1, days_ahead + 1)]


# Which callable produces each method. A projector may answer None when the
# series does not support it, and the caller falls back reporting what actually
# ran — the reader must never be told a method that did not produce the number.
_PROJECTORS = {
    ForecastMethod.DAMPED_TREND: _project_damped,
    ForecastMethod.LINEAR: _project_linear,
    ForecastMethod.MOVING_AVERAGE: _project_moving_average,
}
def project(
    prices: List[PriceRecord],
    days_ahead: int,
    method: ForecastMethod = ForecastMethod.DAMPED_TREND
) -> Projection:
    '''
        Projects one mineral's quotations forward.

        Args:
            prices (List[PriceRecord]): Observed quotations, any order.
            days_ahead (int): How many days to project.
            method (ForecastMethod): Which projection to apply.

        Returns:
            Projection: The projected points, the method actually used, the
                confidence the sample earns and the change against the last
                observed price. Empty when the history cannot support a
                projection.
    '''
    observed = sorted(
        (record for record in prices if record.price_low is not None),
        key = lambda record: record.date
    )
    confidence = confidence_for(len(observed))
    if confidence is ForecastConfidence.INSUFFICIENT or days_ahead < 1:
        return Projection([], method, confidence, None)

    values = [float(record.price_low) for record in observed]
    used_method = method if method in _PROJECTORS else ForecastMethod.DAMPED_TREND
    projected = _PROJECTORS.get(method, _project_damped)(values, days_ahead)

    if projected is None:
        # The fitted line collapses inside the horizon: fall back to the level
        # of the recent days, which cannot invent a slope it does not have, and
        # report the method that actually produced the number.
        used_method = ForecastMethod.MOVING_AVERAGE
        projected = _project_moving_average(values, days_ahead)
        error_msg = (
            f'{method.value} projection produced nothing over {len(observed)} '
            f'observations; fell back to {used_method.value}.'
        )
        logger.warning(error_msg)

    last_price = values[-1]
    change = (
        round((projected[-1] - last_price) / last_price * 100, 2)
        if last_price else None
    )

    message = (
        f'Projected {days_ahead} day(s) with {used_method.value} over '
        f'{len(observed)} observations; confidence {confidence.value}.'
    )
    logger.info(message)
    dates = _future_dates(observed[-1].date, days_ahead)
    return Projection(list(zip(dates, projected)), used_method, confidence, change)


# The official quotation is published with two decimals, so that is the figure
# the service returns: rounding it later, in the browser, would let the API and
# the bulletin disagree on the number a sale is settled at.
_OFFICIAL_QUANTUM: Decimal = Decimal('0.01')


def _official_round(value: float) -> float:
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


def _next_biweekly_period(year: int, month: int, half: int) -> Tuple[int, int, int]:
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


def _period_of(day: date_type) -> Tuple[int, int, int]:
    '''
    Returns the biweekly period a date falls into.

    Args:
        day (date): Any calendar date.

    Returns:
        Tuple[int, int, int]: Its (year, month, half).
    '''
    return day.year, day.month, 1 if day.day <= 15 else 2


def _official_average(
    window: Tuple[date_type, date_type],
    observed: Dict[date_type, float],
    projected: Dict[date_type, float]
) -> Optional[Dict[str, Any]]:
    '''
    Averages one biweekly window, using observations first and the projection
    only for the days still to come.

    Quotations are published on working days — of 104 observations in the
    series, 104 fall on weekdays — so the projection is read on weekdays only.
    Averaging over calendar days instead would put a denominator of 15 against a
    real one of 10 and quietly lower every projected official price.

    Args:
        window (tuple[date, date]): Period start and end, inclusive.
        observed (Dict[date, float]): Quotations already published.
        projected (Dict[date, float]): Projected daily values.

    Returns:
        Dict[str, Any] | None: The average and how it was composed, or None
            when no day of the window has a value at all.
    '''
    start, end = window
    values: List[float] = []
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
        'avg_price_low': _official_round(sum(values) / len(values)),
        'sample_size': len(values),
        'observed_days': observed_days,
        'projected_days': projected_days,
        # A window the horizon only half reaches still averages, but the reader
        # has to know the mean is missing days before treating it as the price.
        'is_complete': len(values) >= working_days,
    }


def _validity_of(period: Tuple[int, int, int]) -> Tuple[date_type, date_type]:
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
        Tuple[date, date]: First and last day the average is in force.
    '''
    return _biweekly_period_bounds(*_next_biweekly_period(*period))


def _projected_officials(
    reference: date_type,
    horizon_end: date_type,
    observed: Dict[date_type, float],
    projected: Dict[date_type, float]
) -> List[Dict[str, Any]]:
    '''
    Builds the upcoming official quotations the horizon reaches.

    Starts at the period in course, whose average is part observed and part
    projected — the days already quoted are facts, and mixing them in is what
    makes the first projected official worth reading at all.

    Args:
        reference (date): Today.
        horizon_end (date): Last projected date.
        observed (Dict[date, float]): Quotations already published.
        projected (Dict[date, float]): Projected daily values.

    Returns:
        List[Dict[str, Any]]: One entry per period, chronologically.
    '''
    entries: List[Dict[str, Any]] = []
    period = _period_of(reference)
    while True:
        entry = _official_average(_biweekly_period_bounds(*period), observed, projected)
        if entry is None:
            break
        entry['valid_from'], entry['valid_to'] = _validity_of(period)
        entries.append(entry)
        period = _next_biweekly_period(*period)
        # Stop once the projection no longer reaches the next window.
        if _biweekly_period_bounds(*period)[0] > horizon_end:
            break
    return entries


def _official_history(
    reference: date_type,
    observed: Dict[date_type, float],
    periods: int
) -> List[Dict[str, Any]]:
    '''
    Returns the official quotations already published, newest first.

    The projected price is only worth as much as the reader's ability to check
    it against what actually happened, so the closed fortnights travel with the
    projection instead of forcing a second call to the report endpoint.

    Args:
        reference (date): Today.
        observed (Dict[date, float]): Quotations already published.
        periods (int): How many closed fortnights to walk back.

    Returns:
        List[Dict[str, Any]]: One entry per period that had quotations.
    '''
    entries: List[Dict[str, Any]] = []
    # Two steps back: one lands on the period in force, which already travels
    # as `official_current` and would only repeat itself here.
    period = _prev_biweekly_period(*_prev_biweekly_period(*_period_of(reference)))
    for _ in range(periods):
        entry = _official_average(_biweekly_period_bounds(*period), observed, {})
        if entry is not None:
            entry['valid_from'], entry['valid_to'] = _validity_of(period)
            entries.append(entry)
        period = _prev_biweekly_period(*period)
    return entries


def _official_block(
    mineral_id: Optional[str],
    projection: Projection,
    reference: date_type,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    '''
    Builds the official-quotation view of one mineral.

    Args:
        mineral_id (str | None): Mineral identifier, None when uncatalogued.
        projection (Projection): The daily projection already computed.
        reference (date): Today, which decides which period is in force.
        db (Session | None): Relational session; ignored on DynamoDB.

    Returns:
        Dict[str, Any]: `official_current`, `official_forecast` and the change
            between the price in force and the next one.
    '''
    empty: Dict[str, Any] = {
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
    current_period = _prev_biweekly_period(*_period_of(reference))
    # Read from the oldest fortnight the history shows through the horizon:
    # everything the averages below may need, in a single pass over storage.
    oldest = current_period
    for _ in range(OFFICIAL_HISTORY_PERIODS):
        oldest = _prev_biweekly_period(*oldest)
    read_from = _biweekly_period_bounds(*oldest)[0]
    observed = {
        record.date: record.price_low
        for record in prices_in_window(mineral_id, read_from, horizon_end, db = db)
        if record.price_low is not None
    }

    current = _official_average(
        _biweekly_period_bounds(*current_period), observed, {}
    )
    if current is not None:
        current['valid_from'], current['valid_to'] = _validity_of(current_period)

    forecast = _projected_officials(reference, horizon_end, observed, projected)

    change = None
    if current and forecast and current['avg_price_low']:
        change = round(
            (forecast[0]['avg_price_low'] - current['avg_price_low'])
            / current['avg_price_low'] * 100, 2
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
    db: Session,
    days_ahead: int = 30,
    method: ForecastMethod = ForecastMethod.DAMPED_TREND
) -> Dict[str, Any]:
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

    Returns:
        Dict[str, Any]: Payload matching PriceForecastResponse shape.
    '''
    mineral_ids = _resolve_mineral_id_map(db)
    minerals: List[Dict[str, Any]] = []
    observed_dates: List[date_type] = []
    # One reference for every mineral, so the whole payload agrees on which
    # fortnight is in force even if the request straddles midnight.
    reference = get_current_time_gmt().date()

    for catalog in OFFICIAL_MINERALS:
        mineral_id = mineral_ids.get(_normalize_name(catalog['name']))
        history = (
            prices_in_window(mineral_id, _HISTORY_FLOOR, date_type.max, db = db)
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
                reference = reference
            ),
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
    catalog: Dict[str, str]
    history: List[PriceRecord]
    days_ahead: int
    method: ForecastMethod
    mineral_id: Optional[str] = None
    reference: Optional[date_type] = None


def _forecast_row(
    request: ForecastRequest,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    '''
    Builds one mineral's entry of the forecast payload.

    Args:
        request (ForecastRequest): Catalogue entry, history and horizon.
        db (Session | None): Relational session; ignored on DynamoDB.

    Returns:
        Dict[str, Any]: The mineral's row, daily projection and official
            quotation included.
    '''
    catalog, history = request.catalog, request.history
    days_ahead, method = request.days_ahead, request.method
    result = project(history, days_ahead, method)
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
        'mean_absolute_error': _backtest(
            [record.price_low for record in priced], days_ahead
        ) if len(priced) > 1 else None,
        'baseline_error': _backtest(
            [record.price_low for record in priced], days_ahead, naive = True
        ) if len(priced) > 1 else None,
        'history': [
            {'date': record.date, 'price': record.price_low} for record in priced
        ],
        'forecast': [
            {'date': day, 'price': round(price, 4)} for day, price in result.points
        ],
        **_official_block(
            request.mineral_id,
            result,
            request.reference or get_current_time_gmt().date(),
            db = db
        ),
    }
