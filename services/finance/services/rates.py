'''
    The exchange rates the report shows its figures with: the official dollar
    and USDT in force at the close of each period, asked to QUOTES by HTTP.

    QUOTES owns the exchange rate; FINANCE never stores one. Every amount is
    kept in bolivianos and its dollars are read at the rate of its own period,
    never at today's (the currency rules of SMARTDECISIONS.md).

    A rate that does not exist is not invented: USDT before its series began
    stays empty, and if QUOTES cannot answer the report still comes out, in
    bolivianos, saying so.
'''
import bisect
import calendar
from datetime import date as date_type

import requests

from schemas.report import ExchangeSchema, ReportError
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger

ENV_VARS = load_and_validate_env_vars({
    'QUOTES_SERVICE_URL': str,
    'REQUEST_TIMEOUT_SECONDS': int,
})
QUOTES_SERVICE_URL = ENV_VARS['QUOTES_SERVICE_URL'].rstrip('/')
REQUEST_TIMEOUT_SECONDS = ENV_VARS['REQUEST_TIMEOUT_SECONDS']

# The currencies QUOTES serves, by the code it answers to.
OFFICIAL_DOLLAR = 'USD'
PARALLEL_DOLLAR = 'USDT'
# What QUOTES calls the regime before the boliviano floated.
_FIXED_REGIME = 'FIXED'


class RatesUnavailable(Exception):
    '''
        QUOTES could not answer: the report goes out in bolivianos only.
    '''


def period_close(
    period: str,
    today: date_type
) -> date_type:
    '''
        The day whose rate a period is read at: its last day, or today while
        the period is still open.

        Args:
            period (str): YYYY-MM or YYYY.
            today (date): Today, in the client's timezone.

        Returns:
            date: The closing day.
    '''
    if len(period) == 4:
        close = date_type(int(period), 12, 31)
    else:
        year, month = int(period[:4]), int(period[5:7])
        close = date_type(year, month, calendar.monthrange(year, month)[1])
    return min(close, today)


def _get(
    path: str,
    params: dict[str, str],
    auth_token: str | None
) -> requests.Response:
    '''
        One question to QUOTES, with the caller's token.

        Args:
            path (str): The route under /v1/quotes.
            params (dict[str, str]): Query parameters.
            auth_token (str | None): The caller's Authorization header.

        Returns:
            requests.Response: The answer.

        Raises:
            RatesUnavailable: QUOTES unreachable.
    '''
    try:
        return requests.get(f'{QUOTES_SERVICE_URL}/v1/quotes/{path}', params = params,
                            headers = {'Authorization': auth_token or ''},
                            timeout = REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as error:
        error_msg = f'Network error asking QUOTES for {path}: {error}'
        logger.error(error_msg)
        raise RatesUnavailable(error_msg) from error


def _series(
    currency: str,
    auth_token: str | None
) -> list[tuple[str, float]]:
    '''
        The stored series of one currency, oldest first.

        Args:
            currency (str): USD or USDT.
            auth_token (str | None): The caller's Authorization header.

        Returns:
            list[tuple[str, float]]: (YYYY-MM-DD, rate).

        Raises:
            RatesUnavailable: QUOTES unreachable or refusing.
    '''
    response = _get('exchange-rates', {'currency': currency}, auth_token)
    if not response.ok:
        error_msg = f'QUOTES refused the {currency} series: status={response.status_code}.'
        logger.error(error_msg)
        raise RatesUnavailable(error_msg)
    return sorted((str(point['date']), float(point['rate']))
                  for point in (response.json() or {}).get('rates') or [])


def _fixed_rate(
    currency: str,
    day: date_type,
    auth_token: str | None
) -> float | None:
    '''
        The rate of the fixed regime, for a day before the series starts.
        Only QUOTES knows it; asking keeps the figure out of this service.

        Args:
            currency (str): USD or USDT.
            day (date): A day before the series.
            auth_token (str | None): The caller's Authorization header.

        Returns:
            float | None: The fixed rate, or None when there is none.
    '''
    response = _get('exchange-rates/at', {'currency': currency, 'date': day.isoformat()},
                    auth_token)
    if not response.ok:
        return None
    answer = response.json() or {}
    return float(answer['rate']) if answer.get('regime') == _FIXED_REGIME else None


def _rate_on(
    series: list[tuple[str, float]],
    day: date_type,
    before_series: float | None
) -> float | None:
    '''
        The rate in force on a day: the latest one published on or before it.

        Args:
            series (list[tuple[str, float]]): The published rates, oldest first.
            day (date): The day.
            before_series (float | None): The rate for a day before the series.

        Returns:
            float | None: The rate.
    '''
    position = bisect.bisect_right([when for when, _ in series], day.isoformat())
    return series[position - 1][1] if position else before_series


def period_rates(
    periods: list[str],
    today: date_type,
    auth_token: str | None
) -> tuple[dict[str, ExchangeSchema], list[ReportError]]:
    '''
        The official dollar and USDT at the close of every period.

        Args:
            periods (list[str]): YYYY-MM and YYYY keys.
            today (date): Today, in the client's timezone.
            auth_token (str | None): The caller's Authorization header.

        Returns:
            tuple: The rates by period, and RATES_UNAVAILABLE when QUOTES
                could not answer.
    '''
    if not periods:
        return {}, []
    closes = {period: period_close(period, today) for period in periods}
    earliest = min(closes.values())
    try:
        series = {currency: _series(currency, auth_token)
                  for currency in (OFFICIAL_DOLLAR, PARALLEL_DOLLAR)}
        before = {currency: (_fixed_rate(currency, earliest, auth_token)
                             if not values or earliest.isoformat() < values[0][0] else None)
                  for currency, values in series.items()}
    except RatesUnavailable:
        return {}, [ReportError.RATES_UNAVAILABLE]
    return {
        period: ExchangeSchema(
            date = close.isoformat(),
            usd = _rate_on(series[OFFICIAL_DOLLAR], close, before[OFFICIAL_DOLLAR]),
            usdt = _rate_on(series[PARALLEL_DOLLAR], close, before[PARALLEL_DOLLAR])
        )
        for period, close in closes.items()
    }, []
