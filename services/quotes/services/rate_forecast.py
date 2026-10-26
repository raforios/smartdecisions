'''
    Projection of the official exchange rate.

    The models and the measuring live in ML_FUNCTIONS, the base service of
    calculations (Rafael, 17-oct and 23-oct-2026): QUOTES asks it to run them
    over the stored series, each projecting the horizon from every point that
    leaves enough history behind and averaging its misses. What stays here is
    what belongs to the exchange rate:

      - Confidence derived from how much history backs the projection.
      - A projection that collapses towards zero is refused, never clamped.
      - The dates, the change against the last rate and the published decimals.

    The history this runs on starts at the float regime, not at the beginning of
    the series. Fitting over the fixed years would conclude the rate stays at
    6.86 forever, which is the opposite of what is happening.
'''
from dataclasses import dataclass, field
from datetime import date as date_type, timedelta
from typing import Any

import requests

from models.quotes import ExchangeRateItem
from schemas.quotes import QuotesError, RateConfidence
from services.utils import load_parameters
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.utils import API_URL, REQUEST_TIMEOUT_SECONDS


# Required, not optional: a fallback in code is still a number living in
# code. Missing configuration must fail loudly at startup.
ENV_VARS = load_parameters({
    'RATE_FORECAST_MIN_DAYS': int,
    'RATE_FORECAST_HIGH_CONFIDENCE_DAYS': int,
    'RATE_FORECAST_MEDIUM_CONFIDENCE_DAYS': int,
    'BACKTEST_MIN_TRAIN': int,
    'BACKTEST_MIN_WINDOWS': int,
    'RATE_COLLAPSE_FLOOR_RATIO': float,
    'RATE_MOVING_AVERAGE_WINDOW': int,
    'ERROR_DECIMALS': int,
    'CHANGE_DECIMALS': int,
    'RATE_DECIMALS': int
})

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

# Days the moving average of the bench takes.
MOVING_AVERAGE_WINDOW = ENV_VARS['RATE_MOVING_AVERAGE_WINDOW']

# Decimals a published error, a published percentage and a published rate
# carry. The rate shares its setting with the rest of the service: the bench
# and the live forecast must not disagree on how precise a rate is.
ERROR_DECIMALS = ENV_VARS['ERROR_DECIMALS']
CHANGE_DECIMALS = ENV_VARS['CHANGE_DECIMALS']
RATE_DECIMALS = ENV_VARS['RATE_DECIMALS']

# The model the live projection uses: the trend that fades, so a run of days
# in one direction does not run away with the projection.
DEFAULT_MODEL = 'DAMPED_TREND'
# The models the bench shows side by side, the naive guess among them: the one
# a projection has to beat.
BENCH_MODELS = ('NAIVE', 'MEAN', 'DRIFT', 'LINEAR', 'MOVING_AVERAGE', 'SIMPLE_EXPONENTIAL',
                'HOLT', 'DAMPED_TREND', 'THETA')


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
    windows: int = field(default = 0)

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


def compare_models(
    values: list[float],
    days_ahead: int,
    models: list[str],
    auth_token: str
) -> dict[str, Any]:
    '''
        Runs the models over the series in ML_FUNCTIONS.

        Args:
            values (list[float]): Observed rates, oldest first.
            days_ahead (int): Days to project.
            models (list[str]): Models to run.
            auth_token (str): The caller's Authorization header.

        Returns:
            dict[str, Any]: ML_FUNCTIONS' answer: the runs, best first, the
                naive error and how many replays were averaged.

        Raises:
            ServiceUnavailableError: FORECAST_UNAVAILABLE when it cannot answer.
    '''
    body = {'values': values, 'horizon': days_ahead, 'models': models,
            'min_train': BACKTEST_MIN_TRAIN, 'min_windows': BACKTEST_MIN_WINDOWS,
            'window': MOVING_AVERAGE_WINDOW}
    try:
        response = requests.post(f'{API_URL}/v1/prediction/forecast/compare', json = body,
                                 headers = {'Authorization': auth_token},
                                 timeout = REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as error:
        error_msg = f'Network error asking ML_FUNCTIONS to compare {models}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = QuotesError.FORECAST_UNAVAILABLE.value) from error
    if not response.ok:
        error_msg = (f'ML_FUNCTIONS refused to compare {models}: '
                     f'status={response.status_code} body={response.text[:200]}')
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = QuotesError.FORECAST_UNAVAILABLE.value)
    return response.json()


def _rounded_error(value: float | None) -> float | None:
    '''
        An error as published.

        Args:
            value (float | None): The error, or None when it was not measured.

        Returns:
            float | None: Rounded to ERROR_DECIMALS.
    '''
    return None if value is None else round(float(value), ERROR_DECIMALS)


def _change(
    last_rate: float,
    final_rate: float
) -> float | None:
    '''
        The projected change against the last rate, in percent.

        Args:
            last_rate (float): The last observed rate.
            final_rate (float): The rate at the end of the horizon.

        Returns:
            float | None: The change, or None when the last rate is zero.
    '''
    return round((final_rate - last_rate) / last_rate * 100, CHANGE_DECIMALS) if last_rate else None


def run_bench(
    rates: list[ExchangeRateItem],
    days_ahead: int,
    models: list[str],
    auth_token: str
) -> tuple[list[dict[str, Any]], int]:
    '''
        Runs several models over the same series and returns them measured.

        It exists so they can be seen together, which answers a better question
        than any of them alone: HOW MUCH THE ANSWER DEPENDS ON THE MODEL. Where
        the projections agree the figure belongs to the business; where they
        separate, to the model, and that is where to distrust it. They come
        ordered by their measured error, best to worst, the default one
        included when it loses.

        Args:
            rates (list[ExchangeRateItem]): Observed quotes.
            days_ahead (int): Days to project.
            models (list[str]): Models to run.
            auth_token (str): The caller's Authorization header.

        Returns:
            tuple[list[dict[str, Any]], int]: One block per model, best first,
                and how many replays each error averages.
    '''
    observed = sorted(rates, key = lambda item: item.date)
    values = [float(item.official_rate) for item in observed]
    dates = [observed[-1].date + timedelta(days = offset) for offset in range(1, days_ahead + 1)]
    answer = compare_models(values, days_ahead, models, auth_token)
    results = [{
        'model': run['model'],
        'change_percent': _change(values[-1], run['forecast'][-1]),
        'final_rate': round(run['forecast'][-1], RATE_DECIMALS),
        'mean_absolute_error': _rounded_error(run.get('mean_absolute_error')),
        'projected': [{'date': day, 'rate': round(value, RATE_DECIMALS)}
                      for day, value in zip(dates, run['forecast'])],
    } for run in answer.get('runs', [])]
    return results, int(answer.get('windows', 0))


def project(
    rates: list[ExchangeRateItem],
    days_ahead: int,
    auth_token: str
) -> RateProjection:
    '''
        Projects the exchange rate forward from the stored history.

        Args:
            rates (list[ExchangeRateItem]): Observed rates, any order.
            days_ahead (int): How many days to project.
            auth_token (str): The caller's Authorization header.

        Returns:
            RateProjection: The projected points, the confidence the sample
                earns, the change against the last observed rate and the errors
                of the model and of the naive guess.
    '''
    observed = sorted(rates, key = lambda item: item.date)
    confidence = confidence_for(len(observed))
    if confidence is RateConfidence.INSUFFICIENT or days_ahead < 1:
        return RateProjection([], confidence, None)

    values = [float(item.official_rate) for item in observed]
    answer = compare_models(values, days_ahead, [DEFAULT_MODEL], auth_token)
    run = answer['runs'][0]
    projected = [float(value) for value in run['forecast']]

    if any(value <= min(values) * _COLLAPSE_FLOOR_RATIO for value in projected):
        error_msg = (f'The rate projection collapses within {days_ahead} day(s); '
                     'refusing to publish it.')
        logger.warning(error_msg)
        return RateProjection([], confidence, None)

    dates = [observed[-1].date + timedelta(days = offset) for offset in range(1, days_ahead + 1)]
    message = (f'Rate projected {days_ahead} day(s) over {len(observed)} observations; '
               f'confidence {confidence.value}.')
    logger.info(message)
    return RateProjection(
        list(zip(dates, projected)), confidence, _change(values[-1], projected[-1]),
        _rounded_error(run.get('mean_absolute_error')),
        _rounded_error(answer.get('naive_mean_absolute_error')),
        int(answer.get('windows', 0))
    )
