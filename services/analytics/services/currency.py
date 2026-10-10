'''
    Reading a report in another currency.

    Every money column of the sales frame is converted at the rate of **its
    own row's day**, never at today's. A sale of March and a sale of September
    are not the same dollars, and converting a whole year at one rate turns a
    devaluation into growth — which is the mistake this module exists to stop.

    The rates come from QUOTES, which owns them: this service asks, it does
    not read that table. One call brings the window the frame covers and the
    series is forward-filled, because the BCB does not publish every day and
    a Sunday settles at Friday's figure.

    Before the float began the rate was fixed. Those rows convert at the fixed
    figure and the answer says so, so nobody reads a decreed stability as a
    market fact.
'''
from typing import Any

import pandas as pd
import requests
from pydantic import BaseModel

from schemas.analytics import AnalyticsError, Money, ReferenceRates
from services.analytics_utils import AMOUNT_DECIMALS
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger

ENV_VARS = load_and_validate_env_vars({
    'QUOTES_SERVICE_URL': str,
    'QUOTES_TIMEOUT_SECONDS': int,
    'PARALLEL_CURRENCY': str,
    'PARALLEL_FALLBACK_CURRENCY': str,
})
QUOTES_SERVICE_URL = ENV_VARS['QUOTES_SERVICE_URL'].rstrip('/')
QUOTES_TIMEOUT_SECONDS = ENV_VARS['QUOTES_TIMEOUT_SECONDS']
# The USDT series (Binance P2P, the parallel dollar) starts the day it was
# connected; days before it read at the official rate, and the answer says so.
PARALLEL_CURRENCY = ENV_VARS['PARALLEL_CURRENCY']
PARALLEL_FALLBACK_CURRENCY = ENV_VARS['PARALLEL_FALLBACK_CURRENCY']

_DATE = 'date'
# The regime QUOTES reports for a day before the boliviano floated.
_FIXED_REGIME = 'FIXED'


def _fetch_rates(
    currency: str,
    auth_token: str,
    window: tuple[str, str]
) -> list[dict[str, Any]]:
    '''
        The published series of one currency over a window, from QUOTES.

        Args:
            currency (str): ISO 4217 code.
            auth_token (str): The caller's Authorization header.
            window (tuple[str, str]): First and last day the frame covers.

        Returns:
            list[dict[str, Any]]: Published rates, oldest first.

        Raises:
            ServiceUnavailableError: QUOTES unreachable or refusing.
    '''
    start, end = window
    try:
        response = requests.get(
            f'{QUOTES_SERVICE_URL}/v1/quotes/exchange-rates',
            headers = {'Authorization': auth_token},
            params = {'currency': currency, 'start': start, 'end': end},
            timeout = QUOTES_TIMEOUT_SECONDS
        )
    except requests.exceptions.RequestException as error:
        error_msg = f'Network error asking QUOTES for {currency}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = AnalyticsError.RATES_UNAVAILABLE.value
        ) from error

    if not response.ok:
        error_msg = (f'QUOTES refused the {currency} series: '
                     f'status={response.status_code} body={response.text[:200]}')
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = AnalyticsError.RATES_UNAVAILABLE.value)
    return (response.json() or {}).get('rates') or []


def _fixed_rate_before(
    currency: str,
    auth_token: str,
    day: str
) -> float | None:
    '''
        The rate of the fixed regime, when `day` falls in it; None otherwise.

        The published series starts when the boliviano floated. A sale made
        before that was paid at the fixed rate, and QUOTES —which owns the
        rate— says so for any day it is asked about. Asking it keeps the
        figure out of this service.

        Args:
            currency (str): ISO 4217 code.
            auth_token (str): The caller's Authorization header.
            day (str): The latest day with no published rate, YYYY-MM-DD.

        Returns:
            float | None: The fixed rate, or None when that day is in the
                float and the gap is real.

        Raises:
            ServiceUnavailableError: QUOTES unreachable or refusing.
    '''
    try:
        response = requests.get(
            f'{QUOTES_SERVICE_URL}/v1/quotes/exchange-rates/at',
            headers = {'Authorization': auth_token},
            params = {'currency': currency, 'date': day},
            timeout = QUOTES_TIMEOUT_SECONDS
        )
    except requests.exceptions.RequestException as error:
        error_msg = f'Network error asking QUOTES for the {currency} rate on {day}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = AnalyticsError.RATES_UNAVAILABLE.value
        ) from error
    if response.status_code == 404:
        return None
    if not response.ok:
        error_msg = (f'QUOTES refused the {currency} rate on {day}: '
                     f'status={response.status_code} body={response.text[:200]}')
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = AnalyticsError.RATES_UNAVAILABLE.value)
    answer = response.json() or {}
    return float(answer['rate']) if answer.get('regime') == _FIXED_REGIME else None


def _rate_series(
    rates: list[dict[str, Any]],
    days: pd.Series
) -> pd.Series:
    '''
        The rate in force on each day the frame mentions.

        Forward-filled on purpose: the BCB does not publish every day, and the
        rate of a Friday governs until the next publication. A day before the
        first publication stays empty and its rows are left in the original
        currency rather than converted at a figure nobody published.

        Args:
            rates (list[dict[str, Any]]): Published rates.
            days (pd.Series): The dates of the frame, as datetime64.

        Returns:
            pd.Series: One rate per row, aligned to `days`.
    '''
    published = pd.Series(
        # QUOTES answers `ExchangeRatePoint` items: {date, rate}.
        {pd.Timestamp(rate['date']): float(rate['rate']) for rate in rates}
    ).sort_index()
    if published.empty:
        return pd.Series(index = days.index, dtype = 'float64')
    calendar = published.reindex(
        pd.date_range(published.index.min(), max(published.index.max(), days.max()))
    ).ffill()
    return days.dt.normalize().map(calendar)


def _fill_from_official(
    series: pd.Series,
    days: pd.Series,
    auth_token: str
) -> tuple[pd.Series, int]:
    '''
        Fills the USDT gaps with the official rate of each row's own day.

        Args:
            series (pd.Series): USDT rate per row, empty before its first reading.
            days (pd.Series): The dates of the frame, as datetime64.
            auth_token (str): The caller's Authorization header, for QUOTES.

        Returns:
            tuple[pd.Series, int]: The filled series and how many rows it filled.
    '''
    window = (days.min().date().isoformat(), days.max().date().isoformat())
    official = _rate_series(_fetch_rates(PARALLEL_FALLBACK_CURRENCY, auth_token, window), days)
    before = series.isna()
    filled = series.where(~before, official)
    return filled, int((before & filled.notna()).sum())


def rates_per_row(
    dataframe: pd.DataFrame,
    currency: str,
    auth_token: str
) -> tuple[pd.Series, dict[str, int]]:
    '''
        The rate of each row's own day, with how it was obtained.

        Shared by the conversion of a whole report and by the exchange-rate
        effect, which needs the rate itself and not converted amounts.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows, with `date`.
            currency (str): ISO 4217 code, or the parallel USDT.
            auth_token (str): The caller's Authorization header, for QUOTES.

        Returns:
            tuple[pd.Series, dict[str, int]]: One rate per row (empty where no
                rate exists) and the counts at the fallback and fixed rates.
    '''
    days = pd.to_datetime(dataframe[_DATE])
    rates = _fetch_rates(
        currency, auth_token,
        (days.min().date().isoformat(), days.max().date().isoformat())
    )
    series = _rate_series(rates, days)

    # In USDT, the days before the series read at the official rate of their
    # own day: a later USDT reading filled backwards would be invented.
    at_fallback = 0
    fixed_currency = currency
    if currency == PARALLEL_CURRENCY and series.isna().any():
        series, at_fallback = _fill_from_official(series, days, auth_token)
        fixed_currency = PARALLEL_FALLBACK_CURRENCY

    # Days before the first published rate. When they belong to the fixed
    # regime they convert at its rate; the series is forward-filled, so every
    # missing day is earlier than the latest one asked about.
    missing = series.isna()
    at_fixed = 0
    if missing.any():
        fixed = _fixed_rate_before(
            fixed_currency, auth_token, days[missing].max().date().isoformat()
        )
        if fixed:
            series = series.where(~missing, fixed)
            at_fixed = int(missing.sum())
    return series, {'at_fallback': at_fallback, 'at_fixed': at_fixed}


def current_rate(
    currency: str,
    auth_token: str,
    today: str
) -> float:
    '''
        The latest published rate on or before today: what replacing the
        merchandise costs now. In USDT, the official one until the USDT
        series has a reading.

        Args:
            currency (str): ISO 4217 code, or the parallel USDT.
            auth_token (str): The caller's Authorization header, for QUOTES.
            today (str): Today, YYYY-MM-DD.

        Returns:
            float: Bolivianos per unit of the currency.

        Raises:
            ServiceUnavailableError: No rate at all to measure against.
    '''
    month_ago = (pd.Timestamp(today) - pd.Timedelta(days = 31)).date().isoformat()
    rates = _fetch_rates(currency, auth_token, (month_ago, today))
    if not rates and currency == PARALLEL_CURRENCY:
        rates = _fetch_rates(PARALLEL_FALLBACK_CURRENCY, auth_token, (month_ago, today))
    if not rates:
        error_msg = f'No {currency} rate published in the month before {today}.'
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = AnalyticsError.RATES_UNAVAILABLE.value)
    return float(sorted(rates, key = lambda rate: rate['date'])[-1]['rate'])


def in_three_currencies[ResponseModel: BaseModel](
    response_type: type[ResponseModel],
    payload: dict[str, Any],
    auth_token: str,
    today: str
) -> ResponseModel:
    '''
        Assembles a response counted in bolivianos with every amount also in
        the official dollar and in USDT, at today's rates.

        The engines worked in bolivianos; this is the one place the dollars
        appear, so a balance, a count and a share never move with the rate.

        Args:
            response_type (type[ResponseModel]): The response DTO.
            payload (dict[str, Any]): Its fields, amounts in bolivianos.
            auth_token (str): The caller's Authorization header, for QUOTES.
            today (str): Today, YYYY-MM-DD.

        Returns:
            ResponseModel: The response, each `Amount` field a `Money`.
    '''
    # The official dollar is the fallback of the parallel one: the same code.
    rates = ReferenceRates(
        usd = current_rate(PARALLEL_FALLBACK_CURRENCY, auth_token, today),
        usdt = current_rate(PARALLEL_CURRENCY, auth_token, today)
    )
    return response_type.model_validate(
        {**payload, 'rates': rates},
        context = {'rates': rates, 'decimals': AMOUNT_DECIMALS}
    )


# What one boliviano of a sale is worth in each reference currency at the
# close of its month: 1 / the rate of the month's last day (today's, for the
# month in progress). An analyst reads sales by month, and a month closes at
# one rate; a sum of amounts times the factor is that month's sales at its
# close, so the engines group the dollars next to the bolivianos and every
# ranking, share and count stays the one the bolivianos give.
USD_FACTOR = '_per_usd'
USDT_FACTOR = '_per_usdt'


def with_month_close_factors(
    dataframe: pd.DataFrame,
    auth_token: str,
    today: str
) -> pd.DataFrame:
    '''
        The sales with the factor of their month's closing rate in the
        official dollar and in USDT.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows, in bolivianos.
            auth_token (str): The caller's Authorization header, for QUOTES.
            today (str): Today, YYYY-MM-DD: the close of the month in progress.

        Returns:
            pd.DataFrame: The same rows with `USD_FACTOR` and `USDT_FACTOR`.
    '''
    if dataframe.empty or _DATE not in dataframe.columns:
        return dataframe
    days = pd.to_datetime(dataframe[_DATE])
    closes = pd.DataFrame({_DATE: (days + pd.offsets.MonthEnd(0)).clip(
        upper = pd.Timestamp(today))}, index = dataframe.index)
    usd, _ = rates_per_row(closes, PARALLEL_FALLBACK_CURRENCY, auth_token)
    usdt, _ = rates_per_row(closes, PARALLEL_CURRENCY, auth_token)
    return dataframe.assign(**{USD_FACTOR: 1 / usd.to_numpy(dtype = float),
                               USDT_FACTOR: 1 / usdt.to_numpy(dtype = float)})


def money_sums(
    dataframe: pd.DataFrame,
    values: pd.Series,
    keys: Any
) -> pd.DataFrame:
    '''
        The sum of `values` per group in bolivianos and, when the frame
        carries the month-close factors, in the official dollar and USDT.

        Args:
            dataframe (pd.DataFrame): The rows `values` belongs to.
            values (pd.Series): Amounts in bolivianos, aligned with the rows.
            keys (Any): What to group by: a column, a list of them, or a
                Series aligned with the rows.

        Returns:
            pd.DataFrame: Columns `bob` and, with factors, `usd` and `usdt`.
    '''
    parts = {'bob': values}
    if USD_FACTOR in dataframe.columns:
        parts['usd'] = values * dataframe[USD_FACTOR]
        parts['usdt'] = values * dataframe[USDT_FACTOR]
    frame = pd.DataFrame(parts, index = dataframe.index)
    if isinstance(keys, str):
        keys = dataframe[keys]
    elif isinstance(keys, list):
        keys = [dataframe[key] for key in keys]
    return frame.groupby(keys).sum()


def to_money(
    bob: float,
    usd: float | None = None,
    usdt: float | None = None
) -> float | Money:
    '''
        An amount in bolivianos, as `Money` when its dollars are known.

        Args:
            bob (float): Bolivianos.
            usd (float | None): Official dollars, None when not computed.
            usdt (float | None): USDT, None when not computed.

        Returns:
            float | Money: The rounded bolivianos alone, or the three.
    '''
    bolivianos = round(float(bob), AMOUNT_DECIMALS) if pd.notna(bob) else 0.0
    if usd is None or pd.isna(usd):
        return bolivianos
    return Money(bob = bolivianos, usd = round(float(usd), AMOUNT_DECIMALS),
                 usdt = round(float(usdt), AMOUNT_DECIMALS)
                 if usdt is not None and pd.notna(usdt) else None)


def money_row(sums: pd.Series) -> float | Money:
    '''
        One row of `money_sums` as an amount.

        Args:
            sums (pd.Series): `bob` and, when computed, `usd` and `usdt`.

        Returns:
            float | Money: The amount.
    '''
    return to_money(sums['bob'], sums.get('usd'), sums.get('usdt'))


def money_total(
    dataframe: pd.DataFrame,
    values: pd.Series
) -> pd.Series:
    '''
        The sum of `values` over the whole frame in each currency it carries.

        Args:
            dataframe (pd.DataFrame): The rows `values` belongs to.
            values (pd.Series): Amounts in bolivianos, aligned with the rows.

        Returns:
            pd.Series: `bob` and, with the month-close factors, `usd` and `usdt`.
    '''
    if dataframe.empty:
        return pd.Series({'bob': 0.0})
    return money_sums(dataframe, values, pd.Series(0, index = dataframe.index)).sum()
