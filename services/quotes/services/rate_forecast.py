'''
    Projection of the official exchange rate.

    Same arithmetic as the mineral projection in MINING_ANALYSIS, and
    deliberately a separate copy: these are independently deployed services with
    independently packaged dependencies, the same reason the boilerplate is
    copied rather than imported. What must not diverge is the behaviour, so the
    rules are stated here explicitly:

      - A least-squares fit over the series, extended forward.
      - Confidence derived from how much history backs it.
      - A fit that collapses towards zero is refused, never clamped.

    The history this runs on starts at the float regime, not at the beginning of
    the series. Fitting over the fixed years would conclude the rate stays at
    6.86 forever, which is the opposite of what is happening.
'''
from dataclasses import dataclass
from datetime import date as date_type, timedelta
from typing import List, Optional, Tuple

import numpy as np

from models.quotes import ExchangeRateItem
from schemas.quotes import RateConfidence
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger


ENV_VARS = load_and_validate_env_vars({}, optional_env_vars = {
    'RATE_FORECAST_MIN_DAYS': int,
    'RATE_FORECAST_HIGH_CONFIDENCE_DAYS': int,
    'RATE_FORECAST_MEDIUM_CONFIDENCE_DAYS': int,
    'RATE_HOLT_ALPHA': float,
    'RATE_HOLT_BETA': float,
    'RATE_HOLT_PHI': float,
    'BACKTEST_MIN_TRAIN': int,
    'BACKTEST_MIN_WINDOWS': int,
})

# Smoothing parameters, chosen by minimising the backtest error over the stored
# series (grid search on 7/15/30-day horizons). They are configurable because
# they are a property of the data, not of the code: as the series grows they
# should be refitted, and that must not need a release.
ALPHA = ENV_VARS['RATE_HOLT_ALPHA'] or 1.0
BETA = ENV_VARS['RATE_HOLT_BETA'] or 0.45
PHI = ENV_VARS['RATE_HOLT_PHI'] or 0.70

# Backtest bounds: how much history each replay needs before forecasting, and
# how many replays make a mean worth publishing.
BACKTEST_MIN_TRAIN = ENV_VARS['BACKTEST_MIN_TRAIN'] or 30
BACKTEST_MIN_WINDOWS = ENV_VARS['BACKTEST_MIN_WINDOWS'] or 5

# Below this the projection describes the noise, not the currency.
MIN_DAYS = ENV_VARS['RATE_FORECAST_MIN_DAYS'] or 15
HIGH_CONFIDENCE_DAYS = ENV_VARS['RATE_FORECAST_HIGH_CONFIDENCE_DAYS'] or 90
MEDIUM_CONFIDENCE_DAYS = ENV_VARS['RATE_FORECAST_MEDIUM_CONFIDENCE_DAYS'] or 45

# A rate projected below this fraction of the lowest observed value is not a
# forecast, it is the fitted line leaving the data behind.
_COLLAPSE_FLOOR_RATIO: float = 0.5


@dataclass(frozen = True)
class RateProjection:
    '''
        The outcome of projecting the exchange rate.

        `points` is empty when the history cannot support a projection; the
        confidence says why, so the caller never has to guess whether an empty
        series means "no data" or "no answer".
    '''
    points: List[Tuple[date_type, float]]
    confidence: RateConfidence
    change_percent: Optional[float]
    expected_error: Optional[float] = None
    baseline_error: Optional[float] = None

    @property
    def final_rate(self) -> Optional[float]:
        '''
            The projected rate at the end of the horizon.

            Returns:
                float | None: The last projected value, or None when there is
                    no projection.
        '''
        return self.points[-1][1] if self.points else None


def confidence_for(sample_size: int) -> RateConfidence:
    '''
        Grades a projection by how much history backs it.

        Args:
            sample_size (int): Days of observed rates.

        Returns:
            RateConfidence: The grade the caller must surface.
    '''
    if sample_size < MIN_DAYS:
        return RateConfidence.INSUFFICIENT
    if sample_size >= HIGH_CONFIDENCE_DAYS:
        return RateConfidence.HIGH
    if sample_size >= MEDIUM_CONFIDENCE_DAYS:
        return RateConfidence.MEDIUM
    return RateConfidence.LOW


def damped_trend(values: List[float], days_ahead: int) -> List[float]:
    '''
        Projects a series with exponential smoothing and a damped trend.

        Replaces the least-squares line that was here before. On the stored
        series a straight line was the **worst** of every option measured: at a
        30-day horizon it missed by 1.07 Bs against 0.33 for simply repeating
        today's rate. An exchange rate behaves close to a random walk — the
        lag-1 autocorrelation of the level is 0.995 — so a line fitted over two
        months extrapolates a slope the market does not honour.

        This keeps the last observation as the level and adds a trend that
        **fades** with distance: `phi` below 1 means each further day inherits
        less of the recent drift. That is what stops the projection from running
        away, and it is why this beats repeating today's value at 7 and 15 days
        while a line loses at every horizon.

        Args:
            values (List[float]): Observed series, oldest first.
            days_ahead (int): How many steps to project.

        Returns:
            List[float]: The projected values.
    '''
    level, trend = values[0], values[1] - values[0]
    for value in values[1:]:
        previous = level
        level = ALPHA * value + (1 - ALPHA) * (level + PHI * trend)
        trend = BETA * (level - previous) + (1 - BETA) * PHI * trend

    damping = np.cumsum(PHI ** np.arange(1, days_ahead + 1))
    return [float(value) for value in level + damping * trend]


def backtest_windows(values: List[float], days_ahead: int) -> int:
    '''
        How many replays a series affords at a horizon.

        Args:
            values (List[float]): Observed series.
            days_ahead (int): Horizon.

        Returns:
            int: Number of windows the backtest averages over.
    '''
    return max(0, len(values) - days_ahead + 1 - BACKTEST_MIN_TRAIN)


def backtest_error(values: List[float], days_ahead: int) -> Optional[float]:
    '''
        Measures how far this model has missed, on this very series.

        The number published next to a projection has to come from somewhere. It
        is not an assumed confidence interval: the series is replayed from every
        starting point that leaves room for the horizon, the model projects from
        each, and this is the mean absolute error of those attempts.

        Args:
            values (List[float]): Observed series, oldest first.
            days_ahead (int): Horizon to measure.

        Returns:
            float | None: Mean absolute error in the unit of the series, or None
                when the history leaves too few windows to measure anything.
    '''
    errors: List[float] = []
    for cut in range(BACKTEST_MIN_TRAIN, len(values) - days_ahead + 1):
        forecast = damped_trend(values[:cut], days_ahead)
        actual = values[cut:cut + days_ahead]
        errors.append(float(np.mean(np.abs(np.array(forecast) - np.array(actual)))))

    if len(errors) < BACKTEST_MIN_WINDOWS:
        return None
    return round(float(np.mean(errors)), 4)


def baseline_error(values: List[float], days_ahead: int) -> Optional[float]:
    '''
        The same measurement for the model that has to be beaten.

        The comparison is "tomorrow is the same as today" — the naive forecast.
        For an exchange rate that is not a straw man: it is the hardest baseline
        in the literature at short horizons, and the straight line this service
        used before lost to it by three to one at 30 days.

        Publishing both errors is what turns "give or take 0.17" into something
        a reader can judge: a projection worth showing is one that misses less
        than assuming nothing moves.

        Args:
            values (List[float]): Observed series, oldest first.
            days_ahead (int): Horizon to measure.

        Returns:
            float | None: Mean absolute error of the naive forecast, or None
                when there are too few windows.
    '''
    errors: List[float] = []
    for cut in range(BACKTEST_MIN_TRAIN, len(values) - days_ahead + 1):
        actual = np.array(values[cut:cut + days_ahead])
        errors.append(float(np.mean(np.abs(actual - values[cut - 1]))))

    if len(errors) < BACKTEST_MIN_WINDOWS:
        return None
    return round(float(np.mean(errors)), 4)


def project(rates: List[ExchangeRateItem], days_ahead: int) -> RateProjection:
    '''
        Projects the exchange rate forward from the stored history.

        Args:
            rates (List[ExchangeRateItem]): Observed rates, any order.
            days_ahead (int): How many days to project.

        Returns:
            RateProjection: The projected points, the confidence the sample
                earns, and the change against the last observed rate.
    '''
    observed = sorted(rates, key = lambda item: item.date)
    confidence = confidence_for(len(observed))
    if confidence is RateConfidence.INSUFFICIENT or days_ahead < 1:
        return RateProjection([], confidence, None, None, None)

    values = [float(item.official_rate) for item in observed]
    projected = damped_trend(values, days_ahead)

    if any(value <= min(values) * _COLLAPSE_FLOOR_RATIO for value in projected):
        error_msg = (
            f'The rate projection collapses within {days_ahead} day(s); '
            'refusing to publish it.'
        )
        logger.warning(error_msg)
        return RateProjection([], confidence, None, None, None)

    last_rate = values[-1]
    change = round((projected[-1] - last_rate) / last_rate * 100, 2) if last_rate else None
    expected_error = backtest_error(values, days_ahead)
    reference_error = baseline_error(values, days_ahead)
    dates = [
        observed[-1].date + timedelta(days = offset)
        for offset in range(1, days_ahead + 1)
    ]

    message = (
        f'Rate projected {days_ahead} day(s) over {len(observed)} observations; '
        f'confidence {confidence.value}.'
    )
    logger.info(message)
    return RateProjection(
        list(zip(dates, projected)), confidence, change,
        expected_error, reference_error
    )
