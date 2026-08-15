'''
    Domain logic for the Supplies service.

    Centralizes:
        - The supply-request state machine and the per-role permissions
          attached to each transition.
        - Stock validation against the configured minimum, and the stock
          reservations that keep two open requests from promising the same
          units.
        - Append-only kardex insertion together with the materialized
          balance update on Item.

    Kept framework-free on purpose: controllers wire HTTP I/O, this module
    encodes the business rules.
'''
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.supplies import (
    EntryDetail,
    Item,
    KardexMovement,
    Request,
    RequestDetail,
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
    RegisterAlreadyExistsError,
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
# Stock validation and reservations                                           #
# --------------------------------------------------------------------------- #
# Requests in these states hold their quantities reserved: the units are still
# physically in the warehouse but already promised to someone.
RESERVING_STATUSES: tuple[RequestStatusEnum, ...] = (
    RequestStatusEnum.CREATED,
    RequestStatusEnum.IN_PROCESS,
)


def available_stock(item: Item) -> Decimal:
    '''
        Units that can still be promised to a new request.

        Physical stock minus what other open requests already reserved and
        minus the minimum the warehouse must keep. Never returns a negative
        number: an over-committed item reads as 0 available, not as debt.

        Args:
            item (Item): Item to measure.

        Returns:
            Decimal: Requestable quantity, floored at zero.
    '''
    free = (Decimal(item.current_stock)
            - Decimal(item.reserved_stock or 0)
            - Decimal(item.min_stock))
    return free if free > 0 else Decimal('0')


def assert_item_requestable(item: Item, requested_qty: Decimal) -> None:
    '''
        Enforces the business rules for putting an item into a request:
            - the item must be active,
            - its current_stock must be strictly above the minimum,
            - the requested quantity must fit in what is left after other open
              requests took their reservations.
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

    available = available_stock(item)
    if requested_qty > available:
        reserved = Decimal(item.reserved_stock or 0)
        detail = (
            f'Requested quantity {requested_qty} for item {item.code} '
            f'exceeds the available quantity ({available}).'
        )
        if reserved > 0:
            detail += f' {reserved} unit(s) are reserved by other open requests.'
        raise InvalidInputError(detail = detail)


def assert_item_deliverable(item: Item, quantity: Decimal) -> None:
    '''
        Checks an item can still serve a quantity that is already reserved.

        Deliberately does NOT subtract reserved_stock: the request being
        served owns part of that reservation, so counting it again would make
        every request block itself. What must still hold is that handing the
        units over does not push the physical balance below the minimum.

        Args:
            item (Item): Item about to be moved out.
            quantity (Decimal): Quantity to hand over.

        Raises:
            InvalidInputError: If the item is inactive or the physical stock
                above the minimum no longer covers the quantity.
    '''
    if not item.is_active:
        raise InvalidInputError(detail = f'Item {item.code} is inactive.')

    serviceable = Decimal(item.current_stock) - Decimal(item.min_stock)
    if quantity > serviceable:
        raise InvalidInputError(
            detail = (
                f'Item {item.code} no longer covers {quantity} unit(s) without '
                f'falling below its minimum ({item.current_stock}/{item.min_stock}).'
            )
        )


def reserve_stock(item: Item, quantity: Decimal) -> None:
    '''
        Commits `quantity` of an item to an open request.

        Args:
            item (Item): Item whose reservation grows.
            quantity (Decimal): Positive quantity to hold.
    '''
    item.reserved_stock = Decimal(item.reserved_stock or 0) + Decimal(quantity)


def release_stock(item: Item, quantity: Decimal) -> None:
    '''
        Gives `quantity` back to the available pool.

        Floors at zero so a double release — a bug elsewhere — degrades into
        an accurate reading instead of a negative reservation that would
        silently inflate availability.

        Args:
            item (Item): Item whose reservation shrinks.
            quantity (Decimal): Positive quantity to release.
    '''
    remaining = Decimal(item.reserved_stock or 0) - Decimal(quantity)
    item.reserved_stock = remaining if remaining > 0 else Decimal('0')


def release_request_reservations(db: Session, request: Request) -> None:
    '''
        Releases everything a request still holds.

        Used by reject, cancel and delete. Each line releases the part that
        was never delivered, so a partially delivered request does not give
        back units that already left the warehouse.

        Args:
            db (Session): Active session; the caller commits.
            request (Request): Request whose lines are released.
    '''
    for detail in request.details:
        pending = Decimal(detail.requested_qty) - Decimal(detail.delivered_qty or 0)
        if pending <= 0:
            continue
        item = db.query(Item).filter(Item.id == detail.item_id).first()
        if item is None:
            continue
        release_stock(item, pending)
        db.add(item)

    message = f'Reservations released for request {request.code}.'
    logger.info(message)


def recalculate_reserved_stock(db: Session) -> int:
    '''
        Rebuilds Item.reserved_stock from the open requests.

        The reservation is materialized on the item so the catalog can answer
        "how many can I ask for" in one read; this recomputes it from the
        source of truth when a manual fix or an old dataset leaves it stale.

        Args:
            db (Session): Active session; the caller commits.

        Returns:
            int: Number of items whose stored reservation changed.
    '''
    pending: dict[int, Decimal] = {}
    rows = (
        db.query(RequestDetail)
        .join(Request, Request.id == RequestDetail.request_id)
        .filter(Request.status.in_(RESERVING_STATUSES))
        .all()
    )
    for row in rows:
        outstanding = Decimal(row.requested_qty) - Decimal(row.delivered_qty or 0)
        if outstanding > 0:
            pending[row.item_id] = pending.get(row.item_id, Decimal('0')) + outstanding

    changed = 0
    for item in db.query(Item).all():
        expected = pending.get(item.id, Decimal('0'))
        if Decimal(item.reserved_stock or 0) != expected:
            item.reserved_stock = expected
            db.add(item)
            changed += 1
    return changed


# --------------------------------------------------------------------------- #
# Kardex                                                                      #
# --------------------------------------------------------------------------- #
@dataclass
class MovementReference:
    '''
        Source document a kardex row points back to: a supply request, a Nota
        de Ingreso or a manual adjustment.
    '''
    kind: ReferenceTypeEnum
    identifier: Optional[int] = None


@dataclass
class CostLayer:
    '''
        PEPS/FIFO layer a movement is valued against. Left empty when the
        movement carries no valuation, such as an unvalued adjustment.
    '''
    unit_cost: Optional[Decimal] = None
    entry_id: Optional[int] = None
    entry_detail_id: Optional[int] = None


@dataclass
class MovementSpec:
    '''
        Everything a kardex row needs beyond the session and the item.

        Grouped into one object because a ledger row carries direction, origin,
        actor, free text and valuation at once: threading ten positional
        arguments through every caller made the call sites unreadable and hid
        which of them were optional.
    '''
    movement_type: MovementTypeEnum
    reference: MovementReference
    quantity: Decimal
    created_by: str
    notes: Optional[str] = None
    batch_code: Optional[str] = None
    layer: CostLayer = field(default_factory = CostLayer)


@dataclass
class OutflowSpec:
    '''
        Actor, origin and note shared by every movement produced by a single
        FIFO consumption, which may span several cost layers.
    '''
    created_by: str
    reference: MovementReference
    notes: Optional[str] = None


def post_kardex_movement(
    db: Session, item: Item, spec: MovementSpec
) -> KardexMovement:
    '''
        Appends a valued kardex row and updates the materialized current_stock.

        Quantity is always positive in storage; the sign of the operation is
        encoded by movement_type:
            IN          -> add to balance
            OUT         -> subtract from balance
            ADJUSTMENT  -> add (signed) to balance, allowing corrections

        For ADJUSTMENT the caller may pass a negative quantity to subtract.
        For IN/OUT the quantity must be positive.

        spec.layer carries the PEPS/FIFO valuation: on IN it describes the
        layer being created, on OUT the exact layer consumed. total_cost is
        derived from the absolute quantity so it stays positive regardless of
        direction.

        Args:
            db (Session): Active session; the caller commits.
            item (Item): Item whose ledger and balance are updated.
            spec (MovementSpec): Direction, origin, quantity, actor and layer.

        Returns:
            KardexMovement: The appended (not yet committed) ledger row.

        Raises:
            InvalidInputError: If the quantity is not positive on an IN/OUT
                movement, or the movement would leave a negative balance.
    '''
    quantity = spec.quantity
    if spec.movement_type in (MovementTypeEnum.IN, MovementTypeEnum.OUT) and quantity <= 0:
        raise InvalidInputError(detail = 'Quantity must be positive for IN/OUT movements.')

    balance_before = Decimal(item.current_stock)
    delta = -quantity if spec.movement_type == MovementTypeEnum.OUT else quantity

    new_balance = balance_before + delta
    if new_balance < 0:
        raise InvalidInputError(
            detail = (
                f'Movement would leave item {item.code} with negative stock '
                f'({new_balance}). Operation rejected.'
            )
        )

    stored_qty = quantity if spec.movement_type == MovementTypeEnum.ADJUSTMENT else abs(quantity)
    unit_cost = spec.layer.unit_cost
    total_cost = Decimal(unit_cost) * abs(stored_qty) if unit_cost is not None else None

    movement = KardexMovement(
        item_id = item.id,
        movement_type = spec.movement_type,
        reference_type = spec.reference.kind,
        reference_id = spec.reference.identifier,
        quantity = stored_qty,
        balance_before = balance_before,
        balance_after = new_balance,
        unit_cost = unit_cost,
        total_cost = total_cost,
        source_entry_id = spec.layer.entry_id,
        source_entry_detail_id = spec.layer.entry_detail_id,
        batch_code = spec.batch_code,
        notes = spec.notes,
        created_by = spec.created_by,
    )
    db.add(movement)
    item.current_stock = new_balance

    message = (
        f'Kardex {spec.movement_type.value} for item {item.code}: '
        f'{balance_before} -> {new_balance} (qty={quantity}, '
        f'ref={spec.reference.kind.value}#{spec.reference.identifier})'
    )
    logger.info(message)
    return movement


def consume_stock_fifo(
    db: Session, item: Item, quantity: Decimal, outflow: OutflowSpec
) -> List[KardexMovement]:
    '''
        Consumes `quantity` from an item's cost layers oldest-first (PEPS).

        Walks the item's EntryDetail layers with remaining quantity in entry
        order, decrementing each and posting one OUT kardex row per layer
        touched. A delivery that spans several layers therefore yields several
        kardex rows, each valued at its own layer cost and tagged with the
        source entry (lote), so a cost difference always maps to a specific
        Nota de Ingreso.

        Args:
            db (Session): Active session; caller commits.
            item (Item): Item whose stock is being consumed.
            quantity (Decimal): Positive quantity to take out.
            outflow (OutflowSpec): Actor, origin document and optional note
                copied onto every movement produced.

        Returns:
            list[KardexMovement]: One movement per layer consumed.

        Raises:
            InvalidInputError: If quantity is not positive or the available
                cost layers cannot cover the requested quantity.
    '''
    remaining = Decimal(quantity)
    if remaining <= 0:
        raise InvalidInputError(detail = 'Quantity to consume must be positive.')

    layers = (
        db.query(EntryDetail)
        .filter(EntryDetail.item_id == item.id, EntryDetail.qty_remaining > 0)
        .order_by(EntryDetail.id.asc())
        .all()
    )

    movements: List[KardexMovement] = []
    for layer in layers:
        if remaining <= 0:
            break
        take = min(Decimal(layer.qty_remaining), remaining)
        layer.qty_remaining = Decimal(layer.qty_remaining) - take
        db.add(layer)
        movement = post_kardex_movement(db, item, MovementSpec(
            movement_type = MovementTypeEnum.OUT,
            reference = outflow.reference,
            quantity = take,
            created_by = outflow.created_by,
            notes = outflow.notes,
            layer = CostLayer(
                unit_cost = Decimal(layer.unit_cost),
                entry_id = layer.entry_id,
                entry_detail_id = layer.id,
            ),
        ))
        movements.append(movement)
        remaining -= take

    if remaining > 0:
        raise InvalidInputError(
            detail = (
                f'Insufficient cost layers for item {item.code}: {remaining} '
                f'units could not be sourced from any Nota de Ingreso.'
            )
        )
    return movements


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


# --------------------------------------------------------------------------- #
# Persistence                                                                 #
# --------------------------------------------------------------------------- #
def commit_or_conflict(db: Session, detail: str) -> None:
    '''
        Commits the session, turning a uniqueness violation into a domain
        error instead of leaking the driver exception.

        Both the Nota de Ingreso and the supply request generate their own
        sequential code, so two concurrent writers can collide on it. Both
        flows need the same rollback-and-explain treatment, so it lives here.

        Args:
            db (Session): Active session to commit.
            detail (str): Message describing the collision to the caller.

        Raises:
            RegisterAlreadyExistsError: If the commit violates a constraint.
    '''
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise RegisterAlreadyExistsError(detail = detail) from exc
