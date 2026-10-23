'''
    ANALYTICS: the clients of a dataset and the card of one of them.
'''
from typing import Any

import pandas as pd
from boto3.resources.base import ServiceResource
from fastapi import Request

from controllers.analytics import _at_month_close, _payments_of, _scoped_dataframe
from schemas.analytics import AnalyticsError
from schemas.client import ClientCardResponse, ClientListResponse
from services.analytics_utils import ORDER, get_credit_policy, get_dataset_metadata
from services.client_card import (
    build_client_list,
    build_client_receivable,
    build_profile,
    build_timeline,
    client_rows,
    default_term_days
)
from services.currency import in_three_currencies
from services.exceptions import ResourceNotFoundError
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt, handle_service_errors


def _today_rates(
    response_type: type,
    payload: dict[str, Any],
    params: dict[str, Any] | None
) -> Any:
    '''
        The response with its amounts also at today's rate.

        Args:
            response_type (type): The response DTO.
            payload (dict[str, Any]): Its fields, amounts in bolivianos.
            params (dict | None): The request options, for the caller's token.

        Returns:
            Any: The response.
    '''
    return in_three_currencies(response_type, payload, (params or {}).get('auth_token') or '',
                               get_current_time_gmt().date().isoformat())


@handle_service_errors('COMMERCIAL')
async def client_list_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: dict[str, Any],
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ClientListResponse:
    '''
        Every client of the dataset, the largest first, to open its card.
    '''
    dataframe, _ = _scoped_dataframe(dynamodb_resource, dataset_id, current_user, params)
    clients = [row.model_dump() for row in build_client_list(dataframe)]
    return _today_rates(ClientListResponse, {'dataset_id': dataset_id, 'clients': clients},
                        params)


@handle_service_errors('COMMERCIAL')
async def client_card_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    client_id: str,
    params: dict[str, Any],
    current_user: str
) -> ClientCardResponse:
    '''
        Everything about one client, and the timeline of its invoices and
        payments. A client not in the dataset answers CLIENT_NOT_FOUND.
    '''
    dataframe, _ = _scoped_dataframe(dynamodb_resource, dataset_id, current_user, params)
    rows = client_rows(dataframe, client_id)
    if rows.empty:
        error_msg = f'Client {client_id} is not in dataset {dataset_id}.'
        logger.warning(error_msg)
        raise ResourceNotFoundError(detail = AnalyticsError.CLIENT_NOT_FOUND.value)
    metadata = get_dataset_metadata(dynamodb_resource = dynamodb_resource,
                                    dataset_id = dataset_id, owner_email = current_user)
    payments = _payments_of(metadata, (params or {}).get('auth_token') or '')
    if payments is not None and ORDER in rows.columns:
        payments = payments.loc[payments[ORDER].isin(rows[ORDER])]
    policy = get_credit_policy(dynamodb_resource = dynamodb_resource,
                               owner_email = current_user)
    timeline = build_timeline(rows, payments, default_term_days(policy))
    as_of = pd.to_datetime(dataframe['date'], errors = 'coerce').max()
    return _today_rates(ClientCardResponse, {
        'dataset_id': dataset_id, 'client_id': client_id,
        **build_profile(_at_month_close(rows, params), as_of),
        'receivable': build_client_receivable(rows, payments, policy, timeline).model_dump(),
        'timeline': [entry.model_dump() for entry in timeline]
    }, params)
