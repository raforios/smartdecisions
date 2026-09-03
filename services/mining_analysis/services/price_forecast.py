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
    _normalize_name,
    _resolve_mineral_id_map
)
from services.prices_store import PriceRecord, prices_in_window
from services.utils import handle_service_errors


ENV_VARS = load_and_validate_env_vars({}, optional_env_vars = {
    'FORECAST_MIN_DAYS': int,
    'FORECAST_HIGH_CONFIDENCE_DAYS': int,
    'FORECAST_MEDIUM_CONFIDENCE_DAYS': int,
    'FORECAST_MOVING_AVERAGE_WINDOW': int,
    'FORECAST_HISTORY_POINTS': int,
})

# Below this, a projection says more about the noise than about the mineral.
MIN_DAYS = ENV_VARS['FORECAST_MIN_DAYS'] or 10
# Thresholds for how much weight the projection deserves.
HIGH_CONFIDENCE_DAYS = ENV_VARS['FORECAST_HIGH_CONFIDENCE_DAYS'] or 60
MEDIUM_CONFIDENCE_DAYS = ENV_VARS['FORECAST_MEDIUM_CONFIDENCE_DAYS'] or 30
# Days averaged by the moving-average method.
MOVING_AVERAGE_WINDOW = ENV_VARS['FORECAST_MOVING_AVERAGE_WINDOW'] or 7

# A linear projection that drops to this fraction of the lowest observed price
# has stopped describing the mineral and started describing the fitted line.
# Wolfram, with three weeks of steeply falling quotations, reached zero inside a
# 30-day horizon: the arithmetic was right and the answer was nonsense.
_COLLAPSE_FLOOR_RATIO: float = 0.25

# How many observed points travel back with each mineral. The UI draws the
# trend behind the projection; a couple of hundred points is plenty for that
# and keeps the payload from growing with the archive.
HISTORY_POINTS = ENV_VARS['FORECAST_HISTORY_POINTS'] or 180

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


def project(
    prices: List[PriceRecord],
    days_ahead: int,
    method: ForecastMethod = ForecastMethod.LINEAR
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
    used_method = method
    projected = (
        _project_moving_average(values, days_ahead)
        if method is ForecastMethod.MOVING_AVERAGE
        else _project_linear(values, days_ahead)
    )

    if projected is None:
        # The fitted line collapses inside the horizon: fall back to the level
        # of the recent days, which cannot invent a slope it does not have, and
        # report the method that actually produced the number.
        used_method = ForecastMethod.MOVING_AVERAGE
        projected = _project_moving_average(values, days_ahead)
        error_msg = (
            f'Linear projection collapsed over {len(observed)} observations; '
            f'fell back to {used_method.value}.'
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


@handle_service_errors('MINING_ANALYSIS')
async def get_price_forecast_service(
    db: Session,
    days_ahead: int = 30,
    method: ForecastMethod = ForecastMethod.LINEAR
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

    for catalog in OFFICIAL_MINERALS:
        mineral_id = mineral_ids.get(_normalize_name(catalog['name']))
        history = (
            prices_in_window(mineral_id, _HISTORY_FLOOR, date_type.max, db = db)
            if mineral_id is not None else []
        )
        observed_dates.extend(record.date for record in history)
        minerals.append(
            _forecast_row(catalog, history[-HISTORY_POINTS:], days_ahead, method)
        )

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


def _forecast_row(
    catalog: Dict[str, str],
    history: List[PriceRecord],
    days_ahead: int,
    method: ForecastMethod
) -> Dict[str, Any]:
    '''
    Builds one mineral's entry of the forecast payload.

    Args:
        catalog (Dict[str, str]): Entry of OFFICIAL_MINERALS.
        history (List[PriceRecord]): Observed quotations to fit on.
        days_ahead (int): How many days to project.
        method (ForecastMethod): Requested projection method.

    Returns:
        Dict[str, Any]: The mineral's row, projection included.
    '''
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
        'history': [
            {'date': record.date, 'price': record.price_low} for record in priced
        ],
        'forecast': [
            {'date': day, 'price': round(price, 4)} for day, price in result.points
        ],
    }
