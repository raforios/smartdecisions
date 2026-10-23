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

    More models any service may ask for by name (23-oct-2026, from the copies
    ANALYTICS, QUOTES and MINING_ANALYSIS kept): LINEAR, the least-squares line
    over the points; MOVING_AVERAGE, the mean of the last `window` points;
    MEAN; DRIFT, the slope from the first point to the last; SIMPLE_EXPONENTIAL,
    a smoothed level; HOLT, the trend that never fades; and THETA, half the
    line and half the smoothed level. Their weights are fitted to the series
    like the others'. A caller that names one model gets that model's projection, with
    its error next to the naive guess; naming several makes them compete.
'''
from dataclasses import dataclass
from itertools import product

from schemas.prediction import ForecastModel

# The names are the contract's (schemas/prediction.py), defined once there.
NAIVE = ForecastModel.NAIVE.value
DAMPED_TREND = ForecastModel.DAMPED_TREND.value
HOLT_WINTERS = ForecastModel.HOLT_WINTERS.value
LINEAR = ForecastModel.LINEAR.value
MOVING_AVERAGE = ForecastModel.MOVING_AVERAGE.value
MEAN = ForecastModel.MEAN.value
DRIFT = ForecastModel.DRIFT.value
SIMPLE_EXPONENTIAL = ForecastModel.SIMPLE_EXPONENTIAL.value
HOLT = ForecastModel.HOLT.value
THETA = ForecastModel.THETA.value
# The models the service chooses among when the caller names none.
DEFAULT_MODELS = (DAMPED_TREND, HOLT_WINTERS)

# The values the fit searches. They belong to the method, not to the business:
# the series picks among them, so no caller has to know they exist.
LEVEL_WEIGHTS = (0.1, 0.3, 0.5, 0.7, 0.9)
TREND_WEIGHTS = (0.05, 0.1, 0.2, 0.4)
DAMPINGS = (0.8, 0.9, 0.98)
SEASON_WEIGHTS = (0.1, 0.3, 0.5)


@dataclass(frozen = True)
class ForecastSpec:
    '''
        What is asked of a series: how far, its season, how many of its last
        points the models are measured on, which models and, for the moving
        average, how many points it averages.
    '''
    horizon: int
    season: int | None
    points: int
    models: tuple[str, ...] = DEFAULT_MODELS
    window: int | None = None


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


def linear(
    values: list[float],
    horizon: int
) -> list[float]:
    '''
        The least-squares line over the points, carried forward.

        Args:
            values (list[float]): The history, oldest first; at least two.
            horizon (int): Steps ahead.

        Returns:
            list[float]: The projected steps.
    '''
    count = len(values)
    mean_x, mean_y = (count - 1) / 2, sum(values) / count
    spread = sum((index - mean_x) ** 2 for index in range(count))
    slope = sum((index - mean_x) * (value - mean_y)
                for index, value in enumerate(values)) / spread
    return [mean_y + slope * (count - 1 + step - mean_x) for step in range(1, horizon + 1)]


def moving_average(
    values: list[float],
    horizon: int,
    window: int
) -> list[float]:
    '''
        The mean of the last `window` points (all of them when there are fewer),
        held flat.

        Args:
            values (list[float]): The history, oldest first.
            horizon (int): Steps ahead.
            window (int): How many of the last points are averaged.

        Returns:
            list[float]: The projected steps.
    '''
    last = values[-window:]
    return [sum(last) / len(last)] * horizon


def _smoothed_level(
    values: list[float],
    alpha: float
) -> tuple[float, float]:
    '''
        Simple exponential smoothing over the series.

        Args:
            values (list[float]): The history, oldest first.
            alpha (float): Weight of each new point.

        Returns:
            tuple[float, float]: The final level and the sum of squared one-step errors.
    '''
    level, total = values[0], 0.0
    for value in values[1:]:
        total += (value - level) ** 2
        level = alpha * value + (1 - alpha) * level
    return level, total


def simple_exponential(
    values: list[float],
    horizon: int
) -> list[float]:
    '''
        The smoothed level, with its weight fitted to the series, held flat.

        Args:
            values (list[float]): The history, oldest first.
            horizon (int): Steps ahead.

        Returns:
            list[float]: The projected steps.
    '''
    alpha = min(LEVEL_WEIGHTS, key = lambda weight: _smoothed_level(values, weight)[1])
    return [_smoothed_level(values, alpha)[0]] * horizon


def drift(
    values: list[float],
    horizon: int
) -> list[float]:
    '''
        The slope from the first point to the last, carried forward.

        Args:
            values (list[float]): The history, oldest first; at least two.
            horizon (int): Steps ahead.

        Returns:
            list[float]: The projected steps.
    '''
    slope = (values[-1] - values[0]) / (len(values) - 1)
    return [values[-1] + slope * step for step in range(1, horizon + 1)]


def holt(
    values: list[float],
    horizon: int
) -> list[float]:
    '''
        Holt's trend without damping: the direct contrast to the damped one.

        Args:
            values (list[float]): The history, oldest first; at least three.
            horizon (int): Steps ahead.

        Returns:
            list[float]: The projected steps.
    '''
    smoothing = min(product(LEVEL_WEIGHTS, TREND_WEIGHTS, (1.0,)),
                    key = lambda params: _damped_trend_error(values, params))
    return damped_trend(values, horizon, smoothing)


def theta(
    values: list[float],
    horizon: int
) -> list[float]:
    '''
        The theta method: half the least-squares line, half the smoothed level.

        Args:
            values (list[float]): The history, oldest first; at least three.
            horizon (int): Steps ahead.

        Returns:
            list[float]: The projected steps.
    '''
    return [(straight + level) / 2 for straight, level
            in zip(linear(values, horizon), simple_exponential(values, horizon))]


def minimum_history(
    model: str,
    season: int | None
) -> int:
    '''
        The fewest points a model needs to be fitted and to predict the next.

        Args:
            model (str): One of the models of this module.
            season (int | None): Points per season, if the series has seasons.

        Returns:
            int: The minimum length of the history.
    '''
    if model == HOLT_WINTERS:
        return (season or 0) + 2
    return {DAMPED_TREND: 3, HOLT: 3, THETA: 3, LINEAR: 2, DRIFT: 2}.get(model, 1)


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
    spec: ForecastSpec
) -> list[float]:
    '''
        Fits a model to the series and projects it.

        Args:
            values (list[float]): The history, long enough for the model.
            model (str): One of the models of this module.
            horizon (int): Steps ahead.
            spec (ForecastSpec): The season and the moving-average window.

        Returns:
            list[float]: The projected steps.
    '''
    season = spec.season
    if model != MOVING_AVERAGE and len(values) < minimum_history(model, season):
        return [values[-1]] * horizon
    # One line per model: the projection with its weights fitted to the series.
    projectors = {
        NAIVE: lambda: [values[-1]] * horizon,
        LINEAR: lambda: linear(values, horizon),
        MOVING_AVERAGE: lambda: moving_average(values, horizon, spec.window or len(values)),
        MEAN: lambda: [sum(values) / len(values)] * horizon,
        DRIFT: lambda: drift(values, horizon),
        SIMPLE_EXPONENTIAL: lambda: simple_exponential(values, horizon),
        HOLT: lambda: holt(values, horizon),
        THETA: lambda: theta(values, horizon),
        HOLT_WINTERS: lambda: holt_winters(values, horizon, fit(values, model, season), season)
    }
    if model in projectors:
        return projectors[model]()
    return damped_trend(values, horizon, fit(values, model, season))


def backtest(
    values: list[float],
    model: str,
    spec: ForecastSpec,
    start: int
) -> float | None:
    '''
        Mean absolute percentage error of a model on the points from `start`,
        each predicted by the model fitted only on the points before it.

        Args:
            values (list[float]): The history, oldest first.
            model (str): One of the models of this module.
            spec (ForecastSpec): The season and the moving-average window.
            start (int): First tested point.

        Returns:
            float | None: The error in percent; None when no point can be tested
                (or every tested value is zero).
    '''
    errors = [abs(project(values[:end], model, 1, spec)[0] - values[end]) / abs(values[end])
              for end in range(start, len(values)) if values[end]]
    return 100 * sum(errors) / len(errors) if errors else None


def candidates(
    values: list[float],
    spec: ForecastSpec
) -> tuple[list[str], int]:
    '''
        The models that can be compared on this series, and the first point
        they are all tested on: the same points for every one, or the
        comparison would not be fair.

        Args:
            values (list[float]): The history.
            spec (ForecastSpec): The models asked for, the season and how many
                of the last points the caller wants tested.

        Returns:
            tuple[list[str], int]: The models (NAIVE always first) and the first
                tested point.
    '''
    season = spec.season
    models = [NAIVE]
    for model in dict.fromkeys(spec.models):
        if model == NAIVE or (model == HOLT_WINTERS and not (season and season > 1)):
            continue
        if len(values) > minimum_history(model, season):
            models.append(model)
    start = max([len(values) - spec.points]
                + [minimum_history(model, season) for model in models])
    return models, start


def choose_and_project(
    values: list[float],
    spec: ForecastSpec
) -> Projection:
    '''
        Measures every candidate on the series and projects with the best one.
        A model is used only when it beats the naive guess; on a tie, or when
        nothing can be measured, the projection is the naive one. A caller that
        names a single model gets that model whenever the series is long enough
        for it, with its error reported next to the naive one.

        Args:
            values (list[float]): The history, oldest first.
            spec (ForecastSpec): Horizon, season, tested points, models, window.

        Returns:
            Projection: The model used, its projection and the errors.
    '''
    models, start = candidates(values, spec)
    tested = max(len(values) - start, 0)
    naive_error = backtest(values, NAIVE, spec, start)
    best, best_error = NAIVE, naive_error
    forced = len(spec.models) == 1 and len(models) == 2
    for model in models[1:]:
        error = backtest(values, model, spec, start)
        if forced or (error is not None and best_error is not None and error < best_error):
            best, best_error = model, error
    return Projection(model = best, forecast = project(values, best, spec.horizon, spec),
                      error_percent = best_error, naive_error_percent = naive_error,
                      tested_points = tested if naive_error is not None else 0)
