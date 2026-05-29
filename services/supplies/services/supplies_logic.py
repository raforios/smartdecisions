'''
    Domain logic for the Supplies service.

    Centralizes:
        - The supply-request state machine and the per-role permissions
          attached to each transition.
        - Stock validation against the configured minimum.
        - Append-only kardex insertion together with the materialized
          balance update on Item.

    Kept framework-free on purpose: controllers wire HTTP I/O, this module
    encodes the business rules.
'''
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from models.supplies import (
    Item,
    KardexMovement,
    Request,
    RequestStatusHistory,
)
from schemas.enums import (
    MovementTypeEnum,
    ReferenceTypeEnum,
    RequestStatusEnum,
    RoleEnum,
)
from services.exceptions import (
    ForbiddenError,
    InvalidInputError,
    RegisterNotFoundError,
)
from services.logger_config import custom_logger as logger
from services.utils import get_current_time_gmt


# --------------------------------------------------------------------------- #
# Request state machine                                                       #
# --------------------------------------------------------------------------- #
# Maps each transition to the roles allowed to perform it. Used both by the
# controllers (for permission checks) and by the unit tests (as documentation
# of expected behavior).
ALLOWED_TRANSITIONS: dict[tuple[RequestStatusEnum, RequestStatusEnum], tuple[RoleEnum, ...]] = {
    (RequestStatusEnum.CREATED, RequestStatusEnum.IN_PROCESS): (
        RoleEnum.WAREHOUSE_MANAGER, RoleEnum.ADMIN,
    ),
    (RequestStatusEnum.IN_PROCESS, RequestStatusEnum.DELIVERED): (
        RoleEnum.WAREHOUSE_MANAGER, RoleEnum.ADMIN,
    ),
    (RequestStatusEnum.IN_PROCESS, RequestStatusEnum.REJECTED): (
        RoleEnum.WAREHOUSE_MANAGER, RoleEnum.ADMIN,
    ),
    (RequestStatusEnum.IN_PROCESS, RequestStatusEnum.CANCELLED): (
        RoleEnum.WAREHOUSE_MANAGER, RoleEnum.ADMIN,
    ),
    (RequestStatusEnum.DELIVERED, RequestStatusEnum.CLOSED): (
        RoleEnum.REQUESTER, RoleEnum.ADMIN,
    ),
}


def assert_transition_allowed(
    current: RequestStatusEnum,
    target: RequestStatusEnum,
    role: str,
) -> None:
    '''
        Raises InvalidInputError if the transition is not part of the state
        machine, or ForbiddenError if the role cannot perform it.
    '''
    allowed_roles = ALLOWED_TRANSITIONS.get((current, target))
    if allowed_roles is None:
        raise InvalidInputError(
            detail = f'Transition {current.value} -> {target.value} is not allowed.'
        )
    if role not in {r.value for r in allowed_roles}:
        raise ForbiddenError(
            detail = (
                f'Role "{role}" cannot move a request from '
                f'{current.value} to {target.value}.'
            )
        )


def assert_can_delete_request(
    request: Request,
    requester_email: str,
    role: str,
) -> None:
    '''
        Raises if the request cannot be physically deleted by the caller.
        Only CREATED requests can be deleted, and only by the original
        REQUESTER or an ADMIN.
    '''
    if request.status != RequestStatusEnum.CREATED:
        raise InvalidInputError(
            detail = (
                f'Only CREATED requests can be deleted. Current status: '
                f'{request.status.value}.'
            )
        )
    is_owner = request.requester_email == requester_email
    is_admin = role == RoleEnum.ADMIN.value
    if not (is_owner or is_admin):
        raise ForbiddenError(
            detail = 'Only the original requester or an ADMIN can delete a request.'
        )


def record_status_change(
    db: Session,
    request: Request,
    new_status: RequestStatusEnum,
    changed_by: str,
    reason: Optional[str] = None,
) -> None:
    '''
        Updates the request status and appends a status-history row inside
        the same transaction. Caller is responsible for db.commit().
    '''
    history = RequestStatusHistory(
        request_id = request.id,
        from_status = request.status,
        to_status = new_status,
        changed_by = changed_by,
        reason = reason,
    )
    db.add(history)
    request.status = new_status

    timestamp = get_current_time_gmt()
    if new_status == RequestStatusEnum.IN_PROCESS:
        request.processed_at = timestamp
        request.processed_by = changed_by
    elif new_status == RequestStatusEnum.DELIVERED:
        request.delivered_at = timestamp
        request.delivered_by = changed_by
    elif new_status == RequestStatusEnum.CLOSED:
        request.closed_at = timestamp


# --------------------------------------------------------------------------- #
# Stock validation                                                            #
# --------------------------------------------------------------------------- #
def assert_item_requestable(item: Item, requested_qty: Decimal) -> None:
    '''
        Enforces the business rules for putting an item into a request:
            - the item must be active,
            - its current_stock must be strictly above the minimum,
            - the requested quantity cannot push the stock at or below the
              minimum (current_stock - requested_qty > min_stock).
    '''
    if not item.is_active:
        raise InvalidInputError(detail = f'Item {item.code} is inactive.')

    if item.current_stock <= item.min_stock:
        raise InvalidInputError(
            detail = (
                f'Item {item.code} is at or below the minimum stock '
                f'({item.current_stock}/{item.min_stock}); it cannot be requested.'
            )
        )

    available = item.current_stock - item.min_stock
    if requested_qty > available:
        raise InvalidInputError(
            detail = (
                f'Requested quantity {requested_qty} for item {item.code} '
                f'exceeds the available buffer above the minimum ({available}).'
            )
        )


# --------------------------------------------------------------------------- #
# Kardex                                                                      #
# --------------------------------------------------------------------------- #
def post_kardex_movement(
    db: Session,
    item: Item,
    movement_type: MovementTypeEnum,
    reference_type: ReferenceTypeEnum,
    reference_id: Optional[int],
    quantity: Decimal,
    created_by: str,
    batch_code: Optional[str] = None,
    notes: Optional[str] = None,
) -> KardexMovement:
    '''
        Appends a kardex row and updates the materialized current_stock.

        Quantity is always positive in storage; the sign of the operation is
        encoded by movement_type:
            IN          -> add to balance
            OUT         -> subtract from balance
            ADJUSTMENT  -> add (signed) to balance, allowing corrections

        For ADJUSTMENT the caller may pass a negative quantity to subtract.
        For IN/OUT the quantity must be positive.

        Caller is responsible for db.commit().
    '''
    if movement_type in (MovementTypeEnum.IN, MovementTypeEnum.OUT) and quantity <= 0:
        raise InvalidInputError(detail = 'Quantity must be positive for IN/OUT movements.')

    balance_before = Decimal(item.current_stock)

    if movement_type == MovementTypeEnum.IN:
        delta = quantity
    elif movement_type == MovementTypeEnum.OUT:
        delta = -quantity
    else:
        delta = quantity

    new_balance = balance_before + delta
    if new_balance < 0:
        raise InvalidInputError(
            detail = (
                f'Movement would leave item {item.code} with negative stock '
                f'({new_balance}). Operation rejected.'
            )
        )

    movement = KardexMovement(
        item_id = item.id,
        movement_type = movement_type,
        reference_type = reference_type,
        reference_id = reference_id,
        quantity = abs(quantity) if movement_type != MovementTypeEnum.ADJUSTMENT else quantity,
        balance_before = balance_before,
        balance_after = new_balance,
        batch_code = batch_code,
        notes = notes,
        created_by = created_by,
    )
    db.add(movement)
    item.current_stock = new_balance

    message = (
        f'Kardex {movement_type.value} for item {item.code}: '
        f'{balance_before} -> {new_balance} (qty={quantity}, ref={reference_type.value}'
        f'#{reference_id})'
    )
    logger.info(message)
    return movement


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #
def fetch_active_item(db: Session, item_id: int) -> Item:
    '''
        Returns an active item or raises RegisterNotFoundError / InvalidInputError.
    '''
    item = db.query(Item).filter(Item.id == item_id).first()
    if item is None:
        raise RegisterNotFoundError(detail = f'Item with id {item_id} not found.')
    if not item.is_active:
        raise InvalidInputError(detail = f'Item {item.code} is inactive.')
    return item


def collect_role_from_payload(payload: dict) -> str:
    '''
        Extracts the role claim from a JWT payload, raising ForbiddenError if
        absent. Used by controllers that need both email and role.
    '''
    role = payload.get('role')
    if not role:
        raise ForbiddenError(detail = 'JWT is missing the "role" claim.')
    return role


def assert_role_in(role: str, allowed: Iterable[RoleEnum]) -> None:
    '''
        Convenience guard used inside controllers when require_roles cannot
        be expressed declaratively at the route level.
    '''
    allowed_values = {r.value for r in allowed}
    if role not in allowed_values:
        raise ForbiddenError(
            detail = f'Role "{role}" is not authorized. Allowed: {sorted(allowed_values)}.'
        )
