'''
    QUOTES controllers.
'''
from datetime import date as date_type
from typing import Optional

from fastapi import Request

from models.quotes import USD
from schemas.quotes import (
    ExchangeRateHistory,
    SaleScenario,
    SaleScenarioRequest,
    SyncResult
)
from services.quotes import (
    get_history_service,
    sale_scenario_service,
    sync_rates_service
)
from services.utils import handle_service_errors


@handle_service_errors('QUOTES')
async def sync_rates_controller(
    days_back: int,
    currency: str,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> SyncResult:
    '''
        Pulls the recently published rates into our own history.

        Args:
            days_back (int): How many days back to cover.
            currency (str): ISO 4217 code.
            current_user (str): Authenticated caller.
            request (Request): Incoming request, used by the audit decorator.

        Returns:
            SyncResult: What the sync stored, skipped and could not find.
    '''
    result = await sync_rates_service(days_back = days_back, currency = currency)
    return SyncResult(**result)


@handle_service_errors('QUOTES')
async def get_history_controller(
    date_from: Optional[date_type],
    date_to: Optional[date_type],
    current_user: str, # pylint: disable=unused-argument
    request: Request, # pylint: disable=unused-argument
    currency: str = USD
) -> ExchangeRateHistory:
    '''
        Returns the stored exchange-rate series.

        Args:
            date_from (date | None): First date to include.
            date_to (date | None): Last date to include.
            current_user (str): Authenticated caller.
            request (Request): Incoming request, used by the audit decorator.
            currency (str): ISO 4217 code.

        Returns:
            ExchangeRateHistory: The series we hold for that window.
    '''
    result = await get_history_service(
        date_from = date_from, date_to = date_to, currency = currency
    )
    return ExchangeRateHistory(**result)


@handle_service_errors('QUOTES')
async def sale_scenario_controller(
    scenario: SaleScenarioRequest,
    current_user: str, # pylint: disable=unused-argument
    request: Request # pylint: disable=unused-argument
) -> SaleScenario:
    '''
        Compares settling a sale today against settling it after a wait.

        Args:
            scenario (SaleScenarioRequest): What is being sold and for how long
                the seller is willing to wait.
            current_user (str): Authenticated caller.
            request (Request): Incoming request, used by the audit decorator.

        Returns:
            SaleScenario: Both outcomes and the difference between them.
    '''
    result = await sale_scenario_service(
        quantity = scenario.quantity,
        unit_price_usd = scenario.unit_price_usd,
        days_ahead = scenario.days_ahead,
        mineral_change_percent = scenario.mineral_change_percent
    )
    return SaleScenario(**result)
