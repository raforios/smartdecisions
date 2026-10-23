'''
    ANALYTICS: the main dashboard. It reads the dataset once and asks each
    area's engine for its view, keeping only the salient figure of each.
'''
from typing import Any

from boto3.resources.base import ServiceResource
from fastapi import Request

from controllers.analytics import _at_month_close, _payments_of, _scoped_dataframe
from controllers.purchases import purchase_figures
from schemas.dashboard import DashboardResponse
from services.analytics_utils import (
    get_commercial_policy,
    get_credit_policy,
    get_dataset_metadata,
    load_dataframe_from_s3
)
from services.currency import in_three_currencies
from services.dashboard import (
    build_client_figures,
    build_sales_figures,
    inventory_figures,
    receivable_figures
)
from services.objectives import build_objectives, select_objective_periods
from services.portfolio import build_portfolio
from services.receivables import build_receivables
from services.stock import build_stock
from services.utils import get_current_time_gmt, handle_service_errors

_PERCENT = 100.0


def _companion(
    metadata: dict[str, Any],
    key: str
) -> Any:
    '''
        A file INGEST attached to the dataset, or None when it was not loaded.

        Args:
            metadata (dict[str, Any]): The dataset record.
            key (str): The attribute holding the file's key.

        Returns:
            Any: The DataFrame, or None.
    '''
    s3_key = metadata.get(key)
    return load_dataframe_from_s3(s3_key) if s3_key else None


@handle_service_errors('ANALYTICS')
async def dashboard_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: dict[str, Any],
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> DashboardResponse:
    '''
        The most salient figure of each area. Read-only: nothing is persisted.
    '''
    dataframe, _ = _scoped_dataframe(dynamodb_resource, dataset_id, current_user, params)
    metadata = get_dataset_metadata(dynamodb_resource = dynamodb_resource,
                                    dataset_id = dataset_id, owner_email = current_user)
    payments = _payments_of(metadata)
    objectives, _ = select_objective_periods(_companion(metadata, 'objectives_s3_key'),
                                             None, None)
    attainment = None if objectives is None else build_objectives(
        sales = dataframe, objectives = objectives, collections = payments,
        stored_policy = get_commercial_policy(dynamodb_resource = dynamodb_resource,
                                              owner_email = current_user))
    closed = _at_month_close(dataframe, params)
    receivables = build_receivables(
        sales = dataframe, collections = payments,
        stored_policy = get_credit_policy(dynamodb_resource = dynamodb_resource,
                                          owner_email = current_user))
    token = (params or {}).get('auth_token') or ''
    response = in_three_currencies(DashboardResponse, {
        'dataset_id': dataset_id,
        'sales': build_sales_figures(closed, attainment).model_dump(),
        'clients': build_client_figures(dataframe, build_portfolio(closed)).model_dump(),
        'inventory': inventory_figures(build_stock(
            sales = dataframe, stock = _companion(metadata, 'stock_s3_key'))).model_dump(),
        'receivables': receivable_figures(receivables).model_dump(),
        'purchases': purchase_figures(metadata, token).model_dump()
    }, token, get_current_time_gmt().date().isoformat())
    rates = response.rates
    return response.model_copy(update = {
        'fx_gap': round((rates.usdt / rates.usd - 1) * _PERCENT, 2) if rates else None})
