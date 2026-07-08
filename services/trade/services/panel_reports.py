'''
    Panel Reports Service — iter6 (Binaria, 2026-06-22), Monitor de Trade (req 7.4).

    The three services below back the executive panels (Impulses,
    Replenishments and Route tracking). They run against the same operational
    tables covered by services.reports; each one composes a pre-aggregated
    payload so the frontend renders the panel in a single round-trip.

    Split out of services.reports so neither module exceeds the size / cyclomatic
    limits; the aggregation steps are factored into small, single-purpose
    helpers shared by the Impulses and Replenishments panels.
'''
from datetime import datetime, time
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.trade import (
    TradePlanning,
    TradePlanningDetail,
    PlannedRoute,
    PlannedPoint,
    Attendance
)
from models.pos import PointOfSale
from models.impulses import (
    ImpulseInventoryStart,
    ImpulseSale,
    ImpulseSaleDetail,
)
from models.products import Product, ProductAssignmentPOS
from schemas.reports import (
    PanelFilterSchema,
    PanelByCityRow,
    PanelByDayRow,
    PanelGeneralIndicatorsSchema,
    PanelInventorySnapshotRow,
    PanelExpirationRow,
    PanelRouteIndicatorsSchema,
    PanelSalesSummaryRow,
    PanelSheetRow,
    ImpulsesPanelResponseSchema,
    ReplenishmentsPanelResponseSchema,
    RouteTrackingFilterSchema,
    RouteTrackingPointSchema,
    RouteTrackingPosInventoryRow,
    RouteTrackingResponseSchema,
    RouteTrackingRouteSchema,
)
from services.logger_config import custom_logger as logger
from services.utils import handle_service_errors


# ---------------------------------------------------------------------------
# Shared query / aggregation helpers
# ---------------------------------------------------------------------------

def _apply_attendance_panel_filters(query, filters: PanelFilterSchema, *,
                                    route_type: str | None):
    '''
        Bolts the panel filters onto an Attendance query already joined to
        PlannedPoint / PlannedRoute / PointOfSale. Centralised so the
        Impulses and Replenishments services stay in sync.
    '''
    start_dt = datetime.combine(filters.date_from, time.min)
    end_dt = datetime.combine(filters.date_to, time.max)
    query = query.filter(
        Attendance.company_id == filters.company_id,
        Attendance.check_in_time.between(start_dt, end_dt),
    )
    if route_type is not None:
        query = query.filter(PlannedRoute.route_type == route_type)
    if filters.client_company_id is not None:
        query = query.filter(Attendance.client_company_id == filters.client_company_id)
    if filters.pos_id is not None:
        query = query.filter(PointOfSale.id == filters.pos_id)
    if filters.country_id is not None:
        query = query.filter(PlannedRoute.country_id == filters.country_id)
    if filters.city_id is not None:
        query = query.filter(PlannedRoute.city_id == filters.city_id)
    if filters.route_id is not None:
        query = query.filter(PlannedRoute.id == filters.route_id)
    if filters.user_id is not None:
        query = query.filter(Attendance.user_id == filters.user_id)
    return query


def _panel_attendance_rows(db: Session, filters: PanelFilterSchema, route_type: str):
    '''
        Runs the base Attendance query (joined to point / route / POS) with the
        panel filters applied, returning the raw (att, pp, pr, pos) tuples.
    '''
    base = (
        db.query(Attendance, PlannedPoint, PlannedRoute, PointOfSale)
        .join(PlannedPoint, PlannedPoint.id == Attendance.trade_planned_point_id)
        .join(PlannedRoute, PlannedRoute.id == PlannedPoint.planned_route_id)
        .join(PointOfSale, PointOfSale.id == PlannedPoint.point_of_sale_id)
    )
    base = _apply_attendance_panel_filters(base, filters, route_type = route_type)
    return base.all()


def _normalize_attendances(rows):
    '''
        Stamps point_of_sale_id / planned_route_id onto each attendance row so
        the indicator helpers can read them uniformly.
    '''
    result = []
    for att, _pp, pr, pos in rows:
        att.point_of_sale_id = pos.id
        att.planned_route_id = pr.id
        result.append(att)
    return result


def _inventory_start_rows(db: Session, attendance_ids):
    '''
        Returns every ImpulseInventoryStart row for the given attendances.
        Shared by the Impulses and Replenishments panels (unified inventory).
    '''
    return (
        db.query(ImpulseInventoryStart)
        .filter(ImpulseInventoryStart.attendance_id.in_(attendance_ids or [0]))
        .all()
    )


def _percentages(rows):
    '''
        Returns rows enriched with a percentage column computed against the
        total count.
    '''
    total = sum(r['count'] for r in rows) or 1
    for row in rows:
        row['percentage'] = round(row['count'] * 100.0 / total, 2)
    return rows


def _city_breakdown(rows):
    '''
        Builds the pdv-by-city and activities-by-city cuadros (with their
        percentage column) from the raw attendance rows.
    '''
    by_city_pdv = defaultdict(set)
    by_city_act = defaultdict(int)
    for _att, _pp, _pr, pos in rows:
        by_city_pdv[pos.city_id].add(pos.id)
        by_city_act[pos.city_id] += 1
    pdv = _percentages([
        {'city_id': city_id, 'count': len(pdvs)}
        for city_id, pdvs in by_city_pdv.items()
    ])
    act = _percentages([
        {'city_id': city_id, 'count': cnt}
        for city_id, cnt in by_city_act.items()
    ])
    return [PanelByCityRow(**r) for r in pdv], [PanelByCityRow(**r) for r in act]


def _activities_by_day(attendances_norm):
    '''
        Counts activities per calendar day (by check-in time).
    '''
    by_day = defaultdict(int)
    for att in attendances_norm:
        if att.check_in_time:
            by_day[att.check_in_time.date()] += 1
    return [PanelByDayRow(day = d, count = c) for d, c in sorted(by_day.items())]


def _build_general_indicators(attendances, products_count, products_per_activity):
    '''
        Computes the "Indicadores generales" cuadro from a list of
        attendance rows.
    '''
    pdvs = {a.point_of_sale_id for a in attendances if a.point_of_sale_id}
    activity_count = len(attendances)
    durations = [a.duration_minutes for a in attendances if a.duration_minutes]
    return PanelGeneralIndicatorsSchema(
        pdv_count = len(pdvs),
        activity_count = activity_count,
        activities_per_pdv = (
            round(activity_count / len(pdvs), 2) if pdvs else 0.0
        ),
        products_count = products_count,
        products_per_activity = products_per_activity,
        avg_time_per_pdv_minutes = (
            round(sum(durations) / len(durations), 2) if durations else 0.0
        ),
    )


def _build_route_indicators(attendances) -> PanelRouteIndicatorsSchema:
    '''
        Computes the "Indicadores de ruta" cuadro. Returns zeros if there
        is not enough data; the panel hides the box on the frontend when
        no route was filtered.
    '''
    by_route = defaultdict(list)
    for a in attendances:
        if a.planned_route_id:
            by_route[a.planned_route_id].append(a)

    if not by_route:
        return PanelRouteIndicatorsSchema()

    avg_pdv_per_route = sum(
        len({a.point_of_sale_id for a in atts}) for atts in by_route.values()
    ) / len(by_route)

    route_durations = []
    between_pdv_durations = []
    for atts in by_route.values():
        atts_sorted = [a for a in atts if a.check_in_time and a.check_out_time]
        atts_sorted.sort(key = lambda x: x.check_in_time)
        if len(atts_sorted) >= 1:
            delta = (
                atts_sorted[-1].check_out_time - atts_sorted[0].check_in_time
            ).total_seconds() / 60
            route_durations.append(delta)
        for prev, curr in zip(atts_sorted, atts_sorted[1:]):
            gap = (curr.check_in_time - prev.check_out_time).total_seconds() / 60
            if gap >= 0:
                between_pdv_durations.append(gap)

    pdv_durations = [
        a.duration_minutes for atts in by_route.values()
        for a in atts if a.duration_minutes
    ]

    return PanelRouteIndicatorsSchema(
        pdv_per_route = round(avg_pdv_per_route, 2),
        avg_time_per_route_minutes = (
            round(sum(route_durations) / len(route_durations), 2)
            if route_durations else 0.0
        ),
        avg_time_per_pdv_minutes = (
            round(sum(pdv_durations) / len(pdv_durations), 2)
            if pdv_durations else 0.0
        ),
        avg_time_between_pdv_minutes = (
            round(sum(between_pdv_durations) / len(between_pdv_durations), 2)
            if between_pdv_durations else 0.0
        ),
    )


# ---------------------------------------------------------------------------
# Impulses panel (req 7.4.1)
# ---------------------------------------------------------------------------

def _impulse_sales(db: Session, attendance_ids, product_id):
    '''
        Aggregates sold quantity per product over the given attendances.
        Returns (sales_summary rows, {product_id: total_quantity}).
    '''
    sales_q = (
        db.query(
            ImpulseSaleDetail.product_id,
            Product.sku,
            Product.name,
            func.sum(ImpulseSaleDetail.quantity).label('total_quantity'),
        )
        .join(ImpulseSale, ImpulseSale.id == ImpulseSaleDetail.impulse_sale_id)
        .join(Product, Product.id == ImpulseSaleDetail.product_id)
        .filter(ImpulseSale.attendance_id.in_(attendance_ids or [0]))
        .group_by(ImpulseSaleDetail.product_id, Product.sku, Product.name)
    )
    sales_rows = sales_q.all()
    if product_id is not None:
        sales_rows = [r for r in sales_rows if r.product_id == product_id]

    sales_summary = [
        PanelSalesSummaryRow(
            product_id = r.product_id, sku = r.sku, name = r.name,
            total_quantity = int(r.total_quantity or 0),
        ) for r in sales_rows
    ]
    sales_by_product = {r.product_id: int(r.total_quantity or 0) for r in sales_rows}
    return sales_summary, sales_by_product


def _impulse_inventory_snapshot(db: Session, inv_rows, sales_by_product):
    '''
        Builds the remaining-stock snapshot (initial inventory minus sales)
        per product for the Impulses panel.
    '''
    acc = defaultdict(lambda: {'quantity': 0, 'sku': None, 'name': None})
    for inv in inv_rows:
        prod = db.query(Product).filter_by(id = inv.product_id).first()
        if prod is None:
            continue
        base_qty = (inv.quantity_in_room or 0) + (inv.quantity_in_warehouse or 0)
        if base_qty == 0 and inv.quantity is not None:
            base_qty = inv.quantity
        acc[inv.product_id]['quantity'] += base_qty
        acc[inv.product_id]['sku'] = prod.sku
        acc[inv.product_id]['name'] = prod.name

    snapshot = []
    for pid, entry in acc.items():
        remaining = entry['quantity'] - sales_by_product.get(pid, 0)
        snapshot.append(PanelInventorySnapshotRow(
            product_id = pid, sku = entry['sku'], name = entry['name'],
            quantity = max(remaining, 0),
        ))
    return snapshot


def _sales_by_attendance_product(db: Session, attendance_ids):
    '''
        Sums sold quantity per (attendance_id, product_id) over the given
        attendances.
    '''
    sale_details = (
        db.query(ImpulseSaleDetail, ImpulseSale, Product)
        .join(ImpulseSale, ImpulseSale.id == ImpulseSaleDetail.impulse_sale_id)
        .join(Product, Product.id == ImpulseSaleDetail.product_id)
        .filter(ImpulseSale.attendance_id.in_(attendance_ids or [0]))
        .all()
    )
    sales_map: dict = defaultdict(int)
    for detail, sale, _prod in sale_details:
        sales_map[(sale.attendance_id, detail.product_id)] += detail.quantity
    return sales_map


def _impulse_sheet(db: Session, attendance_ids, rows, company_id):
    '''
        Flat row per (attendance, product) with the sold quantity.
    '''
    sales_map = _sales_by_attendance_product(db, attendance_ids)
    row_index = {att.id: (att, pr, pos) for att, _pp, pr, pos in rows}
    sheet = []
    for (att_id, product_id), qty in sales_map.items():
        indexed = row_index.get(att_id)
        prod = db.query(Product).filter_by(id = product_id).first()
        if indexed is None or prod is None:
            continue
        att, pr, pos = indexed
        sheet.append(PanelSheetRow(
            company_id = company_id,
            check_in_time = att.check_in_time,
            check_out_time = att.check_out_time,
            country_id = pr.country_id,
            city_id = pr.city_id,
            route_id = pr.id,
            route_name = pr.route_name,
            pos_id = pos.id,
            pos_name = pos.name,
            product_id = prod.id,
            sku = prod.sku,
            product_name = prod.name,
            quantity_sold = qty,
            user_id = att.user_id,
        ))
    return sheet


@handle_service_errors('REPORTS')
async def get_impulses_panel_service(
    db: Session,
    filters: PanelFilterSchema,
) -> ImpulsesPanelResponseSchema:
    '''
        Aggregates everything the Impulses panel (req 7.4.1) needs.
    '''
    message = f'Generating Impulses panel for company {filters.company_id}.'
    logger.info(message)

    rows = _panel_attendance_rows(db, filters, 'IMPULSO')
    attendance_ids = [r[0].id for r in rows]
    attendances_norm = _normalize_attendances(rows)

    sales_summary, sales_by_product = _impulse_sales(db, attendance_ids, filters.product_id)
    general = _build_general_indicators(
        attendances_norm,
        len(sales_by_product),
        round(sum(sales_by_product.values()) / len(attendances_norm), 2)
        if attendances_norm else 0.0,
    )
    route_indicators = (
        _build_route_indicators(attendances_norm)
        if filters.route_id is not None else None
    )
    pdv_by_city, activities_by_city = _city_breakdown(rows)
    inventory_snapshot = _impulse_inventory_snapshot(
        db, _inventory_start_rows(db, attendance_ids), sales_by_product
    )
    sheet = _impulse_sheet(db, attendance_ids, rows, filters.company_id)

    return ImpulsesPanelResponseSchema(
        filters_applied = filters,
        general_indicators = general,
        route_indicators = route_indicators,
        pdv_by_city = pdv_by_city,
        activities_by_city = activities_by_city,
        activities_by_day = _activities_by_day(attendances_norm),
        sales_summary = sales_summary,
        inventory_snapshot = inventory_snapshot,
        sheet = sheet,
    )


# ---------------------------------------------------------------------------
# Replenishments panel (req 7.4.3)
# ---------------------------------------------------------------------------

def _append_expiration_row(expiration_rows, inv, prod, today):
    '''
        Appends a short-date row for an inventory line carrying batch /
        expiration data. No-op when the line has neither.
    '''
    if not (inv.batch_number or inv.expiration_date):
        return
    days_remaining = None
    short = False
    if inv.expiration_date:
        days_remaining = (inv.expiration_date.date() - today).days
        short = days_remaining <= 30
    expiration_rows.append(PanelExpirationRow(
        product_id = inv.product_id,
        sku = prod.sku,
        name = prod.name,
        location = 'ROOM' if (inv.quantity_in_room or 0) > 0 else 'WAREHOUSE',
        batch_number = inv.batch_number,
        expiration_date = (
            inv.expiration_date.date() if inv.expiration_date else None
        ),
        days_remaining = days_remaining,
        is_short_dated = short,
    ))


def _snapshot_row(product_id, entry):
    '''
        Builds the sala/almacén snapshot row for one product accumulator.
    '''
    total = entry['room'] + entry['warehouse']
    minimum = entry['minimum']
    return PanelInventorySnapshotRow(
        product_id = product_id, sku = entry['sku'], name = entry['name'],
        quantity = total,
        quantity_in_room = entry['room'],
        quantity_in_warehouse = entry['warehouse'],
        quantity_minimum = minimum or None,
        stockout = (minimum > 0 and total < minimum),
    )


def _replenishment_inventory_snapshot(db: Session, inv_rows):
    '''
        Aggregates the sala/almacén snapshot and the expiration list for the
        Replenishments panel. Returns (inventory_snapshot, expiration_rows).
    '''
    acc = defaultdict(
        lambda: {'room': 0, 'warehouse': 0, 'sku': None, 'name': None, 'minimum': 0}
    )
    expiration_rows: list[PanelExpirationRow] = []
    today = datetime.utcnow().date()
    for inv in inv_rows:
        prod = db.query(Product).filter_by(id = inv.product_id).first()
        if prod is None:
            continue
        entry = acc[inv.product_id]
        entry['room'] += inv.quantity_in_room or 0
        entry['warehouse'] += inv.quantity_in_warehouse or 0
        entry['sku'] = prod.sku
        entry['name'] = prod.name
        assignment = db.query(ProductAssignmentPOS).filter_by(
            product_id = inv.product_id, point_of_sale_id = inv.product_id  # placeholder
        ).first()
        if assignment is not None:
            entry['minimum'] += assignment.minimum_stock or 0
        _append_expiration_row(expiration_rows, inv, prod, today)

    snapshot = [_snapshot_row(pid, entry) for pid, entry in acc.items()]
    return snapshot, expiration_rows


def _replenishment_sheet(db: Session, inv_rows, rows, company_id):
    '''
        One sheet row per inventory line (attendance, product).
    '''
    row_index = {att.id: (att, pr, pos) for att, _pp, pr, pos in rows}
    sheet = []
    for inv in inv_rows:
        prod = db.query(Product).filter_by(id = inv.product_id).first()
        indexed = row_index.get(inv.attendance_id)
        if prod is None or indexed is None:
            continue
        att, pr, pos = indexed
        total = (inv.quantity_in_room or 0) + (inv.quantity_in_warehouse or 0)
        sheet.append(PanelSheetRow(
            company_id = company_id,
            check_in_time = att.check_in_time,
            check_out_time = att.check_out_time,
            country_id = pr.country_id,
            city_id = pr.city_id,
            route_id = pr.id,
            route_name = pr.route_name,
            pos_id = pos.id,
            pos_name = pos.name,
            product_id = prod.id,
            sku = prod.sku,
            product_name = prod.name,
            quantity_initial = total,
            user_id = att.user_id,
        ))
    return sheet


@handle_service_errors('REPORTS')
async def get_replenishments_panel_service(
    db: Session,
    filters: PanelFilterSchema,
) -> ReplenishmentsPanelResponseSchema:
    '''
        Aggregates everything the Replenishments panel (req 7.4.3) needs.
        Uses the unified Impulses inventory tables to compute sala/almacen
        snapshots and exposes the expiration list expected by the panel.
    '''
    message = f'Generating Replenishments panel for company {filters.company_id}.'
    logger.info(message)

    rows = _panel_attendance_rows(db, filters, 'REPOSICION')
    attendance_ids = [r[0].id for r in rows]
    attendances_norm = _normalize_attendances(rows)

    inv_rows = _inventory_start_rows(db, attendance_ids)
    inventory_snapshot, expiration_rows = _replenishment_inventory_snapshot(db, inv_rows)
    pdv_by_city, activities_by_city = _city_breakdown(rows)

    products_count = len(inventory_snapshot)
    general = _build_general_indicators(
        attendances_norm,
        products_count,
        round(products_count / len(attendances_norm), 2) if attendances_norm else 0.0,
    )
    route_indicators = (
        _build_route_indicators(attendances_norm)
        if filters.route_id is not None else None
    )

    return ReplenishmentsPanelResponseSchema(
        filters_applied = filters,
        general_indicators = general,
        route_indicators = route_indicators,
        pdv_by_city = pdv_by_city,
        activities_by_city = activities_by_city,
        activities_by_day = _activities_by_day(attendances_norm),
        inventory_snapshot = inventory_snapshot,
        expirations = expiration_rows,
        sheet = _replenishment_sheet(db, inv_rows, rows, filters.company_id),
    )


# ---------------------------------------------------------------------------
# Route tracking (req 7.4.4)
# ---------------------------------------------------------------------------

def _attendance_for_point(db: Session, planned_point, filters, window, route):
    '''
        Finds the first attendance for a planned point within the target-day
        window, honouring the optional team_id / user_id filters.
    '''
    start_dt, end_dt = window
    att_q = db.query(Attendance).filter(
        Attendance.trade_planned_point_id == planned_point.id,
        Attendance.check_in_time.between(start_dt, end_dt),
    )
    if filters.team_id is not None:
        att_q = att_q.join(
            TradePlanningDetail,
            TradePlanningDetail.planned_route_id == route.id
        ).join(
            TradePlanning,
            TradePlanning.id == TradePlanningDetail.planning_id
        ).filter(TradePlanning.team_id == filters.team_id)
    if filters.user_id is not None:
        att_q = att_q.filter(Attendance.user_id == filters.user_id)
    return att_q.order_by(Attendance.check_in_time.asc()).first()


def _tracking_status(att) -> str:
    '''
        Maps an attendance (or its absence) to the tracking status label.
    '''
    if att and att.check_out_time:
        return 'CLOSED'
    if att:
        return 'OPEN'
    return 'PENDING'


def _impulse_tracking_inventory(db: Session, att):
    '''
        Per-product initial / sold / remaining rows for an IMPULSO point.
    '''
    starts = db.query(ImpulseInventoryStart).filter_by(attendance_id = att.id).all()
    sales = (
        db.query(ImpulseSaleDetail.product_id, func.sum(ImpulseSaleDetail.quantity))
        .join(ImpulseSale, ImpulseSale.id == ImpulseSaleDetail.impulse_sale_id)
        .filter(ImpulseSale.attendance_id == att.id)
        .group_by(ImpulseSaleDetail.product_id)
        .all()
    )
    sold_map = {pid: int(q or 0) for pid, q in sales}

    rows = []
    for start_row in starts:
        prod = db.query(Product).filter_by(id = start_row.product_id).first()
        if prod is None:
            continue
        initial = (start_row.quantity_in_room or 0) + (start_row.quantity_in_warehouse or 0)
        if initial == 0 and start_row.quantity is not None:
            initial = start_row.quantity
        sold = sold_map.get(start_row.product_id, 0)
        rows.append(RouteTrackingPosInventoryRow(
            product_id = start_row.product_id,
            sku = prod.sku,
            name = prod.name,
            quantity_initial = initial,
            quantity_sold = sold,
            quantity_remaining = max(initial - sold, 0),
        ))
    return rows


def _replenishment_tracking_inventory(db: Session, att, pos):
    '''
        Per-product sala/almacén rows (with minimum-stock stockout flag) for a
        REPOSICION point.
    '''
    starts = db.query(ImpulseInventoryStart).filter_by(attendance_id = att.id).all()
    rows = []
    for start_row in starts:
        prod = db.query(Product).filter_by(id = start_row.product_id).first()
        if prod is None:
            continue
        room = start_row.quantity_in_room or 0
        warehouse = start_row.quantity_in_warehouse or 0
        total = room + warehouse
        assignment = db.query(ProductAssignmentPOS).filter_by(
            product_id = start_row.product_id,
            point_of_sale_id = pos.id
        ).first()
        minimum = assignment.minimum_stock if assignment else None
        rows.append(RouteTrackingPosInventoryRow(
            product_id = start_row.product_id,
            sku = prod.sku,
            name = prod.name,
            quantity_in_room = room,
            quantity_in_warehouse = warehouse,
            quantity_total = total,
            quantity_minimum = minimum,
            stockout = (minimum is not None and total < minimum),
        ))
    return rows


def _track_point(db: Session, point_pair, filters, window, route):
    '''
        Resolves the tracking payload (status + inventory) for one planned
        point of the route.
    '''
    planned_point, pos = point_pair
    att = _attendance_for_point(db, planned_point, filters, window, route)
    status = _tracking_status(att)

    inventory_rows = []
    if att is not None:
        if filters.activity == 'IMPULSO':
            inventory_rows = _impulse_tracking_inventory(db, att)
        else:
            inventory_rows = _replenishment_tracking_inventory(db, att, pos)

    return RouteTrackingPointSchema(
        planned_point_id = planned_point.id,
        sequence = planned_point.sequence,
        pos_id = pos.id,
        pos_name = pos.name,
        latitude = getattr(pos, 'latitude', None),
        longitude = getattr(pos, 'longitude', None),
        planned_check_in_time = (
            planned_point.planned_check_in_time.isoformat()
            if isinstance(planned_point.planned_check_in_time, time) else None
        ),
        status = status,
        check_in_time = att.check_in_time if att else None,
        check_out_time = att.check_out_time if att else None,
        inventory = inventory_rows,
    )


def _track_route(db: Session, route, filters, window):
    '''
        Builds the tracking payload for a single route and its planned points.
    '''
    points = (
        db.query(PlannedPoint, PointOfSale)
        .join(PointOfSale, PointOfSale.id == PlannedPoint.point_of_sale_id)
        .filter(PlannedPoint.planned_route_id == route.id)
        .order_by(PlannedPoint.sequence.asc())
        .all()
    )
    point_payloads = [
        _track_point(db, pair, filters, window, route) for pair in points
    ]
    return RouteTrackingRouteSchema(
        route_id = route.id,
        route_name = route.route_name,
        route_code = route.route_code,
        color = route.color,
        activity = filters.activity,
        points = point_payloads,
    )


@handle_service_errors('REPORTS')
async def get_route_tracking_service(
    db: Session,
    filters: RouteTrackingFilterSchema,
) -> RouteTrackingResponseSchema:
    '''
        Returns one or many routes with their planned points + execution
        state, so the frontend can render the map (req 7.4.4).
    '''
    message = f'Generating route tracking for company {filters.company_id
            } on {filters.target_date} (activity={filters.activity}).'
    logger.info(message)

    routes_q = db.query(PlannedRoute).filter(
        PlannedRoute.company_id == filters.company_id,
        PlannedRoute.route_type == filters.activity,
    )
    if filters.route_id is not None:
        routes_q = routes_q.filter(PlannedRoute.id == filters.route_id)
    routes = routes_q.all()

    window = (
        datetime.combine(filters.target_date, time.min),
        datetime.combine(filters.target_date, time.max),
    )
    result_routes = [_track_route(db, route, filters, window) for route in routes]

    return RouteTrackingResponseSchema(
        filters_applied = filters,
        routes = result_routes,
    )
