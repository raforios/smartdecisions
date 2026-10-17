'''
    Projection of a series: the shared calculation every service asks for by
    HTTP instead of keeping its own copy (Rafael, 17-oct-2026: ML_FUNCTIONS is
    the base service of calculations, formulas, predictions, projections and
    classifications).

    Pure Python and free of the environment: the CI runs this service's tests
    with no .env, and every function here is tested there.

    The model is Holt's linear trend with damping —the level and the trend
    follow the series, and the trend fades step by step— and its error is
    always published next to that of "the next value is the same as the last
    one": a model that does no better than that should not be trusted for more.
'''


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


def backtest(
    values: list[float],
    smoothing: tuple[float, float, float],
    points: int
) -> tuple[float | None, float | None]:
    '''
        How the model did on the last points of the series, each predicted
        from the points before it, next to the naive guess.

        Args:
            values (list[float]): The history, oldest first.
            smoothing (tuple[float, float, float]): alpha, beta and phi.
            points (int): How many of the last points to test.

        Returns:
            tuple[float | None, float | None]: Mean absolute percentage error
                of the model and of the naive guess; None without enough data.
    '''
    model, naive = [], []
    for end in range(max(len(values) - points, 2), len(values)):
        actual = values[end]
        if not actual:
            continue
        model.append(abs(damped_trend(values[:end], 1, smoothing)[0] - actual) / abs(actual))
        naive.append(abs(values[end - 1] - actual) / abs(actual))
    if not model:
        return None, None
    return 100 * sum(model) / len(model), 100 * sum(naive) / len(naive)
