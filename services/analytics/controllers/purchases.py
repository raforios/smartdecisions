'''
    ANALYTICS: the purchases view, and the purchase figures of the dashboard.
'''
from typing import Any

from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.analytics import ReferenceRates
from schemas.dashboard import PurchaseFigures
from schemas.purchases import PurchasesResponse, PurchasesUnavailable
from services.analytics_utils import get_dataset_metadata, load_dataframe_from_s3
from services.currency import PARALLEL_CURRENCY, PARALLEL_FALLBACK_CURRENCY, current_rate
from services.purchases import (
    build_purchase_rows,
    last_month_amount,
    latest_prices,
    with_costs_in_bolivianos
)
from services.utils import get_current_time_gmt, handle_service_errors


def todays_rates(auth_token: str) -> ReferenceRates:
    '''
        Today's official dollar and USDT, as QUOTES publishes them.

        Args:
            auth_token (str): The caller's Authorization header, for QUOTES.

        Returns:
            ReferenceRates: Bolivianos per unit of each.
    '''
    today = get_current_time_gmt().date().isoformat()
    return ReferenceRates(usd = current_rate(PARALLEL_FALLBACK_CURRENCY, auth_token, today),
                          usdt = current_rate(PARALLEL_CURRENCY, auth_token, today))


def _prices_of(metadata: dict[str, Any]) -> dict[str, float]:
    '''
        The latest sale price of each product of the dataset.

        Args:
            metadata (dict[str, Any]): The dataset record.

        Returns:
            dict[str, float]: Bolivianos per product.
    '''
    stock_key = metadata.get('stock_s3_key')
    return latest_prices(load_dataframe_from_s3(metadata['file_s3_key']),
                         load_dataframe_from_s3(stock_key) if stock_key else None)


def _cost_moves(rows: list) -> tuple[int, int]:
    '''
        How many products' last cost rose and fell against the previous one.

        Args:
            rows (list): The purchase rows.

        Returns:
            tuple[int, int]: Rose, fell.
    '''
    changes = [row.change_vs_previous or 0 for row in rows]
    return sum(1 for change in changes if change > 0), sum(1 for change in changes if change < 0)


def purchase_figures(
    metadata: dict[str, Any],
    auth_token: str
) -> PurchaseFigures:
    '''
        The purchases of the last month and the products whose last cost moved.

        Args:
            metadata (dict[str, Any]): The dataset record.
            auth_token (str): The caller's Authorization header, for QUOTES.

        Returns:
            PurchaseFigures: Unavailable when no purchases were loaded.
    '''
    key = metadata.get('purchases_s3_key')
    if not key:
        return PurchaseFigures()
    rates = todays_rates(auth_token)
    costed = with_costs_in_bolivianos(load_dataframe_from_s3(key), auth_token, rates)
    if costed.empty:
        return PurchaseFigures()
    rows = build_purchase_rows(costed, {}, rates)
    month, amount = last_month_amount(costed, auth_token,
                                      get_current_time_gmt().date().isoformat())
    up, down = _cost_moves(rows)
    return PurchaseFigures(available = True, month = month, amount = amount,
                           cost_up = up, cost_down = down)


@handle_service_errors('ANALYTICS')
async def purchases_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: dict[str, Any],
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> PurchasesResponse:
    '''
        What the last purchase of each product cost against the previous
        ones, and what the same purchase costs today. Read-only.
    '''
    metadata = get_dataset_metadata(dynamodb_resource = dynamodb_resource,
                                    dataset_id = dataset_id, owner_email = current_user)
    key = metadata.get('purchases_s3_key')
    if not key:
        return PurchasesResponse(dataset_id = dataset_id,
                                 reason_code = PurchasesUnavailable.NO_PURCHASES.value)
    token = (params or {}).get('auth_token') or ''
    rates = todays_rates(token)
    costed = with_costs_in_bolivianos(load_dataframe_from_s3(key), token, rates)
    rows = build_purchase_rows(costed, _prices_of(metadata), rates)
    month, amount = last_month_amount(costed, token, get_current_time_gmt().date().isoformat())
    up, down = _cost_moves(rows)
    return PurchasesResponse(
        dataset_id = dataset_id, available = True, rates = rates, month = month,
        month_amount = amount, purchases_count = int(len(costed)),
        suppliers = int(costed['supplier'].nunique()), cost_up = up, cost_down = down,
        products = rows)
