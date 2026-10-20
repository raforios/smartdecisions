'''
    Projection of a series: the shared calculation every service asks for by
    HTTP instead of keeping its own copy (Rafael, 17-oct-2026: ML_FUNCTIONS is
    the base service of calculations, formulas, predictions, projections and
    classifications).

    Pure Python and free of the environment: the CI runs this service's tests
    with no .env, and every function here is tested there.

    Three candidates, and the series decides (Rafael, 19-oct-2026):
      - NAIVE: the next value is the same as the last one.
      - DAMPED_TREND: Holt's linear trend with damping; the level and the trend
        follow the series and the trend fades step by step.
      - HOLT_WINTERS: the same damped trend plus an additive seasonal pattern,
        when the caller says the series has seasons and there is more than one.

    The parameters of each model are fitted to the series itself, never sent by
    the caller: fixed values projected a seasonal series worse than the naive
    guess. Each candidate is measured out of sample —every tested point is
    predicted by a model fitted only on the points before it— and the one with
    the lowest error wins. A model has to beat the naive guess to be used.
'''
from dataclasses import dataclass
from itertools import product

NAIVE = 'NAIVE'
DAMPED_TREND = 'DAMPED_TREND'
HOLT_WINTERS = 'HOLT_WINTERS'

# The values the fit searches. They belong to the method, not to the business:
# the series picks among them, so no caller has to know they exist.
LEVEL_WEIGHTS = (0.1, 0.3, 0.5, 0.7, 0.9)
TREND_WEIGHTS = (0.05, 0.1, 0.2, 0.4)
DAMPINGS = (0.8, 0.9, 0.98)
SEASON_WEIGHTS = (0.1, 0.3, 0.5)


@dataclass(frozen = True)
class Projection:
    '''
        What the service answers: the model used, its projection and how it
        did on the series next to the naive guess.
    '''
    model: str
    forecast: list[float]
    error_percent: float | None
    naive_error_percent: float | None
    tested_points: int


def damped_trend(
    values: list[float],
    horizon: int,
    smoothing: tuple[float, float, float]
) -> list[float]:
    '''
        Holt's linear trend with damping.

        Args:
            values (list[float]): The history, oldest first; at least two.
            horizon (int): Steps ahead.
            smoothing (tuple[float, float, float]): alpha (level), beta (trend)
                and phi (damping; 1 turns it off).

        Returns:
            list[float]: The projected steps.
    '''
    alpha, beta, phi = smoothing
    level, trend = values[0], values[1] - values[0]
    for value in values[1:]:
        previous = level
        level = alpha * value + (1 - alpha) * (level + phi * trend)
        trend = beta * (level - previous) + (1 - beta) * phi * trend
    projected, damping = [], 0.0
    for step in range(1, horizon + 1):
        damping += phi ** step
        projected.append(level + damping * trend)
    return projected


def _damped_trend_error(
    values: list[float],
    smoothing: tuple[float, float, float]
) -> float:
    '''
        Sum of squared one-step errors of the damped trend over the series:
        what the fit minimizes.

        Args:
            values (list[float]): The history, oldest first; at least three.
            smoothing (tuple[float, float, float]): alpha, beta and phi.

        Returns:
            float: The sum of squared errors.
    '''
    alpha, beta, phi = smoothing
    level, trend = values[0], values[1] - values[0]
    total = 0.0
    for index, value in enumerate(values[1:], start = 1):
        # The same path damped_trend follows; the first point only seeds it.
        if index >= 2:
            total += (value - (level + phi * trend)) ** 2
        previous = level
        level = alpha * value + (1 - alpha) * (level + phi * trend)
        trend = beta * (level - previous) + (1 - beta) * phi * trend
    return total


def _seasonal_start(
    values: list[float],
    season: int
) -> tuple[float, float, list[float]]:
    '''
        The starting level, trend and seasonal pattern, from the first season
        (and the second, when there is a whole one).

        Args:
            values (list[float]): The history; at least one season and one point.
            season (int): Points per season (12 for months).

        Returns:
            tuple[float, float, list[float]]: Level, trend and pattern.
    '''
    level = sum(values[:season]) / season
    if len(values) >= 2 * season:
        trend = (sum(values[season:2 * season]) - sum(values[:season])) / season ** 2
    else:
        trend = (values[season] - values[0]) / season
    return level, trend, [value - level for value in values[:season]]


def _holt_winters_run(
    values: list[float],
    smoothing: tuple[float, float, float, float],
    season: int
) -> tuple[float, float, list[float], float]:
    '''
        Runs the additive Holt-Winters with damped trend over the series.

        Args:
            values (list[float]): The history; more than one season.
            smoothing (tuple[float, float, float, float]): alpha (level), beta
                (trend), gamma (season) and phi (damping).
            season (int): Points per season.

        Returns:
            tuple[float, float, list[float], float]: The final level, trend and
                pattern, and the sum of squared one-step errors.
    '''
    alpha, beta, gamma, phi = smoothing
    level, trend, pattern = _seasonal_start(values, season)
    total = 0.0
    for index in range(season, len(values)):
        value, slot = values[index], index % season
        total += (value - (level + phi * trend + pattern[slot])) ** 2
        new_level = alpha * (value - pattern[slot]) + (1 - alpha) * (level + phi * trend)
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        pattern[slot] = gamma * (value - new_level) + (1 - gamma) * pattern[slot]
        level = new_level
    return level, trend, pattern, total


def holt_winters(
    values: list[float],
    horizon: int,
    smoothing: tuple[float, float, float, float],
    season: int
) -> list[float]:
    '''
        Additive Holt-Winters with damped trend.

        Args:
            values (list[float]): The history, oldest first; more than one season.
            horizon (int): Steps ahead.
            smoothing (tuple[float, float, float, float]): alpha, beta, gamma and phi.
            season (int): Points per season.

        Returns:
            list[float]: The projected steps.
    '''
    level, trend, pattern, _ = _holt_winters_run(values, smoothing, season)
    phi = smoothing[3]
    projected, damping = [], 0.0
    for step in range(1, horizon + 1):
        damping += phi ** step
        projected.append(level + damping * trend + pattern[(len(values) + step - 1) % season])
    return projected


def minimum_history(
    model: str,
    season: int | None
) -> int:
    '''
        The fewest points a model needs to be fitted and to predict the next.

        Args:
            model (str): NAIVE, DAMPED_TREND or HOLT_WINTERS.
            season (int | None): Points per season, if the series has seasons.

        Returns:
            int: The minimum length of the history.
    '''
    if model == HOLT_WINTERS:
        return (season or 0) + 2
    return 3 if model == DAMPED_TREND else 1


def fit(
    values: list[float],
    model: str,
    season: int | None
) -> tuple[float, ...]:
    '''
        The parameters of a model that best follow the series: the ones with
        the lowest sum of squared one-step errors.

        Args:
            values (list[float]): The history, long enough for the model.
            model (str): DAMPED_TREND or HOLT_WINTERS.
            season (int | None): Points per season, for HOLT_WINTERS.

        Returns:
            tuple[float, ...]: alpha, beta, phi, or alpha, beta, gamma, phi.
    '''
    if model == HOLT_WINTERS:
        return min(product(LEVEL_WEIGHTS, TREND_WEIGHTS, SEASON_WEIGHTS, DAMPINGS),
                   key = lambda params: _holt_winters_run(values, params, season)[3])
    return min(product(LEVEL_WEIGHTS, TREND_WEIGHTS, DAMPINGS),
               key = lambda params: _damped_trend_error(values, params))


def project(
    values: list[float],
    model: str,
    horizon: int,
    season: int | None
) -> list[float]:
    '''
        Fits a model to the series and projects it.

        Args:
            values (list[float]): The history, long enough for the model.
            model (str): NAIVE, DAMPED_TREND or HOLT_WINTERS.
            horizon (int): Steps ahead.
            season (int | None): Points per season, for HOLT_WINTERS.

        Returns:
            list[float]: The projected steps.
    '''
    if model == NAIVE:
        return [values[-1]] * horizon
    if model == HOLT_WINTERS:
        return holt_winters(values, horizon, fit(values, model, season), season)
    return damped_trend(values, horizon, fit(values, model, season))


def backtest(
    values: list[float],
    model: str,
    season: int | None,
    start: int
) -> float | None:
    '''
        Mean absolute percentage error of a model on the points from `start`,
        each predicted by the model fitted only on the points before it.

        Args:
            values (list[float]): The history, oldest first.
            model (str): NAIVE, DAMPED_TREND or HOLT_WINTERS.
            season (int | None): Points per season, for HOLT_WINTERS.
            start (int): First tested point.

        Returns:
            float | None: The error in percent; None when no point can be tested
                (or every tested value is zero).
    '''
    errors = [abs(project(values[:end], model, 1, season)[0] - values[end]) / abs(values[end])
              for end in range(start, len(values)) if values[end]]
    return 100 * sum(errors) / len(errors) if errors else None


def candidates(
    values: list[float],
    season: int | None,
    points: int
) -> tuple[list[str], int]:
    '''
        The models that can be compared on this series, and the first point
        they are all tested on: the same points for every one, or the
        comparison would not be fair.

        Args:
            values (list[float]): The history.
            season (int | None): Points per season, if the series has seasons.
            points (int): How many of the last points the caller wants tested.

        Returns:
            tuple[list[str], int]: The models (NAIVE always first) and the first
                tested point.
    '''
    models = [NAIVE]
    for model in (DAMPED_TREND, HOLT_WINTERS):
        if model == HOLT_WINTERS and not (season and season > 1):
            continue
        if len(values) > minimum_history(model, season):
            models.append(model)
    start = max([len(values) - points] + [minimum_history(model, season) for model in models])
    return models, start


def choose_and_project(
    values: list[float],
    horizon: int,
    season: int | None,
    points: int
) -> Projection:
    '''
        Measures every candidate on the series and projects with the best one.
        A model is used only when it beats the naive guess; on a tie, or when
        nothing can be measured, the projection is the naive one.

        Args:
            values (list[float]): The history, oldest first.
            horizon (int): Steps ahead.
            season (int | None): Points per season (12 for months), or None.
            points (int): How many of the last points to test the models on.

        Returns:
            Projection: The model used, its projection and the errors.
    '''
    models, start = candidates(values, season, points)
    tested = max(len(values) - start, 0)
    naive_error = backtest(values, NAIVE, season, start)
    best, best_error = NAIVE, naive_error
    for model in models[1:]:
        error = backtest(values, model, season, start)
        if error is not None and best_error is not None and error < best_error:
            best, best_error = model, error
    return Projection(model = best, forecast = project(values, best, horizon, season),
                      error_percent = best_error, naive_error_percent = naive_error,
                      tested_points = tested if naive_error is not None else 0)
