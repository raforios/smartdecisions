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
})

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
        return RateProjection([], confidence, None)

    values = [float(item.official_rate) for item in observed]
    positions = np.arange(len(values), dtype = float)
    slope, intercept = np.polyfit(positions, np.array(values, dtype = float), 1)
    future = np.arange(len(values), len(values) + days_ahead, dtype = float)
    projected = [float(value) for value in slope * future + intercept]

    if any(value <= min(values) * _COLLAPSE_FLOOR_RATIO for value in projected):
        error_msg = (
            f'The rate projection collapses within {days_ahead} day(s); '
            'refusing to publish it.'
        )
        logger.warning(error_msg)
        return RateProjection([], confidence, None)

    last_rate = values[-1]
    change = round((projected[-1] - last_rate) / last_rate * 100, 2) if last_rate else None
    dates = [
        observed[-1].date + timedelta(days = offset)
        for offset in range(1, days_ahead + 1)
    ]

    message = (
        f'Rate projected {days_ahead} day(s) over {len(observed)} observations; '
        f'confidence {confidence.value}.'
    )
    logger.info(message)
    return RateProjection(list(zip(dates, projected)), confidence, change)
