'''
    Controllers for the valued warehouse reports.

    All aggregation is done in Python over the append-only, valued kardex and
    the live PEPS/FIFO cost layers. The workload is a low-throughput admin task,
    so clarity is favoured over query micro-optimization.
'''
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from models.supplies import EntryDetail, Item, KardexMovement, Request
from schemas.enums import MovementTypeEnum, ReferenceTypeEnum
from schemas.reports import (
    InOutByGroupReportSchema,
    InOutByGroupRowSchema,
    KardexValuedItemSchema,
    KardexValuedLineSchema,
    KardexValuedReportSchema,
    OutflowItemSchema,
    OutflowLineSchema,
    OutflowReportSchema,
    PhysicalValuedGroupSchema,
    PhysicalValuedItemSchema,
    PhysicalValuedReportSchema,
    PhysicalValuedSummaryRowSchema,
    StockOnHandGroupSchema,
    StockOnHandItemSchema,
    StockOnHandReportSchema,
    StockOnHandSummaryRowSchema,
)
from services.utils import get_current_time_gmt

ZERO = Decimal('0')


# --------------------------------------------------------------------------- #
# Shared helpers                                                              #
# --------------------------------------------------------------------------- #
def _direction(movement: KardexMovement) -> Tuple[str, Decimal, Decimal]:
    '''
        Normalizes a movement into ('in'|'out', quantity, value), folding
        signed ADJUSTMENT rows into the matching direction. total_cost is
        treated as 0 when the movement carries no valuation.
    '''
    quantity = Decimal(movement.quantity)
    value = Decimal(movement.total_cost) if movement.total_cost is not None else ZERO
    if movement.movement_type == MovementTypeEnum.IN:
        return 'in', quantity, value
    if movement.movement_type == MovementTypeEnum.OUT:
        return 'out', quantity, value
    # ADJUSTMENT: quantity is signed.
    if quantity >= 0:
        return 'in', quantity, value
    return 'out', -quantity, abs(value)


def _items_by_group(db: Session) -> Tuple[List[Item], Dict[int, Item]]:
    '''
        Loads all items with their group and unit eagerly. Returns the ordered
        list plus an id-indexed map.
    '''
    items = (
        db.query(Item)
        .options(joinedload(Item.category), joinedload(Item.unit))
        .order_by(Item.code.asc())
        .all()
    )
    return items, {item.id: item for item in items}


def _movements_by_item(
    db: Session, date_to: Optional[datetime]
) -> Dict[int, List[KardexMovement]]:
    '''
        Groups every kardex movement up to `date_to` by item id, ordered by
        time. Movements after the range are excluded up front.
    '''
    query = db.query(KardexMovement)
    if date_to:
        query = query.filter(KardexMovement.created_at <= date_to)
    grouped: Dict[int, List[KardexMovement]] = {}
    for movement in query.order_by(KardexMovement.created_at.asc(),
                                   KardexMovement.id.asc()).all():
        grouped.setdefault(movement.item_id, []).append(movement)
    return grouped


def _unit_of(item: Item) -> str:
    '''
        Abbreviated unit of measure, empty when the item has none.
    '''
    return item.unit.abbreviation if item.unit else ''


def _bucket_of(groups: Dict[str, Dict], item: Item) -> Dict:
    '''
        Returns (creating it on first use) the accumulator bucket of the item's
        accounting group. Items without a group fall into a single placeholder
        so they stay visible in the report instead of disappearing.

        Args:
            groups (Dict[str, Dict]): Buckets indexed by group code.
            item (Item): Item whose group is being resolved.

        Returns:
            Dict: The bucket, holding the group name and its rows.
    '''
    category = item.category
    code = category.code if category else '—'
    name = category.name if category else 'SIN GRUPO'
    return groups.setdefault(code, {'name': name, 'rows': []})


def _in_group(item: Item, group_code: Optional[str]) -> bool:
    '''
        Whether the item belongs to the requested accounting group. No filter
        means every item passes.

        Args:
            item (Item): Item under evaluation.
            group_code (str | None): Requested group code, or None for all.

        Returns:
            bool: True when the item must be included.
    '''
    if not group_code:
        return True
    return bool(item.category and item.category.code == group_code)


@dataclass
class _PeriodTotals:
    '''
        Opening balance and in/out flows of one item over a date range, both
        physical and valued. Grouped so the aggregation loop returns one object
        instead of six parallel accumulators.
    '''
    fisico_inicio: Decimal = ZERO
    valorado_inicio: Decimal = ZERO
    fisico_ingreso: Decimal = ZERO
    valorado_ingreso: Decimal = ZERO
    fisico_egreso: Decimal = ZERO
    valorado_egreso: Decimal = ZERO


def _period_totals(
    movements: List[KardexMovement], date_from: Optional[datetime]
) -> _PeriodTotals:
    '''
        Splits an item's movements into the opening balance (everything before
        date_from) and the in/out flows inside the range.

        Args:
            movements (List[KardexMovement]): Item movements up to date_to.
            date_from (datetime | None): Start of the range; None folds every
                movement into the in/out flows.

        Returns:
            _PeriodTotals: The six accumulated figures.
    '''
    totals = _PeriodTotals()
    for movement in movements:
        direction, quantity, value = _direction(movement)
        if date_from and movement.created_at < date_from:
            sign = Decimal('1') if direction == 'in' else Decimal('-1')
            totals.fisico_inicio += sign * quantity
            totals.valorado_inicio += sign * value
        elif direction == 'in':
            totals.fisico_ingreso += quantity
            totals.valorado_ingreso += value
        else:
            totals.fisico_egreso += quantity
            totals.valorado_egreso += value
    return totals


def _physical_row(item: Item, totals: _PeriodTotals) -> PhysicalValuedItemSchema:
    '''
        Builds one row of the physical + valued inventory, where
        agregado = inicio + ingreso and final = agregado - egreso.

        Args:
            item (Item): Item the row describes.
            totals (_PeriodTotals): Its accumulated figures for the range.

        Returns:
            PhysicalValuedItemSchema: The report row.
    '''
    fisico_agregado = totals.fisico_inicio + totals.fisico_ingreso
    valorado_agregado = totals.valorado_inicio + totals.valorado_ingreso
    fisico_final = fisico_agregado - totals.fisico_egreso
    valorado_final = valorado_agregado - totals.valorado_egreso
    return PhysicalValuedItemSchema(
        item_code = item.code,
        item_name = item.name,
        unit = _unit_of(item),
        fisico_inicio = totals.fisico_inicio,
        fisico_ingreso = totals.fisico_ingreso,
        fisico_agregado = fisico_agregado,
        fisico_egreso = totals.fisico_egreso,
        fisico_final = fisico_final,
        valorado_inicio = totals.valorado_inicio,
        valorado_ingreso = totals.valorado_ingreso,
        valorado_agregado = valorado_agregado,
        valorado_egreso = totals.valorado_egreso,
        valorado_final = valorado_final,
        precio_unitario = (valorado_final / fisico_final) if fisico_final != ZERO else ZERO,
    )


# --------------------------------------------------------------------------- #
# 1. Inventario General Físico Valorado                                       #
# --------------------------------------------------------------------------- #
def _physical_groups(
    groups: Dict[str, Dict]
) -> Tuple[List[PhysicalValuedGroupSchema], List[PhysicalValuedSummaryRowSchema], Decimal]:
    '''
        Folds the per-item rows into the group blocks, the per-group summary
        and the grand total, all ordered by accounting group code.

        Args:
            groups (Dict[str, Dict]): Buckets of rows indexed by group code.

        Returns:
            Tuple: (group blocks, summary rows, grand total valued).
    '''
    group_schemas: List[PhysicalValuedGroupSchema] = []
    summary: List[PhysicalValuedSummaryRowSchema] = []
    grand_total = ZERO
    for code in sorted(groups):
        bucket = groups[code]
        fisico = sum((row.fisico_final for row in bucket['rows']), ZERO)
        valorado = sum((row.valorado_final for row in bucket['rows']), ZERO)
        grand_total += valorado
        group_schemas.append(PhysicalValuedGroupSchema(
            group_code = code, group_name = bucket['name'], items = bucket['rows'],
            fisico_final = fisico, valorado_final = valorado,
        ))
        summary.append(PhysicalValuedSummaryRowSchema(
            group_code = code, group_name = bucket['name'],
            fisico_final = fisico, valorado_final = valorado,
        ))
    return group_schemas, summary, grand_total


async def physical_valued_report_controller(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    group_code: Optional[str] = None,
    include_zero: bool = True,
) -> PhysicalValuedReportSchema:
    '''
        Builds the physical + valued inventory report per accounting group,
        where agregado = inicio + ingreso and final = agregado - egreso.
    '''
    items, _ = _items_by_group(db)
    movements = _movements_by_item(db, date_to)

    groups: Dict[str, Dict] = {}
    for item in items:
        if not _in_group(item, group_code):
            continue
        totals = _period_totals(movements.get(item.id, []), date_from)
        row = _physical_row(item, totals)
        # "Sin registros 0" drops items that neither hold stock nor moved.
        if not include_zero and row.fisico_final == ZERO \
                and totals.fisico_ingreso == ZERO and totals.fisico_egreso == ZERO:
            continue
        _bucket_of(groups, item)['rows'].append(row)

    group_schemas, summary, grand_total = _physical_groups(groups)
    return PhysicalValuedReportSchema(
        date_from = date_from, date_to = date_to,
        groups = group_schemas, summary = summary, grand_total_valorado = grand_total,
    )


# --------------------------------------------------------------------------- #
# 2. Inventario con Stock Existente                                           #
# --------------------------------------------------------------------------- #
def _stock_from_layers(db: Session) -> Dict[int, Dict[str, Decimal]]:
    '''
        Current stock read straight from the live PEPS/FIFO layers
        (sum of qty_remaining * unit_cost). Exact, and the cheapest path when
        the report is asked for "today".
    '''
    per_item: Dict[int, Dict[str, Decimal]] = {}
    for layer in db.query(EntryDetail).filter(EntryDetail.qty_remaining > 0).all():
        acc = per_item.setdefault(layer.item_id, {'qty': ZERO, 'val': ZERO})
        acc['qty'] += Decimal(layer.qty_remaining)
        acc['val'] += Decimal(layer.qty_remaining) * Decimal(layer.unit_cost)
    return per_item


def _stock_at_date(db: Session, date_to: datetime) -> Dict[int, Dict[str, Decimal]]:
    '''
        Stock as it stood on a past cut-off date, replayed from the kardex.

        The live layers only describe *today*, so a historical snapshot has to
        be rebuilt from the movements. The valued balance stays PEPS-consistent
        because every OUT was already costed against its layer when it happened.
    '''
    per_item: Dict[int, Dict[str, Decimal]] = {}
    for item_id, movements in _movements_by_item(db, date_to).items():
        acc = per_item.setdefault(item_id, {'qty': ZERO, 'val': ZERO})
        for movement in movements:
            direction, quantity, value = _direction(movement)
            sign = Decimal('1') if direction == 'in' else Decimal('-1')
            acc['qty'] += sign * quantity
            acc['val'] += sign * value
    return per_item


def _stock_row(item: Item, balance: Dict[str, Decimal]) -> StockOnHandItemSchema:
    '''
        Builds one row of the stock-on-hand report from an item's balance.

        Args:
            item (Item): Item the row describes.
            balance (Dict[str, Decimal]): Its 'qty' and 'val' figures.

        Returns:
            StockOnHandItemSchema: The report row, with the unit price derived
                from the valued balance so it reflects the real PEPS mix.
    '''
    saldo = balance['qty']
    valorado = balance['val']
    return StockOnHandItemSchema(
        item_code = item.code,
        item_name = item.name,
        unit = _unit_of(item),
        saldo_existente = saldo,
        precio_unitario = (valorado / saldo) if saldo != ZERO else ZERO,
        total_valorado = valorado,
    )


def _stock_groups(
    groups: Dict[str, Dict]
) -> Tuple[List[StockOnHandGroupSchema], List[StockOnHandSummaryRowSchema], Decimal]:
    '''
        Folds the stock rows into group blocks, summary rows and grand total.

        Args:
            groups (Dict[str, Dict]): Buckets of rows indexed by group code.

        Returns:
            Tuple: (group blocks, summary rows, grand total valued).
    '''
    group_schemas: List[StockOnHandGroupSchema] = []
    summary: List[StockOnHandSummaryRowSchema] = []
    grand_total = ZERO
    for code in sorted(groups):
        bucket = groups[code]
        bucket['rows'].sort(key = lambda row: row.item_code)
        total = sum((row.total_valorado for row in bucket['rows']), ZERO)
        saldo = sum((row.saldo_existente for row in bucket['rows']), ZERO)
        grand_total += total
        group_schemas.append(StockOnHandGroupSchema(
            group_code = code, group_name = bucket['name'],
            items = bucket['rows'], total_valorado = total,
        ))
        summary.append(StockOnHandSummaryRowSchema(
            group_code = code, group_name = bucket['name'],
            saldo_existente = saldo, total_valorado = total,
        ))
    return group_schemas, summary, grand_total


async def stock_on_hand_report_controller(
    db: Session,
    group_code: Optional[str] = None,
    date_to: Optional[datetime] = None,
    include_zero: bool = False,
) -> StockOnHandReportSchema:
    '''
        Items with stock on hand, valued from their PEPS/FIFO cost layers.

        `date_to` is a cut-off, not a range: a stock report answers "how much
        was there on this date", so there is no start boundary to honour. When
        omitted the snapshot is the live one.

        `include_zero` mirrors the legacy "con/sin registros 0" switch: keep
        items whose balance is zero (they still had movements) or drop them.
    '''
    items, _ = _items_by_group(db)
    per_item = _stock_at_date(db, date_to) if date_to else _stock_from_layers(db)

    # Iterating over the catalog (not over the balances) is what makes
    # "con registros 0" possible: an item with no stock left has no cost layer
    # and no balance entry, yet the legacy report still lists it.
    groups: Dict[str, Dict] = {}
    for item in items:
        if not _in_group(item, group_code):
            continue
        acc = per_item.get(item.id, {'qty': ZERO, 'val': ZERO})
        if not include_zero and acc['qty'] <= ZERO:
            continue
        _bucket_of(groups, item)['rows'].append(_stock_row(item, acc))

    group_schemas, summary, grand_total = _stock_groups(groups)
    return StockOnHandReportSchema(
        generated_at = get_current_time_gmt(),
        groups = group_schemas, summary = summary, grand_total_valorado = grand_total,
    )


# --------------------------------------------------------------------------- #
# 3. Entradas y Salidas Valorado por Cuenta Contable                          #
# --------------------------------------------------------------------------- #
async def in_out_by_group_report_controller(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> InOutByGroupReportSchema:
    '''
        Valued ins/outs aggregated per accounting group over the range, with
        saldo = ingresos - salidas.
    '''
    items, _ = _items_by_group(db)
    movements = _movements_by_item(db, date_to)

    per_group: Dict[str, Dict] = {}
    for item in items:
        bucket = _bucket_of(per_group, item)
        bucket.setdefault('in', ZERO)
        bucket.setdefault('out', ZERO)
        for movement in movements.get(item.id, []):
            if date_from and movement.created_at < date_from:
                continue
            direction, _, value = _direction(movement)
            bucket[direction] += value

    rows: List[InOutByGroupRowSchema] = []
    total_in = total_out = ZERO
    for code in sorted(per_group):
        bucket = per_group[code]
        total_in += bucket['in']
        total_out += bucket['out']
        rows.append(InOutByGroupRowSchema(
            group_code = code, group_name = bucket['name'],
            ingresos = bucket['in'], salidas = bucket['out'],
            saldo = bucket['in'] - bucket['out'],
        ))

    return InOutByGroupReportSchema(
        date_from = date_from, date_to = date_to, rows = rows,
        total_ingresos = total_in, total_salidas = total_out,
        total_saldo = total_in - total_out,
    )


# --------------------------------------------------------------------------- #
# 4. Kardex Físico y Valorado                                                 #
# --------------------------------------------------------------------------- #
def _kardex_item(
    item: Item, movements: List[KardexMovement], date_from: Optional[datetime]
) -> KardexValuedItemSchema:
    '''
        Builds the valued kardex block of a single item: the opening balance,
        one line per in-range movement with its running balance, and the
        closing balance.

        Movements before date_from are still walked — they are what produces
        the opening balance — but they do not become visible lines.

        Args:
            item (Item): Item the ledger belongs to.
            movements (List[KardexMovement]): Its movements up to date_to,
                chronologically ordered.
            date_from (datetime | None): Start of the visible range.

        Returns:
            KardexValuedItemSchema: The item block, physical and valued.
    '''
    saldo_qty = saldo_val = ZERO
    lines: List[KardexValuedLineSchema] = []
    for movement in movements:
        direction, quantity, value = _direction(movement)
        is_in = direction == 'in'
        saldo_qty += quantity if is_in else -quantity
        saldo_val += value if is_in else -value

        if date_from and movement.created_at < date_from:
            continue

        lines.append(KardexValuedLineSchema(
            created_at = movement.created_at,
            detail = movement.notes or movement.reference_type.value,
            source_entry_id = movement.source_entry_id,
            entrada_qty = quantity if is_in else ZERO,
            salida_qty = ZERO if is_in else quantity,
            saldo_qty = saldo_qty,
            unit_cost = movement.unit_cost,
            entrada_val = value if is_in else ZERO,
            salida_val = ZERO if is_in else value,
            saldo_val = saldo_val,
        ))

    # The opening balance is the closing one minus everything the visible lines
    # moved, which is exactly the balance just before the first visible line.
    return KardexValuedItemSchema(
        item_code = item.code,
        item_name = item.name,
        unit = _unit_of(item),
        group_name = item.category.name if item.category else 'SIN GRUPO',
        saldo_inicial_qty = saldo_qty - sum(
            (line.entrada_qty - line.salida_qty for line in lines), ZERO),
        saldo_inicial_val = saldo_val - sum(
            (line.entrada_val - line.salida_val for line in lines), ZERO),
        lines = lines,
        saldo_final_qty = saldo_qty,
        saldo_final_val = saldo_val,
    )


async def kardex_valued_report_controller(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    item_id: Optional[int] = None,
    group_code: Optional[str] = None,
) -> KardexValuedReportSchema:
    '''
        Physical + valued kardex for one item, one accounting group or the whole
        warehouse, carrying an opening balance (before date_from) and a running
        balance through the range.
    '''
    items, _ = _items_by_group(db)
    if item_id:
        items = [it for it in items if it.id == item_id]
    if group_code:
        items = [it for it in items if it.category and it.category.code == group_code]
    movements = _movements_by_item(db, date_to)

    result: List[KardexValuedItemSchema] = []
    for item in items:
        item_movements = movements.get(item.id, [])
        if item_movements:
            result.append(_kardex_item(item, item_movements, date_from))

    return KardexValuedReportSchema(
        date_from = date_from, date_to = date_to, items = result,
    )


# --------------------------------------------------------------------------- #
# 5. Estadísticas de Salida de Artículos                                      #
# --------------------------------------------------------------------------- #
async def outflow_report_controller(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> OutflowReportSchema:
    '''
        Per-item outflow (deliveries) over the range, listing recipient and
        quantity for each OUT movement sourced from a request.
    '''
    _, item_map = _items_by_group(db)

    query = db.query(KardexMovement).filter(
        KardexMovement.movement_type == MovementTypeEnum.OUT
    )
    if date_from:
        query = query.filter(KardexMovement.created_at >= date_from)
    if date_to:
        query = query.filter(KardexMovement.created_at <= date_to)
    out_movements = query.order_by(KardexMovement.created_at.asc()).all()

    # Resolve recipient (requester email + code) for request-sourced rows.
    request_ids = {
        m.reference_id for m in out_movements
        if m.reference_type == ReferenceTypeEnum.REQUEST and m.reference_id
    }
    requests: Dict[int, Request] = {}
    if request_ids:
        for request in db.query(Request).filter(Request.id.in_(request_ids)).all():
            requests[request.id] = request

    per_item: Dict[int, Dict] = {}
    for movement in out_movements:
        item = item_map.get(movement.item_id)
        if item is None:
            continue
        request = requests.get(movement.reference_id) if movement.reference_id else None
        acc = per_item.setdefault(movement.item_id, {'item': item, 'total': ZERO, 'lines': []})
        acc['total'] += Decimal(movement.quantity)
        acc['lines'].append(OutflowLineSchema(
            created_at = movement.created_at,
            recipient = request.requester_email if request else (movement.created_by or '—'),
            request_code = request.code if request else None,
            quantity = Decimal(movement.quantity),
        ))

    items: List[OutflowItemSchema] = []
    grand_total = ZERO
    for acc in sorted(per_item.values(), key = lambda a: a['item'].code):
        item = acc['item']
        grand_total += acc['total']
        items.append(OutflowItemSchema(
            item_code = item.code,
            item_name = item.name,
            unit = _unit_of(item),
            total_salida = acc['total'],
            lines = acc['lines'],
        ))

    return OutflowReportSchema(
        date_from = date_from, date_to = date_to,
        items = items, grand_total_salida = grand_total,
    )
