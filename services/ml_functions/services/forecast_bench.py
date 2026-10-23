'''
    The bench: several models measured on the same series (23-oct-2026, from
    the copy QUOTES kept for the exchange rate).

    Each model projects `horizon` steps from every point that leaves
    `min_train` points behind it, and its misses are averaged: the error
    published next to a projection comes from the series itself, never from an
    assumed interval. The naive guess is measured the same way, because it is
    the one to beat. Each replay fits the model's weights on the points
    before it only, so no replay sees the future it is measured against.

    Pure Python and free of the environment, like the rest of the projection.
'''
from dataclasses import dataclass

from services.forecast import NAIVE, ForecastSpec, project


@dataclass(frozen = True)
class BenchSpec:
    '''
        How the bench runs: steps ahead, the points a replay needs, the
        replays an error needs and the moving-average window.
    '''
    horizon: int
    min_train: int
    min_windows: int
    window: int | None = None


@dataclass(frozen = True)
class Measured:
    '''
        One model on the series: its projection and its mean absolute miss.
    '''
    model: str
    forecast: list[float]
    mean_absolute_error: float | None


def replays(
    values: list[float],
    spec: BenchSpec
) -> int:
    '''
        How many replays the series affords at the horizon.

        Args:
            values (list[float]): The history.
            spec (BenchSpec): Horizon and points a replay needs.

        Returns:
            int: The number of replays.
    '''
    return max(0, len(values) - spec.horizon + 1 - spec.min_train)


def mean_absolute_error(
    values: list[float],
    model: str,
    spec: BenchSpec
) -> float | None:
    '''
        The mean absolute miss of a model over every replay of the series.

        Args:
            values (list[float]): The history, oldest first.
            model (str): One of the models of services/forecast.py.
            spec (BenchSpec): Horizon, points per replay, replays needed, window.

        Returns:
            float | None: The error in the unit of the series, or None with
                fewer replays than `min_windows`.
    '''
    if replays(values, spec) < spec.min_windows:
        return None
    settings = ForecastSpec(horizon = spec.horizon, season = None, points = 1,
                            window = spec.window)
    errors = []
    for cut in range(spec.min_train, len(values) - spec.horizon + 1):
        projected = project(values[:cut], model, spec.horizon, settings)
        actual = values[cut:cut + spec.horizon]
        errors.append(sum(abs(one - two) for one, two in zip(projected, actual)) / len(actual))
    return sum(errors) / len(errors)


def compare(
    values: list[float],
    models: list[str],
    spec: BenchSpec
) -> tuple[list[Measured], float | None]:
    '''
        Runs every model asked for and measures it; the one that missed least
        comes first, and one that could not be measured goes last.

        Args:
            values (list[float]): The history, oldest first.
            models (list[str]): The models to run.
            spec (BenchSpec): Horizon, points per replay, replays needed, window.

        Returns:
            tuple[list[Measured], float | None]: The runs, and the naive error.
    '''
    settings = ForecastSpec(horizon = spec.horizon, season = None, points = 1,
                            window = spec.window)
    runs = [Measured(model = model,
                     forecast = project(values, model, spec.horizon, settings),
                     mean_absolute_error = mean_absolute_error(values, model, spec))
            for model in dict.fromkeys(models)]
    runs.sort(key = lambda run: (run.mean_absolute_error is None, run.mean_absolute_error or 0.0))
    return runs, mean_absolute_error(values, NAIVE, spec)
