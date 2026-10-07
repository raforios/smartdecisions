'''
    Cash tills: HTTP layer.

    Anybody at the counter opens, moves and closes their own till; a manager
    sees every till of the shop and may close somebody else's with a note. The
    owner is the shop the token names and the user is the token's e-mail:
    neither is a parameter.
'''
from datetime import date as date_type
from typing import Any

from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Path, Query, Request, status

from controllers.billing_cash import (
    add_expense_controller,
    cancel_expense_controller,
    close_till_controller,
    current_till_controller,
    get_till_controller,
    list_tills_controller,
    open_till_controller,
    till_alerts_controller
)
from schemas.billing_cash import (
    CashAlertsResponse,
    CashCloseIn,
    CashOpenIn,
    CashSessionOut,
    CashSessionsResponse,
    ExpenseIn,
    TillClose,
    TillExpense,
    TillExpenseRef,
    TillQuery,
    TillRef
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner, get_current_payload, get_current_user

router = APIRouter(prefix = '/v1/billing/cash', tags = ['Billing — cash tills'])

# Roles that see every till of the shop. Same pair that runs the shop in
# `routes/billing.py`.
MANAGERS = ('ADMIN', 'MANAGER')

SESSION_ID = Path(..., min_length = 1, max_length = 120, description = 'The till.')


def is_manager(payload: dict[str, Any] = Depends(get_current_payload)) -> bool:
    '''
        Whether the caller sees every till of the shop.

        Args:
            payload (dict[str, Any]): Decoded token claims.

        Returns:
            bool: True for a manager.
    '''
    return payload.get('role') in MANAGERS


def till_query(
    manager: bool = Depends(is_manager),
    user_email: str | None = Query(None, description = 'Only this user (managers).'),
    date_from: date_type | None = Query(None, description = 'First day.'),
    date_to: date_type | None = Query(None, description = 'Last day.')
) -> TillQuery:
    '''
        The filters of a till list, as one argument.

        Returns:
            TillQuery: Who asks and what to narrow to.
    '''
    return TillQuery(is_manager = manager, user_email = user_email,
                     date_from = date_from, date_to = date_to)


def till_ref(
    session_id: str = SESSION_ID,
    manager: bool = Depends(is_manager)
) -> TillRef:
    '''
        One till and whether the caller sees every till, as one argument.

        Returns:
            TillRef: The till and the caller's reach.
    '''
    return TillRef(session_id = session_id, is_manager = manager)


def till_expense(
    expense: ExpenseIn,
    session_id: str = SESSION_ID
) -> TillExpense:
    '''
        The expense and the till it leaves, as one argument.

        Returns:
            TillExpense: Both together.
    '''
    return TillExpense(session_id = session_id, expense = expense)


def till_expense_ref(
    session_id: str = SESSION_ID,
    movement_id: str = Path(..., min_length = 1, max_length = 60)
) -> TillExpenseRef:
    '''
        One expense of one till, as one argument.

        Returns:
            TillExpenseRef: The till and the expense.
    '''
    return TillExpenseRef(session_id = session_id, movement_id = movement_id)


def till_close(
    closing: CashCloseIn,
    session_id: str = SESSION_ID,
    manager: bool = Depends(is_manager)
) -> TillClose:
    '''
        The closing of one till, by its user or a manager, as one argument.

        Returns:
            TillClose: The till, the caller's reach and the count.
    '''
    return TillClose(session_id = session_id, is_manager = manager, closing = closing)


@router.post('/sessions', response_model = CashSessionOut,
             status_code = status.HTTP_201_CREATED)
async def open_till_endpoint(
    request: Request,
    opening: CashOpenIn,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> CashSessionOut:
    ''' Endpoint to open the caller's till. '''
    message = f'{current_user} opens a till in {owner}.'
    logger.info(message)
    return await open_till_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, opening = opening,
        request = request, current_user = current_user
    )


@router.get('/sessions/current', response_model = CashSessionOut)
async def current_till_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> CashSessionOut:
    ''' Endpoint for the caller's open till. '''
    return await current_till_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        request = request, current_user = current_user
    )


@router.get('/sessions', response_model = CashSessionsResponse)
async def list_tills_endpoint(
    request: Request,
    query: TillQuery = Depends(till_query),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> CashSessionsResponse:
    ''' Endpoint for the tills of the shop. '''
    return await list_tills_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, query = query,
        request = request, current_user = current_user
    )


@router.get('/sessions/{session_id}', response_model = CashSessionOut)
async def get_till_endpoint(
    request: Request,
    ref: TillRef = Depends(till_ref),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> CashSessionOut:
    ''' Endpoint for one till and its count. '''
    return await get_till_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        ref = ref,
        request = request, current_user = current_user
    )


@router.post('/sessions/{session_id}/expenses', response_model = CashSessionOut,
             status_code = status.HTTP_201_CREATED)
async def add_expense_endpoint(
    request: Request,
    target: TillExpense = Depends(till_expense),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> CashSessionOut:
    ''' Endpoint to take cash out of the caller's open till. '''
    message = (f'{current_user} takes {target.expense.amount} '
               f'out of till {target.session_id}.')
    logger.info(message)
    return await add_expense_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        target = target,
        request = request, current_user = current_user
    )


@router.post('/sessions/{session_id}/expenses/{movement_id}/cancel',
             response_model = CashSessionOut)
async def cancel_expense_endpoint(
    request: Request,
    target: TillExpenseRef = Depends(till_expense_ref),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> CashSessionOut:
    ''' Endpoint to cancel an expense of the caller's open till. '''
    message = (f'{current_user} cancels expense {target.movement_id} '
               f'of till {target.session_id}.')
    logger.info(message)
    return await cancel_expense_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        target = target,
        request = request, current_user = current_user
    )


@router.post('/sessions/{session_id}/close', response_model = CashSessionOut)
async def close_till_endpoint(
    request: Request,
    target: TillClose = Depends(till_close),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> CashSessionOut:
    ''' Endpoint to close a till against the cash counted. '''
    message = (f'{current_user} closes till {target.session_id} '
               f'counting {target.closing.counted_cash}.')
    logger.info(message)
    return await close_till_controller(
        dynamodb_resource = dynamodb_resource, owner = owner,
        target = target,
        request = request, current_user = current_user
    )


@router.get('/alerts', response_model = CashAlertsResponse)
async def till_alerts_endpoint(
    request: Request,
    manager: bool = Depends(is_manager),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    owner: str = Depends(get_current_owner),
    current_user: str = Depends(get_current_user)
) -> CashAlertsResponse:
    ''' Endpoint for the tills to close now. '''
    return await till_alerts_controller(
        dynamodb_resource = dynamodb_resource, owner = owner, is_manager = manager,
        request = request, current_user = current_user
    )
