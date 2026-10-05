'''
    Cash tills: orchestration between the HTTP layer and the services.

    Same contract as `controllers/billing.py`: every controller carries
    `@handle_service_errors`, and every one that changes a till carries
    `@audit_event`, so who opened, took cash out, cancelled or closed a till is
    on record.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.billing_cash import (
    CashAlertsResponse,
    CashOpenIn,
    CashSessionOut,
    CashSessionsResponse,
    TillClose,
    TillExpense,
    TillExpenseRef,
    TillQuery,
    TillRef
)
from services import billing_cash
from services.billing_cash import TillFilter, Viewer
from services.utils import audit_event, handle_service_errors

SERVICE = 'BILLING'


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'CashSession', 'OPEN')
async def open_till_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    opening: CashOpenIn,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CashSessionOut:
    '''
        Opens the caller's till with the cash counted in the drawer.
    '''
    return billing_cash.open_session(dynamodb_resource, owner, current_user, opening)


@handle_service_errors(SERVICE)
async def current_till_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CashSessionOut:
    '''
        The caller's open till and its count.
    '''
    return billing_cash.current_session(dynamodb_resource, owner, current_user)


@handle_service_errors(SERVICE)
async def list_tills_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    query: TillQuery,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CashSessionsResponse:
    '''
        The tills of the shop: every user's for a manager, their own otherwise.
    '''
    return billing_cash.list_sessions(
        dynamodb_resource, owner, Viewer(current_user, query.is_manager),
        TillFilter(
            user_email = query.user_email,
            date_from = query.date_from.isoformat() if query.date_from else None,
            date_to = query.date_to.isoformat() if query.date_to else None
        )
    )


@handle_service_errors(SERVICE)
async def get_till_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    ref: TillRef,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CashSessionOut:
    '''
        One till and its count, for its user or a manager.
    '''
    return billing_cash.get_session(dynamodb_resource, owner,
                                    Viewer(current_user, ref.is_manager), ref.session_id)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'CashSession', 'EXPENSE')
async def add_expense_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    target: TillExpense,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CashSessionOut:
    '''
        Records cash leaving the caller's open till.
    '''
    return billing_cash.add_expense(dynamodb_resource, owner, current_user,
                                    target.session_id, target.expense)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'CashSession', 'CANCEL_EXPENSE')
async def cancel_expense_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    target: TillExpenseRef,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CashSessionOut:
    '''
        Cancels an expense of the caller's open till.
    '''
    return billing_cash.cancel_expense(dynamodb_resource, owner, current_user,
                                       target.session_id, target.movement_id)


@handle_service_errors(SERVICE)
@audit_event(SERVICE, 'CashSession', 'CLOSE')
async def close_till_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    target: TillClose,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CashSessionOut:
    '''
        Closes a till against the cash counted.
    '''
    return billing_cash.close_session(dynamodb_resource, owner,
                                      Viewer(current_user, target.is_manager),
                                      target.session_id, target.closing)


@handle_service_errors(SERVICE)
async def till_alerts_controller(
    dynamodb_resource: ServiceResource,
    owner: str,
    is_manager: bool,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> CashAlertsResponse:
    '''
        The tills to close now.
    '''
    return billing_cash.cash_alerts(dynamodb_resource, owner,
                                    Viewer(current_user, is_manager))
