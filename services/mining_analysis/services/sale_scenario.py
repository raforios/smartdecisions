'''
    "Vender hoy o esperar": a sale settled today against one settled later.

    Moved from QUOTES (23-oct-2026), which is a base service now: the decision
    is about minerals, and QUOTES only answers where the dollar is heading.
'''
from typing import Any

import requests

from schemas.market import MarketError, SaleOutcome, SaleScenario, SaleScenarioRequest
from services.environment import load_and_validate_env_vars
from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger
from services.utils import API_URL, REQUEST_TIMEOUT_SECONDS

ENV_VARS = load_and_validate_env_vars({
    'AMOUNT_DECIMALS': int,
    'RATE_DECIMALS': int,
})
# Decimals a published amount and a published rate carry.
AMOUNT_DECIMALS = ENV_VARS['AMOUNT_DECIMALS']
RATE_DECIMALS = ENV_VARS['RATE_DECIMALS']


def rate_forecast(
    days_ahead: int,
    auth_token: str
) -> dict[str, Any]:
    '''
        The official dollar projected `days_ahead` days, asked of QUOTES.

        Args:
            days_ahead (int): How far ahead.
            auth_token (str): The caller's Authorization header.

        Returns:
            dict[str, Any]: QUOTES' RateForecast: last and final rate,
                confidence and change.

        Raises:
            ServiceUnavailableError: RATES_UNAVAILABLE when QUOTES cannot answer.
    '''
    try:
        response = requests.get(f'{API_URL}/v1/quotes/exchange-rates/forecast',
                                params = {'days_ahead': days_ahead},
                                headers = {'Authorization': auth_token},
                                timeout = REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as error:
        error_msg = f'Network error asking QUOTES for the rate forecast: {error}'
        logger.error(error_msg, exc_info = True)
        raise ServiceUnavailableError(detail = MarketError.RATES_UNAVAILABLE.value) from error
    if not response.ok:
        error_msg = (f'QUOTES refused the rate forecast: status={response.status_code} '
                     f'body={response.text[:200]}')
        logger.error(error_msg)
        raise ServiceUnavailableError(detail = MarketError.RATES_UNAVAILABLE.value)
    return response.json()


def sale_scenario(
    scenario: SaleScenarioRequest,
    forecast: dict[str, Any]
) -> SaleScenario:
    '''
        Prices the same sale at today's rate and at the projected one.

        Both sides of the price move: the mineral is quoted in dollars and the
        dollar in bolivianos. The mineral's expected change is the caller's
        input, so the seller can test any assumption, including none.

        Args:
            scenario (SaleScenarioRequest): Quantity, price, horizon and the
                mineral's expected change.
            forecast (dict[str, Any]): QUOTES' projection of the dollar.

        Returns:
            SaleScenario: Both outcomes and the difference between them.
    '''
    today_rate = float(forecast['last_rate'])
    amount_today = round(scenario.quantity * scenario.unit_price_usd, AMOUNT_DECIMALS)
    today = SaleOutcome(exchange_rate = today_rate, mineral_price = scenario.unit_price_usd,
                        amount_usd = amount_today,
                        amount_bob = round(amount_today * today_rate, AMOUNT_DECIMALS))
    base = {'days_ahead': scenario.days_ahead, 'rate_confidence': str(forecast['confidence']),
            'mineral_change_percent': scenario.mineral_change_percent, 'today': today}
    final_rate = forecast.get('final_rate')
    if final_rate is None:
        message = (f'Sale scenario over {scenario.days_ahead} day(s) priced today only: '
                   'the rate history does not support a projection.')
        logger.info(message)
        return SaleScenario(**base)

    future_price = scenario.unit_price_usd * (1 + (scenario.mineral_change_percent or 0.0) / 100)
    amount_future = round(scenario.quantity * future_price, AMOUNT_DECIMALS)
    projected = SaleOutcome(
        exchange_rate = round(float(final_rate), RATE_DECIMALS),
        mineral_price = round(future_price, RATE_DECIMALS),
        amount_usd = amount_future,
        amount_bob = round(amount_future * float(final_rate), AMOUNT_DECIMALS)
    )
    difference = round(projected.amount_bob - today.amount_bob, AMOUNT_DECIMALS)
    percent = (round(difference / today.amount_bob * 100, AMOUNT_DECIMALS)
               if today.amount_bob else None)
    message = f'Sale scenario over {scenario.days_ahead} day(s): {difference:+.2f} Bs.'
    logger.info(message)
    return SaleScenario(**base, rate_change_percent = forecast.get('change_percent'),
                        projected = projected, difference_bob = difference,
                        difference_percent = percent)
