'''
    The bench of projection models.

    One place, one signature: every model takes the observed series and how many
    steps to project, and returns that many values. Nothing else. That is what
    lets the service run all of them over the same data and compare them without
    knowing what any of them does.

    Which models are here is a judgement about the data, not about ambition. The
    exchange-rate series is short — it starts at the float regime — and short
    series punish complex models: they have too many parameters to estimate from
    too few points, and end up fitting noise. So the bench holds classical
    methods that estimate two or three parameters at most, plus the naive
    forecast, which in exchange rates is the benchmark nobody beats easily.

    Deliberately absent: ARIMA and its seasonal variants. With seventy
    observations there is not enough to identify their orders, and a model
    presented as sophisticated while performing worse than "tomorrow is the same
    as today" is a liability in front of a client. When the series is long
    enough to estimate them, they belong here.
'''
from typing import Callable, Dict, List

import numpy as np

from services.environment import load_and_validate_env_vars


ENV_VARS = load_and_validate_env_vars({
    'RATE_HOLT_ALPHA': float,
    'RATE_HOLT_BETA': float,
    'RATE_HOLT_PHI': float,
    'RATE_SES_ALPHA': float,
    'RATE_MOVING_AVERAGE_WINDOW': int,
    'RATE_THETA_ALPHA': float,
})

# Holt smoothing: level, trend and damping. Fitted by minimising the backtest
# error over the stored series.
ALPHA = ENV_VARS['RATE_HOLT_ALPHA']
BETA = ENV_VARS['RATE_HOLT_BETA']
PHI = ENV_VARS['RATE_HOLT_PHI']

# Simple exponential smoothing: no trend, level only.
SES_ALPHA = ENV_VARS['RATE_SES_ALPHA']

# Window of the moving average.
MOVING_WINDOW = ENV_VARS['RATE_MOVING_AVERAGE_WINDOW']

# Smoothing of the theta line.
THETA_ALPHA = ENV_VARS['RATE_THETA_ALPHA']


def naive(
    values: List[float],
    days_ahead: int
) -> List[float]:
    '''
        Repeats the last observation.

        It is the rival to beat, not a filler: on exchange rates, at short
        horizons, almost no model beats it consistently. A projection that does
        not clear it is not earning its place.

        Args:
            values (List[float]): Observed series, oldest first.
            days_ahead (int): Steps to project.

        Returns:
            List[float]: Projected values.
    '''
    return [float(values[-1])] * days_ahead


def mean(
    values: List[float],
    days_ahead: int
) -> List[float]:
    '''
        Repeats the mean of the whole series.

        It works as a contrast: if it beats the others, the series has no trend
        and any projection with a slope is reading noise.

        Args:
            values (List[float]): Observed series.
            days_ahead (int): Steps to project.

        Returns:
            List[float]: Projected values.
    '''
    return [float(np.mean(values))] * days_ahead


def drift(
    values: List[float],
    days_ahead: int
) -> List[float]:
    '''
        Random walk with drift: extends the slope between the first and the
        last point.

        Args:
            values (List[float]): Observed series.
            days_ahead (int): Steps to project.

        Returns:
            List[float]: Projected values.
    '''
    if len(values) < 2:
        return naive(values, days_ahead)
    slope = (values[-1] - values[0]) / (len(values) - 1)
    return [float(values[-1] + slope * step) for step in range(1, days_ahead + 1)]


def linear(
    values: List[float],
    days_ahead: int
) -> List[float]:
    '''
        Least-squares straight line over the whole series.

        It is here so it can be shown losing: it was the default model until
        the backtest showed it erred twice as much as the damped trend, because
        it extrapolates forever a slope the market does not respect.

        Args:
            values (List[float]): Observed series.
            days_ahead (int): Steps to project.

        Returns:
            List[float]: Projected values.
    '''
    if len(values) < 2:
        return naive(values, days_ahead)
    positions = np.arange(len(values), dtype = float)
    slope, intercept = np.polyfit(positions, np.array(values, dtype = float), 1)
    future = np.arange(len(values), len(values) + days_ahead, dtype = float)
    return [float(value) for value in slope * future + intercept]


def moving_average(
    values: List[float],
    days_ahead: int
) -> List[float]:
    '''
        Repite el promedio de los últimos días.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.

        Returns:
            List[float]: Valores proyectados.
    '''
    window = values[-MOVING_WINDOW:] if len(values) >= MOVING_WINDOW else values
    return [float(np.mean(window))] * days_ahead


def simple_exponential(
    values: List[float],
    days_ahead: int
) -> List[float]:
    '''
        Suavizado exponencial simple: nivel que sigue a la serie, sin tendencia.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.

        Returns:
            List[float]: Valores proyectados.
    '''
    level = values[0]
    for value in values[1:]:
        level = SES_ALPHA * value + (1 - SES_ALPHA) * level
    return [float(level)] * days_ahead


def holt(
    values: List[float],
    days_ahead: int
) -> List[float]:
    '''
        Holt smoothing with a linear trend, undamped.

        The direct contrast to the damped trend: same mechanics, but the trend
        never fades. On a series that flattens this one overshoots and the other
        does not; seeing them together shows how much the damping is worth.

        Args:
            values (List[float]): Observed series.
            days_ahead (int): Steps to project.

        Returns:
            List[float]: Projected values.
    '''
    return _holt(values, days_ahead, phi = 1.0)


def damped_trend(
    values: List[float],
    days_ahead: int
) -> List[float]:
    '''
        Holt smoothing with a damped trend.

        The level follows the latest observations and the trend FADES: every
        day further out inherits less of the recent drift. That is what keeps
        the projection from running away, and why this is the default model.

        Args:
            values (List[float]): Observed series.
            days_ahead (int): Steps to project.

        Returns:
            List[float]: Projected values.
    '''
    return _holt(values, days_ahead, phi = PHI)


def _holt(
    values: List[float],
    days_ahead: int,
    phi: float
) -> List[float]:
    '''
        Mecánica común de Holt, con y sin amortiguación.

        Args:
            values (List[float]): Serie observada.
            days_ahead (int): Pasos a proyectar.
            phi (float): Factor de amortiguación; 1.0 la desactiva.

        Returns:
            List[float]: Valores proyectados.
    '''
    if len(values) < 2:
        return naive(values, days_ahead)

    level, trend = values[0], values[1] - values[0]
    for value in values[1:]:
        previous = level
        level = ALPHA * value + (1 - ALPHA) * (level + phi * trend)
        trend = BETA * (level - previous) + (1 - BETA) * phi * trend

    damping = np.cumsum(phi ** np.arange(1, days_ahead + 1))
    return [float(value) for value in level + damping * trend]


def theta(
    values: List[float],
    days_ahead: int
) -> List[float]:
    '''
        Theta method: averages a long-term straight line with a smoothing that
        follows the recent movements.

        It won the M3 competition and is still hard to beat on short series,
        which is exactly the case here. The idea is simple: half the answer
        comes from the underlying trend and half from the current level, so it
        neither ignores the direction nor extrapolates it without a brake.

        Args:
            values (List[float]): Observed series.
            days_ahead (int): Steps to project.

        Returns:
            List[float]: Projected values.
    '''
    if len(values) < 3:
        return naive(values, days_ahead)

    # Theta-zero line: the regression straight line, extended.
    straight = linear(values, days_ahead)

    # Theta-two line: exponential smoothing over the series, which puts the
    # weight on what is recent.
    level = values[0]
    for value in values[1:]:
        level = THETA_ALPHA * value + (1 - THETA_ALPHA) * level
    smoothed = [float(level)] * days_ahead

    return [(one + two) / 2 for one, two in zip(straight, smoothed)]


# The registry is the contract: adding a model is adding an entry, and
# everything that compares, measures and publishes walks it without knowing
# any model in particular.
MODELS: Dict[str, Callable[[List[float], int], List[float]]] = {
    'NAIVE': naive,
    'MEAN': mean,
    'DRIFT': drift,
    'LINEAR': linear,
    'MOVING_AVERAGE': moving_average,
    'SIMPLE_EXPONENTIAL': simple_exponential,
    'HOLT': holt,
    'DAMPED_TREND': damped_trend,
    'THETA': theta,
}
