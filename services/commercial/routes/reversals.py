'''
    Cancellations and returns — HTTP layer: a system records each one, and
    the manager reads them by month and by reason.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Header, Request, status

from controllers.reversals import record_reversal_controller, reversals_report_controller
from routes.analytics import DateWindow
from schemas.reversals import ReversalResponse, ReversalSchema, ReversalsReport
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner

router = APIRouter(prefix = '/v1/commercial/reversals', tags = ['Cancellations and returns'])

# A FastAPI endpoint declares its dependencies as parameters —resource,
# token, caller, body— so the five-argument budget does not describe it.
# pylint: disable=too-many-arguments, too-many-positional-arguments


@router.post(
    '',
    response_model = ReversalResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Record a cancellation or a return',
    description = (
        'Records what was undone —the whole sale, or some of its units— and '
        'replaces the sale\'s lines in the company\'s latest dataset with '
        '`rows`, what the buyer kept (nothing when cancelled), so the analysis '
        'counts net sales. Sending the same id again with state REVERTED '
        'keeps the record and stops counting it; send the sale\'s lines as '
        'they stand again in `rows`.'
    )
)
async def record_reversal_endpoint(
    request: Request,
    reversal: ReversalSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    authorization: str = Header(None),
    current_user: str = Depends(get_current_owner)
) -> ReversalResponse:
    '''
        Endpoint recording a cancellation or a return.
    '''
    message = (f'User: {current_user}. {reversal.kind.value} {reversal.reversal_id} '
               f'{reversal.state.value}.')
    logger.info(message)
    return await record_reversal_controller(
        dynamodb_resource = dynamodb_resource,
        reversal = reversal,
        current_user = current_user,
        auth_token = authorization,
        request = request
    )


@router.get(
    '',
    response_model = ReversalsReport,
    status_code = status.HTTP_200_OK,
    summary = 'Cancellations and returns, by month and by reason',
    description = (
        'Totals of what stands —each month at its close, the reasons at '
        'today\'s rate, in bolivianos, official dollars and USDT— and every '
        'record of the window, reverted ones included.'
    )
)
async def reversals_report_endpoint(
    request: Request,
    window: DateWindow = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> ReversalsReport:
    '''
        Endpoint returning the cancellations and returns of a window.
    '''
    return await reversals_report_controller(
        dynamodb_resource = dynamodb_resource,
        params = window.as_params(),
        current_user = current_user,
        request = request
    )
