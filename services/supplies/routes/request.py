'''
    Routes for supply requests (flow 1: REQUESTER, flow 2: WAREHOUSE_MANAGER).
'''
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from controllers.request import (
    cancel_request_controller,
    close_request_controller,
    create_request_controller,
    delete_request_controller,
    deliver_request_controller,
    get_request_controller,
    list_requests_controller,
    process_request_controller,
    reject_request_controller,
)
from schemas.enums import RequestStatusEnum, RoleEnum
from schemas.request import (
    RequestCreateSchema,
    RequestDeliverSchema,
    RequestDetailedResponseSchema,
    RequestFilterSchema,
    RequestResponseSchema,
    RequestTransitionSchema,
)
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_payload, require_roles


router = APIRouter(prefix = '/v1/supplies', tags = ['Requests'])


def _payload_email_role(payload: Dict[str, str]) -> tuple[str, str]:
    '''
        Extracts the (email, role) tuple from a JWT payload. Helper used by
        every transition endpoint.
    '''
    return payload.get('email'), payload.get('role')


@router.post(
    '/requests',
    response_model = RequestDetailedResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a supply request (flow 1)',
)
async def create_request(
    payload: RequestCreateSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    jwt_payload: Dict[str, str] = Depends(get_current_payload),
):
    '''
        Creates a new supply request. Any authenticated user may request,
        but stock validation rules apply.
    '''
    email, _ = _payload_email_role(jwt_payload)
    return await create_request_controller(db, payload, requester_email = email)


@router.get(
    '/requests',
    response_model = List[RequestResponseSchema],
    summary = 'List supply requests',
)
async def list_requests(
    status_filter: Optional[RequestStatusEnum] = Query(None, alias = 'status'),
    requester_email: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 500),
    db: Session = Depends(GET_DB_DEPENDENCY),
    jwt_payload: Dict[str, str] = Depends(get_current_payload),
):
    '''
        Lists supply requests with optional filters. REQUESTER callers are
        restricted to their own requests; WAREHOUSE_MANAGER and ADMIN can
        see everything.
    '''
    email, role = _payload_email_role(jwt_payload)
    filters = RequestFilterSchema(
        status = status_filter,
        requester_email = requester_email,
        date_from = date_from,
        date_to = date_to,
    )
    return await list_requests_controller(
        db, filters, current_role = role, current_email = email, skip = skip, limit = limit,
    )


@router.get(
    '/requests/{request_id}',
    response_model = RequestDetailedResponseSchema,
    summary = 'Get a supply request with its details and history',
)
async def get_request(
    request_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    jwt_payload: Dict[str, str] = Depends(get_current_payload),
):
    '''
        Returns a request with details and full status history. REQUESTER
        callers cannot access requests created by others.
    '''
    email, role = _payload_email_role(jwt_payload)
    return await get_request_controller(db, request_id, current_role = role, current_email = email)


@router.delete(
    '/requests/{request_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a CREATED supply request',
)
async def delete_request(
    request_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    jwt_payload: Dict[str, str] = Depends(get_current_payload),
):
    '''
        Hard-deletes a CREATED request. Only the requester or an ADMIN may
        delete; in any other state, use the transition endpoints.
    '''
    email, role = _payload_email_role(jwt_payload)
    deleted = await delete_request_controller(
        db, request_id, current_role = role, current_email = email,
    )
    return {'deleted_id': deleted}


# --------------------------------------------------------------------------- #
# State transitions                                                           #
# --------------------------------------------------------------------------- #
@router.patch(
    '/requests/{request_id}/process',
    response_model = RequestDetailedResponseSchema,
    summary = 'CREATED -> IN_PROCESS',
)
async def process_request(
    request_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
    payload: Dict[str, str] = Depends(get_current_payload),
):
    '''
        Moves a CREATED request to IN_PROCESS after re-validating stock.
    '''
    email, role = _payload_email_role(payload)
    return await process_request_controller(
        db, request_id, current_role = role, current_email = email,
    )


@router.patch(
    '/requests/{request_id}/deliver',
    response_model = RequestDetailedResponseSchema,
    summary = 'IN_PROCESS -> DELIVERED (posts kardex OUT)',
)
async def deliver_request(
    request_id: int,
    body: RequestDeliverSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
    payload: Dict[str, str] = Depends(get_current_payload),
):
    '''
        Delivers a request, posting OUT kardex movements per line item.
    '''
    email, role = _payload_email_role(payload)
    return await deliver_request_controller(
        db, request_id, body, current_role = role, current_email = email,
    )


@router.patch(
    '/requests/{request_id}/close',
    response_model = RequestDetailedResponseSchema,
    summary = 'DELIVERED -> CLOSED (requester conformity)',
)
async def close_request(
    request_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    jwt_payload: Dict[str, str] = Depends(get_current_payload),
):
    '''
        Closes a DELIVERED request. Only the original requester or an ADMIN
        may close it.
    '''
    email, role = _payload_email_role(jwt_payload)
    return await close_request_controller(
        db, request_id, current_role = role, current_email = email,
    )


@router.patch(
    '/requests/{request_id}/reject',
    response_model = RequestDetailedResponseSchema,
    summary = 'IN_PROCESS -> REJECTED',
)
async def reject_request(
    request_id: int,
    body: RequestTransitionSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
    payload: Dict[str, str] = Depends(get_current_payload),
):
    '''
        Rejects a request with a mandatory textual reason.
    '''
    email, role = _payload_email_role(payload)
    return await reject_request_controller(
        db, request_id, body, current_role = role, current_email = email,
    )


@router.patch(
    '/requests/{request_id}/cancel',
    response_model = RequestDetailedResponseSchema,
    summary = 'IN_PROCESS -> CANCELLED',
)
async def cancel_request(
    request_id: int,
    body: RequestTransitionSchema,
    db: Session = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value, RoleEnum.WAREHOUSE_MANAGER.value)),
    payload: Dict[str, str] = Depends(get_current_payload),
):
    '''
        Annuls an IN_PROCESS request with an optional reason.
    '''
    email, role = _payload_email_role(payload)
    return await cancel_request_controller(
        db, request_id, body, current_role = role, current_email = email,
    )
