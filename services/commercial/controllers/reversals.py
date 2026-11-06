'''
    Cancellations and returns: recorded apart, and the sale they undid set
    right in the company's latest dataset, so the analysis counts net sales
    (Rafael, 6-nov-2026).
'''
from typing import Any

from boto3.resources.base import ServiceResource
from fastapi import Request

from controllers.sales_load import replace_order_lines
from schemas.reversals import ReversalResponse, ReversalSchema, ReversalsReport
from services.commercial_utils import get_owned_dataset, list_datasets_for_owner
from services.reversals import build_report, list_reversals, store_reversal, to_reversal_response
from services.utils import audit_event, handle_service_errors


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Reversal', 'UPLOAD', id_field = 'reversal_id')
async def record_reversal_controller(
    dynamodb_resource: ServiceResource,
    reversal: ReversalSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> ReversalResponse:
    '''
        Records a cancellation or a return —or its reversion— and leaves the
        sale in the latest dataset as it now stands. Sales arrive as they
        happen into the latest dataset, so that is where the sale is; a
        company with no dataset only keeps the record.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            reversal (ReversalSchema): What was undone and the sale after it.
            current_user (str): Authenticated caller, owner of the data.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ReversalResponse: The record, and the dataset set right.
    '''
    item = store_reversal(dynamodb_resource, current_user, reversal)
    latest = list_datasets_for_owner(dynamodb_resource, current_user, limit = 1)
    if not latest:
        return to_reversal_response(item)
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = str(latest[0]['dataset_id']),
        owner_email = current_user
    )
    replace_order_lines(dynamodb_resource, dataset, reversal.order_id, reversal.rows,
                        auth_token)
    return to_reversal_response(item, str(dataset['dataset_id']))


@handle_service_errors('COMMERCIAL')
async def reversals_report_controller(
    dynamodb_resource: ServiceResource,
    params: dict[str, Any],
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ReversalsReport:
    '''
        The company's cancellations and returns in the window.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            params (dict[str, Any]): The window and the caller's token.
            current_user (str): Authenticated caller, owner of the data.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ReversalsReport: Totals by month and by reason, and every record.
    '''
    return build_report(list_reversals(dynamodb_resource, current_user, params),
                        params['auth_token'])
