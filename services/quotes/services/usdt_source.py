'''
    The USDT price in bolivianos on Binance P2P: the reference of the
    parallel dollar in Bolivia, and less political than the official rate.

    The public quote endpoint needs no credentials and answers only the price
    of now, so the history is ours: one reading a day, kept next to the
    official rate in the same table.
'''
from typing import Optional

import requests

from schemas.quotes import QuotesError
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger

ENV_VARS = load_and_validate_env_vars({
    'USDT_SOURCE_URL': str,
    'USDT_TIMEOUT_SECONDS': int,
})
SOURCE_URL = ENV_VARS['USDT_SOURCE_URL']
TIMEOUT_SECONDS = ENV_VARS['USDT_TIMEOUT_SECONDS']
SOURCE_NAME = 'BINANCE_P2P'


def fetch_usdt_rate() -> Optional[float]:
    '''
        Bolivianos per USDT right now on Binance P2P.

        Returns:
            float | None: The price, or None when the answer carries none.

        Raises:
            ServiceUnavailableError: If Binance cannot be reached or refuses.
    '''
    try:
        response = requests.get(SOURCE_URL, timeout = TIMEOUT_SECONDS)
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as error:
        error_msg = f'Could not read the USDT price from Binance P2P: {error}'
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = QuotesError.SOURCE_UNAVAILABLE.value) from error

    price = (payload.get('data') or {}).get('price')
    if price is None:
        error_msg = f'Binance P2P answered without a price: {payload.get("code")}.'
        logger.warning(error_msg)
        return None
    return float(price)
