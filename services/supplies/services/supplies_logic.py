'''
    Domain logic for the Supplies service.

    Centralizes:
        - Stock validation against the configured minimum.
        - PEPS/FIFO consumption of the cost layers a Nota de Ingreso created.
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

from models.supplies import EntryDetail, Item, KardexMovement
from schemas.enums import MovementTypeEnum, ReferenceTypeEnum, RoleEnum
from services.exceptions import (
    ForbiddenError,
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError,
)
from services.logger_config import custom_logger as logger


def available_stock(item: Item) -> Decimal:
    '''
        Units that can still be taken out of the warehouse.

        Physical stock minus the minimum the warehouse must keep. Never returns
        a negative number: an item below its floor reads as 0 available, not as
        debt.

        Args:
            item (Item): Item to measure.

        Returns:
            Decimal: Available quantity, floored at zero.
    '''
    free = Decimal(item.current_stock) - Decimal(item.min_stock)
    return free if free > 0 else Decimal('0')


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
def fetch_active_item(
    db: Session,
    item_id: int
) -> Item:
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


def assert_role_in(
    role: str,
    allowed: Iterable[RoleEnum]
) -> None:
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
def commit_or_conflict(
    db: Session,
    detail: str
) -> None:
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
