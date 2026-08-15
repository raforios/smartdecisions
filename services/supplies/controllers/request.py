'''
    Controllers for supply requests.

    Implements both flows:
        - Flow 1 (REQUESTER): creates a request, deletes own CREATED requests,
          confirms delivery (CLOSED).
        - Flow 2 (WAREHOUSE_MANAGER / ADMIN): processes, rejects, cancels and
          delivers requests; the DELIVERED transition consumes stock through
          the kardex.
'''
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from sqlalchemy.orm import Session, joinedload

from models.supplies import Item, Request, RequestDetail
from schemas.enums import (
    ReferenceTypeEnum,
    RequestStatusEnum,
    RoleEnum,
)
from schemas.request import (
    RequestCreateSchema,
    RequestDeliverSchema,
    RequestDetailedResponseSchema,
    RequestDetailResponseSchema,
    RequestFilterSchema,
    RequestResponseSchema,
    RequestStatusHistorySchema,
    RequestTransitionSchema,
)
from services.exceptions import (
    ForbiddenError,
    InvalidInputError,
    RegisterNotFoundError,
)
from services.logger_config import custom_logger as logger
from services.supplies_logic import (
    MovementReference,
    OutflowSpec,
    assert_can_delete_request,
    assert_item_deliverable,
    assert_item_requestable,
    assert_role_in,
    assert_transition_allowed,
    commit_or_conflict,
    consume_stock_fifo,
    record_status_change,
    release_request_reservations,
    release_stock,
    reserve_stock,
)


def _generate_request_code(db: Session) -> str:
    '''
        Builds SOL-YYYY-XXXXXX codes for requests.
    '''
    last = db.query(Request).order_by(Request.id.desc()).first()
    next_id = (last.id + 1) if last else 1
    year = datetime.now().year
    return f'SOL-{year}-{next_id:06d}'


def _serialize_request(record: Request) -> RequestResponseSchema:
    '''
        Lightweight serializer used by list endpoints.
    '''
    return RequestResponseSchema.model_validate(record)


def _serialize_line(detail: RequestDetail) -> RequestDetailResponseSchema:
    '''
        Line of a request, resolving the item identity the printable forms
        need (code, description and unit).
    '''
    item = detail.item
    return RequestDetailResponseSchema(
        id = detail.id,
        item_id = detail.item_id,
        item_code = item.code if item else None,
        item_name = item.name if item else None,
        unit = item.unit.abbreviation if item and item.unit else None,
        requested_qty = detail.requested_qty,
        delivered_qty = detail.delivered_qty,
    )


def _serialize_detailed(record: Request) -> RequestDetailedResponseSchema:
    '''
        Includes line items and the full status history.
    '''
    return RequestDetailedResponseSchema(
        id = record.id,
        code = record.code,
        requester_email = record.requester_email,
        requester_name = record.requester_name,
        requester_position = record.requester_position,
        requester_unit = record.requester_unit,
        status = record.status,
        notes = record.notes,
        requested_at = record.requested_at,
        processed_at = record.processed_at,
        processed_by = record.processed_by,
        delivered_at = record.delivered_at,
        delivered_by = record.delivered_by,
        closed_at = record.closed_at,
        details = [_serialize_line(d) for d in record.details],
        status_history = [
            RequestStatusHistorySchema.model_validate(h) for h in record.status_history
        ],
    )


def _delivery_note(record: Request) -> str:
    '''
        Builds the kardex note for a delivery.

        Names the person and unit that received the material, the way the
        legacy NSIAF kardex did, falling back to the request code alone for
        older requests that carry no requester identity.

        Args:
            record (Request): Request being delivered.

        Returns:
            str: Note stored on every OUT movement of this delivery.
    '''
    who = ' - '.join(part for part in (
        record.requester_name, record.requester_position, record.requester_unit,
    ) if part)
    if not who:
        return f'Entrega de solicitud {record.code}'
    return f'Entrega {record.code} · {who}'


# --------------------------------------------------------------------------- #
# Create                                                                      #
# --------------------------------------------------------------------------- #
async def create_request_controller(
    db: Session, payload: RequestCreateSchema, requester_email: str
) -> RequestDetailedResponseSchema:
    '''
        Creates a request after validating that every requested item is
        active, above its minimum stock, and that the requested quantity
        leaves room above the minimum.
    '''
    # Aggregate quantities per item so a payload that lists the same item
    # twice is checked against the total demand, not each entry in isolation.
    aggregated: Dict[int, Decimal] = {}
    for detail in payload.details:
        aggregated[detail.item_id] = aggregated.get(detail.item_id, Decimal('0')) \
                                     + detail.requested_qty

    items_by_id: Dict[int, Item] = {}
    for item_id, total_qty in aggregated.items():
        item = db.query(Item).filter(Item.id == item_id).first()
        if item is None:
            raise RegisterNotFoundError(detail = f'Item {item_id} not found.')
        assert_item_requestable(item, total_qty)
        items_by_id[item_id] = item

    record = Request(
        code = _generate_request_code(db),
        requester_email = requester_email,
        requester_name = payload.requester_name,
        requester_position = payload.requester_position,
        requester_unit = payload.requester_unit,
        status = RequestStatusEnum.CREATED,
        notes = payload.notes,
    )
    db.add(record)
    db.flush()

    # Preserve the original detail rows from the payload so callers retain
    # the line-level breakdown (no implicit aggregation in storage).
    for detail in payload.details:
        db.add(RequestDetail(
            request_id = record.id,
            item_id = detail.item_id,
            requested_qty = detail.requested_qty,
        ))

    # Hold the units from this moment on: the next request must see them gone.
    for item_id, total_qty in aggregated.items():
        reserve_stock(items_by_id[item_id], total_qty)
        db.add(items_by_id[item_id])

    record_status_change(
        db = db,
        request = record,
        new_status = RequestStatusEnum.CREATED,
        changed_by = requester_email,
    )

    commit_or_conflict(db, 'Request detail collision (duplicated item lines).')

    db.refresh(record)
    message = f'Request {record.code} created by {requester_email}.'
    logger.info(message)
    return _serialize_detailed(record)


# --------------------------------------------------------------------------- #
# Read                                                                        #
# --------------------------------------------------------------------------- #
async def list_requests_controller(
    db: Session, filters: RequestFilterSchema, current_role: str, current_email: str
) -> List[RequestResponseSchema]:
    '''
        Lists requests.

        REQUESTER callers are restricted to their own requests; warehouse
        and admin roles can see everything and can narrow down with filters.
    '''
    query = db.query(Request)
    if current_role == RoleEnum.REQUESTER.value:
        query = query.filter(Request.requester_email == current_email)
    elif filters.requester_email:
        query = query.filter(Request.requester_email == filters.requester_email)

    if filters.status:
        query = query.filter(Request.status == filters.status)
    if filters.date_from:
        query = query.filter(Request.requested_at >= filters.date_from)
    if filters.date_to:
        query = query.filter(Request.requested_at <= filters.date_to)

    rows = (
        query.order_by(Request.requested_at.desc())
        .offset(filters.skip)
        .limit(filters.limit)
        .all()
    )
    return [_serialize_request(row) for row in rows]


async def get_request_controller(
    db: Session, request_id: int, current_role: str, current_email: str
) -> RequestDetailedResponseSchema:
    '''
        Returns a single request with its details and status history.
        REQUESTER callers cannot access requests created by others.
    '''
    record = (
        db.query(Request)
        .options(joinedload(Request.details), joinedload(Request.status_history))
        .filter(Request.id == request_id)
        .first()
    )
    if record is None:
        raise RegisterNotFoundError(detail = f'Request {request_id} not found.')

    if current_role == RoleEnum.REQUESTER.value and record.requester_email != current_email:
        raise ForbiddenError(detail = 'You cannot access requests created by other users.')

    return _serialize_detailed(record)


# --------------------------------------------------------------------------- #
# Delete                                                                      #
# --------------------------------------------------------------------------- #
async def delete_request_controller(
    db: Session, request_id: int, current_role: str, current_email: str
) -> int:
    '''
        Hard-deletes a CREATED request. Only the requester or an ADMIN may
        delete; any other state must use the transitions endpoints.
    '''
    record = db.query(Request).filter(Request.id == request_id).first()
    if record is None:
        raise RegisterNotFoundError(detail = f'Request {request_id} not found.')

    assert_can_delete_request(record, current_email, current_role)
    # Give the held units back before the lines disappear with the request.
    release_request_reservations(db, record)
    db.delete(record)
    db.commit()
    return request_id


# --------------------------------------------------------------------------- #
# Transitions                                                                 #
# --------------------------------------------------------------------------- #
async def process_request_controller(
    db: Session, request_id: int, current_role: str, current_email: str
) -> RequestDetailedResponseSchema:
    '''
        CREATED -> IN_PROCESS. Re-validates that the physical stock still
        covers every line; the reservation taken at creation stays in place.
    '''
    record = (
        db.query(Request)
        .options(joinedload(Request.details), joinedload(Request.status_history))
        .filter(Request.id == request_id)
        .first()
    )
    if record is None:
        raise RegisterNotFoundError(detail = f'Request {request_id} not found.')

    assert_transition_allowed(record.status, RequestStatusEnum.IN_PROCESS, current_role)

    for detail in record.details:
        item = db.query(Item).filter(Item.id == detail.item_id).first()
        if item is None:
            raise RegisterNotFoundError(detail = f'Item {detail.item_id} not found.')
        assert_item_deliverable(item, Decimal(detail.requested_qty))

    record_status_change(
        db = db,
        request = record,
        new_status = RequestStatusEnum.IN_PROCESS,
        changed_by = current_email,
    )
    db.commit()
    db.refresh(record)
    return _serialize_detailed(record)


async def deliver_request_controller(
    db: Session,
    request_id: int,
    payload: RequestDeliverSchema,
    current_role: str,
    current_email: str,
) -> RequestDetailedResponseSchema:
    '''
        IN_PROCESS -> DELIVERED. Posts an OUT kardex movement per item and
        records the delivered quantities on each line. Supports partial
        deliveries when payload.details is provided.
    '''
    record = (
        db.query(Request)
        .options(joinedload(Request.details), joinedload(Request.status_history))
        .filter(Request.id == request_id)
        .first()
    )
    if record is None:
        raise RegisterNotFoundError(detail = f'Request {request_id} not found.')

    assert_transition_allowed(record.status, RequestStatusEnum.DELIVERED, current_role)

    # Map declared deliveries by item; default to the requested quantity for
    # any line missing from the payload.
    overrides: Dict[int, Decimal] = {}
    if payload.details:
        for entry in payload.details:
            overrides[entry.item_id] = entry.delivered_qty

    for detail in record.details:
        delivered_qty = overrides.get(detail.item_id, Decimal(detail.requested_qty))
        if delivered_qty <= 0:
            raise InvalidInputError(
                detail = (
                    f'Delivered quantity must be positive for item '
                    f'{detail.item_id}.'
                )
            )
        if delivered_qty > Decimal(detail.requested_qty):
            raise InvalidInputError(
                detail = (
                    f'Delivered quantity ({delivered_qty}) exceeds requested '
                    f'quantity ({detail.requested_qty}) for item {detail.item_id}.'
                )
            )
        item = db.query(Item).filter(Item.id == detail.item_id).first()
        if item is None:
            raise RegisterNotFoundError(detail = f'Item {detail.item_id} not found.')
        # PEPS/FIFO: the delivery consumes cost layers oldest-first, so a
        # single line may produce several valued OUT rows in the kardex.
        consume_stock_fifo(db, item, delivered_qty, OutflowSpec(
            created_by = current_email,
            reference = MovementReference(
                kind = ReferenceTypeEnum.REQUEST, identifier = record.id),
            # Spanish on purpose: this note is shown verbatim in the kardex UI
            # and printed in the "Detalle" column of the valued kardex, where
            # the legacy system named the person who received the material.
            notes = _delivery_note(record),
        ))
        # The units left the warehouse, so the whole line stops being a
        # promise: what was delivered turned into an outflow and the
        # undelivered remainder goes back to the available pool.
        release_stock(item, Decimal(detail.requested_qty))
        db.add(item)
        detail.delivered_qty = delivered_qty
        db.add(detail)

    record_status_change(
        db = db,
        request = record,
        new_status = RequestStatusEnum.DELIVERED,
        changed_by = current_email,
        reason = payload.notes,
    )
    db.commit()
    db.refresh(record)
    return _serialize_detailed(record)


async def close_request_controller(
    db: Session, request_id: int, current_role: str, current_email: str
) -> RequestDetailedResponseSchema:
    '''
        DELIVERED -> CLOSED. Only the requester (conformity) or an ADMIN.
    '''
    record = (
        db.query(Request)
        .options(joinedload(Request.details), joinedload(Request.status_history))
        .filter(Request.id == request_id)
        .first()
    )
    if record is None:
        raise RegisterNotFoundError(detail = f'Request {request_id} not found.')

    assert_transition_allowed(record.status, RequestStatusEnum.CLOSED, current_role)
    if (current_role == RoleEnum.REQUESTER.value
            and record.requester_email != current_email):
        raise ForbiddenError(detail = 'Only the original requester can close the request.')

    record_status_change(
        db = db,
        request = record,
        new_status = RequestStatusEnum.CLOSED,
        changed_by = current_email,
    )
    db.commit()
    db.refresh(record)
    return _serialize_detailed(record)


async def reject_request_controller(
    db: Session,
    request_id: int,
    payload: RequestTransitionSchema,
    current_role: str,
    current_email: str,
) -> RequestDetailedResponseSchema:
    '''
        IN_PROCESS -> REJECTED. Reason is required to keep the trail meaningful.
    '''
    if not payload.reason:
        raise InvalidInputError(detail = 'A reason is required to reject a request.')

    record = (
        db.query(Request)
        .options(joinedload(Request.details), joinedload(Request.status_history))
        .filter(Request.id == request_id)
        .first()
    )
    if record is None:
        raise RegisterNotFoundError(detail = f'Request {request_id} not found.')

    assert_transition_allowed(record.status, RequestStatusEnum.REJECTED, current_role)
    release_request_reservations(db, record)
    record_status_change(
        db = db,
        request = record,
        new_status = RequestStatusEnum.REJECTED,
        changed_by = current_email,
        reason = payload.reason,
    )
    db.commit()
    db.refresh(record)
    return _serialize_detailed(record)


async def cancel_request_controller(
    db: Session,
    request_id: int,
    payload: RequestTransitionSchema,
    current_role: str,
    current_email: str,
) -> RequestDetailedResponseSchema:
    '''
        IN_PROCESS -> CANCELLED. Reserved for warehouse/admin annulment.
    '''
    assert_role_in(current_role, [RoleEnum.WAREHOUSE_MANAGER, RoleEnum.ADMIN])

    record = (
        db.query(Request)
        .options(joinedload(Request.details), joinedload(Request.status_history))
        .filter(Request.id == request_id)
        .first()
    )
    if record is None:
        raise RegisterNotFoundError(detail = f'Request {request_id} not found.')

    assert_transition_allowed(record.status, RequestStatusEnum.CANCELLED, current_role)
    release_request_reservations(db, record)
    record_status_change(
        db = db,
        request = record,
        new_status = RequestStatusEnum.CANCELLED,
        changed_by = current_email,
        reason = payload.reason,
    )
    db.commit()
    db.refresh(record)
    return _serialize_detailed(record)
