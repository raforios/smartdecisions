'''
    Reader for the Banco Central de Bolivia's published exchange rate.

    The BCB serves its quotation table one date at a time, from an endpoint the
    public pages consume:

        /librerias/indicadores/otras/otras_imprimir.php?qdd=DD&qmm=MM&qaa=YYYY

    It answers HTML — there is no JSON API — so the figure is extracted from the
    table. That makes this module the fragile part of the service, and it is
    deliberately the only fragile part: everything downstream reads our own
    stored history, so a change in the BCB's markup stops new data from arriving
    but never breaks what is already published.

    The parser looks for the official rate row by its currency name and code
    rather than by position, because a column reordering is far more likely than
    a rename. When the shape stops matching, the module says it cannot read the
    page instead of returning a number it is not sure about: a wrong exchange
    rate silently stored would poison every scenario built on top of it.
'''
import re
from datetime import date as date_type
from typing import Optional

import requests

from schemas.quotes import QuotesError
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger


ENV_VARS = load_and_validate_env_vars({}, optional_env_vars = {
    'BCB_BASE_URL': str,
    'BCB_REQUEST_TIMEOUT_SECONDS': int,
})
BASE_URL = (
    ENV_VARS['BCB_BASE_URL']
    or 'https://www.bcb.gob.bo/librerias/indicadores/otras/otras_imprimir.php'
)
REQUEST_TIMEOUT_SECONDS = ENV_VARS['BCB_REQUEST_TIMEOUT_SECONDS'] or 20

SOURCE_NAME = 'BCB'

# The official rate sits in the row naming the country, the currency and its
# ISO code. Matching on that triplet survives a column reorder; matching on a
# cell position would not. Accents are stripped before matching because the page
# encodes them as HTML entities.
_RATE_PATTERN = re.compile(
    r'ESTADOS\s+UNIDOS\s*\|?\s*D[^|]*LAR\s*\|?\s*USD\s*\|?\s*([\d.,]+)',
    re.IGNORECASE
)


def _plain_text(html: str) -> str:
    '''
        Flattens the HTML table into a single spaced line.

        Args:
            html (str): Raw page returned by the BCB.

        Returns:
            str: Tag-free text with cells separated by pipes.
    '''
    text = re.sub(r'<[^>]+>', ' | ', html)
    return re.sub(r'(\s*\|\s*)+', ' | ', text)


def _to_float(raw: str) -> Optional[float]:
    '''
        Parses the rate as the page writes it.

        Args:
            raw (str): Cell content, e.g. '12.26'.

        Returns:
            float | None: The value, or None when it is not a number.
    '''
    cleaned = raw.strip().replace(',', '')
    try:
        return float(cleaned)
    except ValueError:
        return None


def fetch_official_rate(day: date_type) -> Optional[float]:
    '''
        Returns the official USD rate the BCB published for one date.

        Args:
            day (date): Date to query.

        Returns:
            float | None: Bolivianos per dollar, or None when the BCB publishes
                nothing for that date — weekends and holidays have no table, and
                that is an absence, not a failure.

        Raises:
            ServiceUnavailableError: If the BCB cannot be reached, or answers
                something this parser does not recognise.
    '''
    params = {'qdd': f'{day.day:02d}', 'qmm': f'{day.month:02d}', 'qaa': str(day.year)}
    try:
        response = requests.get(BASE_URL, params = params,
                                timeout = REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as error:
        error_msg = f'Could not reach the BCB for {day}: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(
            detail = QuotesError.SOURCE_UNAVAILABLE.value
        ) from error

    text = _plain_text(response.text)
    match = _RATE_PATTERN.search(text)
    if not match:
        # Either there is no table for that date, or the page changed shape.
        # Those are different problems: a missing table is short, a redesigned
        # page is not.
        if 'COTIZACI' not in text.upper():
            message = f'The BCB publishes no quotation table for {day}.'
            logger.info(message)
            return None
        error_msg = (
            f'The BCB page for {day} no longer matches the expected layout; '
            'the official rate row was not found.'
        )
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = QuotesError.SOURCE_UNREADABLE.value)

    rate = _to_float(match.group(1))
    if rate is None or rate <= 0:
        error_msg = f'The BCB returned an unusable rate for {day}: {match.group(1)!r}'
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = QuotesError.SOURCE_UNREADABLE.value)

    message = f'BCB official rate for {day}: {rate}'
    logger.info(message)
    return rate
