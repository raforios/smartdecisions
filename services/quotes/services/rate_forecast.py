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
from typing import Any

import numpy as np

from models.quotes import ExchangeRateItem
from schemas.quotes import RateConfidence
from services.environment import load_and_validate_env_vars
from services.forecast_models import MODELS, damped_trend
from services.logger_config import custom_logger as logger


# Required, not optional: a fallback in code is still a number living in
# code. Missing configuration must fail loudly at startup.
ENV_VARS = load_and_validate_env_vars({
    'RATE_FORECAST_MIN_DAYS': int,
    'RATE_FORECAST_HIGH_CONFIDENCE_DAYS': int,
    'RATE_FORECAST_MEDIUM_CONFIDENCE_DAYS': int,
    'RATE_HOLT_ALPHA': float,
    'RATE_HOLT_BETA': float,
    'RATE_HOLT_PHI': float,
    'BACKTEST_MIN_TRAIN': int,
    'BACKTEST_MIN_WINDOWS': int,
    'RATE_COLLAPSE_FLOOR_RATIO': float,
    'ERROR_DECIMALS': int,
    'CHANGE_DECIMALS': int,
    'RATE_DECIMALS': int,
})

# Smoothing parameters, chosen by minimising the backtest error over the stored
# series (grid search on 7/15/30-day horizons). They are configurable because
# they are a property of the data, not of the code: as the series grows they
# should be refitted, and that must not need a release.
ALPHA = ENV_VARS['RATE_HOLT_ALPHA']
BETA = ENV_VARS['RATE_HOLT_BETA']
PHI = ENV_VARS['RATE_HOLT_PHI']

# Backtest bounds: how much history each replay needs before forecasting, and
# how many replays make a mean worth publishing.
BACKTEST_MIN_TRAIN = ENV_VARS['BACKTEST_MIN_TRAIN']
BACKTEST_MIN_WINDOWS = ENV_VARS['BACKTEST_MIN_WINDOWS']

# Below this the projection describes the noise, not the currency.
MIN_DAYS = ENV_VARS['RATE_FORECAST_MIN_DAYS']
HIGH_CONFIDENCE_DAYS = ENV_VARS['RATE_FORECAST_HIGH_CONFIDENCE_DAYS']
MEDIUM_CONFIDENCE_DAYS = ENV_VARS['RATE_FORECAST_MEDIUM_CONFIDENCE_DAYS']

# A rate projected below this fraction of the lowest observed value is not a
# forecast, it is the model leaving the data behind. What counts as "too far
# below" is a judgement about the currency, so it is configured.
_COLLAPSE_FLOOR_RATIO: float = ENV_VARS['RATE_COLLAPSE_FLOOR_RATIO']

# Decimals a published error, a published percentage and a published rate
# carry. The rate shares its setting with the rest of the service: the bench
# and the live forecast must not disagree on how precise a rate is.
ERROR_DECIMALS = ENV_VARS['ERROR_DECIMALS']
CHANGE_DECIMALS = ENV_VARS['CHANGE_DECIMALS']
RATE_DECIMALS = ENV_VARS['RATE_DECIMALS']


@dataclass(frozen = True)
class RateProjection:
    '''
        The outcome of projecting the exchange rate.

        `points` is empty when the history cannot support a projection; the
        confidence says why, so the caller never has to guess whether an empty
        series means "no data" or "no answer".
    '''
    points: list[tuple[date_type, float]]
    confidence: RateConfidence
    change_percent: float | None
    expected_error: float | None = None
    baseline_error: float | None = None

    @property
    def final_rate(self) -> float | None:
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


def backtest_windows(
    values: list[float],
    days_ahead: int
) -> int:
    '''
        How many replays a series affords at a horizon.

        Args:
            values (list[float]): Observed series.
            days_ahead (int): Horizon.

        Returns:
            int: Number of windows the backtest averages over.
    '''
    return max(0, len(values) - days_ahead + 1 - BACKTEST_MIN_TRAIN)


def backtest_error(
    values: list[float],
    days_ahead: int
) -> float | None:
    '''
        Measures how far this model has missed, on this very series.

        The number published next to a projection has to come from somewhere. It
        is not an assumed confidence interval: the series is replayed from every
        starting point that leaves room for the horizon, the model projects from
        each, and this is the mean absolute error of those attempts.

        Args:
            values (list[float]): Observed series, oldest first.
            days_ahead (int): Horizon to measure.

        Returns:
            float | None: Mean absolute error in the unit of the series, or None
                when the history leaves too few windows to measure anything.
    '''
    errors: list[float] = []
    for cut in range(BACKTEST_MIN_TRAIN, len(values) - days_ahead + 1):
        forecast = damped_trend(values[:cut], days_ahead)
        actual = values[cut:cut + days_ahead]
        errors.append(float(np.mean(np.abs(np.array(forecast) - np.array(actual)))))

    if len(errors) < BACKTEST_MIN_WINDOWS:
        return None
    return round(float(np.mean(errors)), ERROR_DECIMALS)


def baseline_error(
    values: list[float],
    days_ahead: int
) -> float | None:
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
            values (list[float]): Observed series, oldest first.
            days_ahead (int): Horizon to measure.

        Returns:
            float | None: Mean absolute error of the naive forecast, or None
                when there are too few windows.
    '''
    errors: list[float] = []
    for cut in range(BACKTEST_MIN_TRAIN, len(values) - days_ahead + 1):
        actual = np.array(values[cut:cut + days_ahead])
        errors.append(float(np.mean(np.abs(actual - values[cut - 1]))))

    if len(errors) < BACKTEST_MIN_WINDOWS:
        return None
    return round(float(np.mean(errors)), ERROR_DECIMALS)


def error_of(
    model: str,
    values: list[float],
    days_ahead: int
) -> float | None:
    '''
        Measures how much a model has erred over this very series.

        It is not an assumed confidence interval: the series is re-run from
        every starting point that leaves room for the horizon, the model
        projects from there and the absolute misses are averaged. It is the one
        measure that cannot be dressed up.

        Args:
            model (str): Name of the model in the registry.
            values (list[float]): Observed series.
            days_ahead (int): Horizon to measure.

        Returns:
            float | None: Mean absolute error, or None with too few windows.
    '''
    projector = MODELS.get(model)
    if projector is None:
        return None

    errors: list[float] = []
    for cut in range(BACKTEST_MIN_TRAIN, len(values) - days_ahead + 1):
        forecast = np.array(projector(values[:cut], days_ahead))
        actual = np.array(values[cut:cut + days_ahead])
        errors.append(float(np.mean(np.abs(forecast - actual))))

    if len(errors) < BACKTEST_MIN_WINDOWS:
        return None
    return round(float(np.mean(errors)), ERROR_DECIMALS)


def run_bench(
    rates: list[ExchangeRateItem],
    days_ahead: int,
    models: list[str]
) -> list[dict[str, Any]]:
    '''
        Runs several models over the same series and returns them measured.

        It exists so they can be seen together, which answers a better question
        than any of them alone: HOW MUCH THE ANSWER DEPENDS ON THE MODEL. Where
        the projections agree the figure belongs to the business; where they
        separate, to the model, and that is where to distrust it.

        They come ordered by their measured error, best to worst. That exposes
        all of them, the default one included when it loses — which is
        precisely what has to be visible.

        Args:
            rates (list[ExchangeRateItem]): Observed quotes.
            days_ahead (int): Days to project.
            models (list[str]): Models to run; unknown ones are ignored.

        Returns:
            list[dict[str, Any]]: One block per model, best first.
    '''
    observed = sorted(rates, key = lambda item: item.date)
    values = [float(item.official_rate) for item in observed]
    dates = [
        observed[-1].date + timedelta(days = offset)
        for offset in range(1, days_ahead + 1)
    ]
    last_rate = values[-1]

    results: list[dict[str, Any]] = []
    for name in models:
        projector = MODELS.get(name)
        if projector is None:
            continue
        projected = projector(values, days_ahead)
        change = (
            round((projected[-1] - last_rate) / last_rate * 100, CHANGE_DECIMALS)
            if last_rate else None
        )
        results.append({
            'model': name,
            'change_percent': change,
            'final_rate': round(projected[-1], RATE_DECIMALS),
            'mean_absolute_error': error_of(name, values, days_ahead),
            'projected': [
                {'date': day, 'rate': round(value, RATE_DECIMALS)}
                for day, value in zip(dates, projected)
            ],
        })

    # The ones that could not be measured go last: a model with no known error
    # cannot present itself as the best.
    results.sort(key = lambda item: (
        item['mean_absolute_error'] is None,
        item['mean_absolute_error'] or 0.0
    ))
    return results


def project(
    rates: list[ExchangeRateItem],
    days_ahead: int
) -> RateProjection:
    '''
        Projects the exchange rate forward from the stored history.

        Args:
            rates (list[ExchangeRateItem]): Observed rates, any order.
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
    change = (
        round((projected[-1] - last_rate) / last_rate * 100, CHANGE_DECIMALS)
        if last_rate else None
    )
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
