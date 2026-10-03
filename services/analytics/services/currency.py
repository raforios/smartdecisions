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
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from schemas.analytics import AnalyticsError
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger

ENV_VARS = load_and_validate_env_vars({
    'QUOTES_SERVICE_URL': str,
    'QUOTES_TIMEOUT_SECONDS': int,
    'BASE_CURRENCY': str,
})
QUOTES_SERVICE_URL = ENV_VARS['QUOTES_SERVICE_URL'].rstrip('/')
QUOTES_TIMEOUT_SECONDS = ENV_VARS['QUOTES_TIMEOUT_SECONDS']
# What the file is written in. Asking for it is asking for no conversion.
BASE_CURRENCY = ENV_VARS['BASE_CURRENCY']

# The columns that hold money. A rate applies to an amount, not to a quantity
# or a coordinate, so the list is explicit: converting a latitude would be
# silent nonsense.
MONEY_COLUMNS: Tuple[str, ...] = (
    'unit_price', 'unit_cost', 'total_amount', 'credit_limit'
)
_DATE = 'date'
# The regime QUOTES reports for a day before the boliviano floated.
_FIXED_REGIME = 'FIXED'


def _fetch_rates(
    currency: str,
    auth_token: str,
    window: Tuple[str, str]
) -> List[Dict[str, Any]]:
    '''
        The published series of one currency over a window, from QUOTES.

        Args:
            currency (str): ISO 4217 code.
            auth_token (str): The caller's Authorization header.
            window (Tuple[str, str]): First and last day the frame covers.

        Returns:
            List[Dict[str, Any]]: Published rates, oldest first.

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
) -> Optional[float]:
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
            Optional[float]: The fixed rate, or None when that day is in the
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
    rates: List[Dict[str, Any]],
    days: pd.Series
) -> pd.Series:
    '''
        The rate in force on each day the frame mentions.

        Forward-filled on purpose: the BCB does not publish every day, and the
        rate of a Friday governs until the next publication. A day before the
        first publication stays empty and its rows are left in the original
        currency rather than converted at a figure nobody published.

        Args:
            rates (List[Dict[str, Any]]): Published rates.
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


def convert_frame(
    dataframe: pd.DataFrame,
    currency: str,
    auth_token: str
) -> Tuple[pd.DataFrame, Optional[Dict[str, Any]]]:
    '''
        The same rows, with every amount read in another currency.

        Args:
            dataframe (pd.DataFrame): Normalized sales rows.
            currency (str): ISO 4217 code to read the report in.
            auth_token (str): The caller's Authorization header, for QUOTES.

        Returns:
            Tuple[pd.DataFrame, Optional[Dict[str, Any]]]: The converted frame
                and what the conversion was based on. The descriptor is None
                when nothing was converted, so a caller can say so instead of
                implying a rate that was never applied.
    '''
    if currency == BASE_CURRENCY or dataframe.empty or _DATE not in dataframe.columns:
        return dataframe, None

    days = pd.to_datetime(dataframe[_DATE])
    rates = _fetch_rates(
        currency, auth_token,
        (days.min().date().isoformat(), days.max().date().isoformat())
    )
    series = _rate_series(rates, days)

    # Days before the first published rate. When they belong to the fixed
    # regime they convert at its rate; the series is forward-filled, so every
    # missing day is earlier than the latest one asked about.
    missing = series.isna()
    at_fixed = 0
    if missing.any():
        fixed = _fixed_rate_before(
            currency, auth_token, days[missing].max().date().isoformat()
        )
        if fixed:
            series = series.where(~missing, fixed)
            at_fixed = int(missing.sum())

    converted = dataframe.copy()
    for column in MONEY_COLUMNS:
        if column in converted.columns:
            # A row with no rate keeps its own amount: dividing by nothing
            # turned it into NaN, and a NaN sums as zero.
            converted[column] = (converted[column] / series).where(
                series.notna(), converted[column]
            )

    applied = int(series.notna().sum())
    message = (f'Converted {applied}/{len(series)} row(s) to {currency} at the rate '
               f'of each row\'s own day.')
    logger.info(message)
    return converted, {
        'currency': currency,
        'base_currency': BASE_CURRENCY,
        'rows_converted': applied,
        'rows_at_fixed_rate': at_fixed,
        'rows_total': int(len(series)),
        # Rows before the first published rate keep their original amounts.
        # Saying so is the difference between a gap and a silent lie.
        'rows_without_rate': int(len(series) - applied)
    }
