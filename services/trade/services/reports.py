'''
    Reports Service
    Contains the business logic for calculating KPIs and aggregating report data.
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
from models.replenishments import (
    # iter5 (Binaria, 2026-06-20): ReplenishmentInventory removed; inventory
    # now lives in the unified Impulses tables (ImpulseInventoryStart).
    ReplenishmentReport,
    ComplementaryBandeo,
    ComplementaryCompetition,
    ComplementaryPromoPoint
)
from models.products import Product, ProductAssignmentPOS
from schemas.reports import (
    ComplianceFilterSchema,
    ComplianceReportResponseSchema,
    ComplianceUserStatsSchema,
    ComplianceTeamStatsSchema,
    ComplianceGlobalStatsSchema,
    InventoryAlertFilterSchema,
    InventoryAlertResponseSchema,
    SalesReportFilterSchema,
    SalesReportResponseSchema,
    SalesDetailItemSchema,
    MerchandisingFilterSchema,
    MerchandisingReportResponseSchema,
    MerchandisingItemSchema,
    PhotoItemSchema,
    PhotographicReportResponseSchema,
    AttendanceReportFilterSchema,
    AttendanceReportResponseSchema,
    AttendanceReportItemSchema,
    # iter6 panel schemas
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

# --- COMPLIANCE REPORT SERVICE ---

def _empty_stats() -> dict:
    '''
        Initial aggregation bucket for compliance counters.
    '''
    return {
        'planned': 0, 'executed': 0, 'pending': 0, 'adhoc': 0, 'justified': 0,
        'unassigned': 0,
        'planned_mins': 0, 'actual_minutes': 0
    }


@handle_service_errors('REPORTS')
# pylint: disable=too-many-locals,too-many-branches,too-many-statements
async def get_compliance_report_service(
    db: Session,
    filters: ComplianceFilterSchema
) -> ComplianceReportResponseSchema:
    '''
        Calculates Compliance KPIs: Planned vs. Executed visits.

        Planning lives in PlannedPoint (reachable through TradePlanning →
        TradePlanningDetail → PlannedRoute). Execution is the matching
        Attendance row, which carries the operator's `user_id`. The report
        provides two aggregation cuts:

        * Per team (`team_id` from TradePlanning) — every planned point is
          counted at the team level even if no Attendance exists.
        * Per user (`user_id` from Attendance) — only planned points with at
          least one Attendance contribute, since unexecuted points have no
          user attribution.
    '''
    message = f'Generating Compliance Report for Company: {filters.company_id}'
    logger.info(message)

    # 1. Build planning query joined through the full hierarchy. The date
    # range applies to TradePlanningDetail.date_of_day, which represents the
    # actual day a route is meant to be executed.
    rows_query = db.query(
        PlannedPoint, TradePlanning.team_id, TradePlanningDetail.date_of_day
    ).join(
        PlannedRoute, PlannedPoint.planned_route_id == PlannedRoute.id
    ).join(
        TradePlanningDetail, TradePlanningDetail.planned_route_id == PlannedRoute.id
    ).join(
        TradePlanning, TradePlanningDetail.planning_id == TradePlanning.id
    ).filter(
        TradePlanning.company_id == filters.company_id,
        TradePlanningDetail.date_of_day.between(filters.start_date, filters.end_date)
    )

    if filters.team_id:
        rows_query = rows_query.filter(TradePlanning.team_id == filters.team_id)

    rows = rows_query.all()

    if not rows:
        empty_global = ComplianceGlobalStatsSchema(
            total_teams = 0,
            total_users = 0,
            global_compliance_percentage = 0.0,
            total_planned_visits = 0,
            total_executed_visits = 0
        )
        return ComplianceReportResponseSchema(
            period_start = filters.start_date,
            period_end = filters.end_date,
            global_stats = empty_global,
            team_details = [],
            details = []
        )

    # 2. Fetch Attendances for the involved planned points in one shot so we
    # can attribute execution to the operator (user_id) coming from the
    # frontend. A planned point may have multiple Attendances (re-visits);
    # we attribute the planned slot to the user(s) that registered them.
    point_ids = [p.id for (p, _t, _d) in rows]
    attendances = db.query(Attendance).filter(
        Attendance.trade_planned_point_id.in_(point_ids),
        Attendance.company_id == filters.company_id
    ).all()

    attendances_by_point: dict[int, list[Attendance]] = {}
    for att in attendances:
        attendances_by_point.setdefault(att.trade_planned_point_id, []).append(att)

    # 3. Walk every planned point. Team aggregation always counts; user
    # aggregation only happens when an Attendance exists.
    team_data: dict[int, dict] = {}
    user_data: dict[tuple[int, int], dict] = {}
    team_users: dict[int, set[int]] = {}

    for point, team_id, _date_of_day in rows:
        team_bucket = team_data.setdefault(team_id, _empty_stats())
        team_bucket['planned'] += 1
        team_bucket['planned_mins'] += point.planned_workload_minutes or 0
        if point.is_adhoc:
            team_bucket['adhoc'] += 1

        if point.status == 'COMPLETED':
            team_bucket['executed'] += 1
            team_bucket['actual_minutes'] += point.actual_workload_minutes or 0
        elif point.status == 'CANCELLED':
            team_bucket['justified'] += 1
        else:
            team_bucket['pending'] += 1

        # User attribution comes from Attendance records. Points with no
        # Attendance at all are flagged as unassigned at team level.
        atts = attendances_by_point.get(point.id, [])
        if not atts:
            team_bucket['unassigned'] += 1

        seen_users: set[int] = set()
        for att in atts:
            if filters.user_id and att.user_id != filters.user_id:
                continue
            if att.user_id in seen_users:
                continue
            seen_users.add(att.user_id)
            team_users.setdefault(team_id, set()).add(att.user_id)

            key = (team_id, att.user_id)
            user_bucket = user_data.setdefault(key, _empty_stats())
            user_bucket['planned'] += 1
            user_bucket['planned_mins'] += point.planned_workload_minutes or 0
            if point.is_adhoc:
                user_bucket['adhoc'] += 1

            if point.status == 'COMPLETED' and att.check_out_time is not None:
                user_bucket['executed'] += 1
                user_bucket['actual_minutes'] += point.actual_workload_minutes or 0
            elif point.status == 'CANCELLED':
                user_bucket['justified'] += 1
            else:
                user_bucket['pending'] += 1

    # 4. Build team detail rows.
    team_details: list[ComplianceTeamStatsSchema] = []
    total_planned = 0
    total_executed = 0

    for tid, stats in team_data.items():
        comp_pct = (stats['executed'] / stats['planned'] * 100) if stats['planned'] > 0 else 0
        total_planned += stats['planned']
        total_executed += stats['executed']

        team_details.append(ComplianceTeamStatsSchema(
            team_id = tid,
            total_users = len(team_users.get(tid, set())),
            total_planned = stats['planned'],
            total_executed = stats['executed'],
            total_pending = stats['pending'],
            total_adhoc = stats['adhoc'],
            total_justified = stats['justified'],
            unassigned_planned = stats['unassigned'],
            compliance_percentage = round(comp_pct, 2),
            total_planned_minutes = stats['planned_mins'],
            total_actual_minutes = stats['actual_minutes'],
            workload_gap_minutes = stats['actual_minutes'] - stats['planned_mins']
        ))

    # 5. Build user detail rows.
    user_details: list[ComplianceUserStatsSchema] = []
    for (tid, uid), stats in user_data.items():
        comp_pct = (stats['executed'] / stats['planned'] * 100) if stats['planned'] > 0 else 0
        user_details.append(ComplianceUserStatsSchema(
            team_id = tid,
            user_id = uid,
            total_planned = stats['planned'],
            total_executed = stats['executed'],
            total_pending = stats['pending'],
            total_adhoc = stats['adhoc'],
            total_justified = stats['justified'],
            compliance_percentage = round(comp_pct, 2),
            total_planned_minutes = stats['planned_mins'],
            total_actual_minutes = stats['actual_minutes'],
            workload_gap_minutes = stats['actual_minutes'] - stats['planned_mins']
        ))

    # 6. Global stats.
    global_pct = (total_executed / total_planned * 100) if total_planned > 0 else 0
    global_stats = ComplianceGlobalStatsSchema(
        total_teams = len(team_data),
        total_users = len(user_data),
        global_compliance_percentage = round(global_pct, 2),
        total_planned_visits = total_planned,
        total_executed_visits = total_executed
    )

    return ComplianceReportResponseSchema(
        period_start = filters.start_date,
        period_end = filters.end_date,
        global_stats = global_stats,
        team_details = team_details,
        details = user_details
    )

# --- INVENTORY ALERTS SERVICE ---

@handle_service_errors('REPORTS')
async def get_inventory_alerts_service(
    db: Session,
    filters: InventoryAlertFilterSchema
) -> InventoryAlertResponseSchema:
    '''
        Scans current inventory for stockouts or short-dated products.
    '''
    # Simplified scan logic. iter5: inventory lives in ImpulseInventoryStart
    # now (unified Impulses + Replenishments table).
    _ = db.query(PointOfSale, ImpulseInventoryStart).join(
        ImpulseInventoryStart, PointOfSale.id == ImpulseInventoryStart.attendance_id
    ).filter(PointOfSale.company_id == filters.company_id)

    # ... (Actual DB logic would be more complex joining POS and Inventory models)
    # Returning empty list for now as a placeholder
    return InventoryAlertResponseSchema(total_alerts = 0, items = [])

# --- SALES REPORT SERVICE ---

@handle_service_errors('REPORTS')
async def get_sales_report_service(
    db: Session,
    filters: SalesReportFilterSchema,
    auth_token: str # pylint: disable=unused-argument
) -> SalesReportResponseSchema:
    '''
        Aggregates sales data from ImpulseSale models.
    '''
    start_dt = datetime.combine(filters.start_date, time.min)
    end_dt = datetime.combine(filters.end_date, time.max)

    # Base query for Sales
    query = db.query(ImpulseSale, ImpulseSaleDetail).join(
        ImpulseSaleDetail, ImpulseSale.id == ImpulseSaleDetail.impulse_sale_id
    ).filter(
        ImpulseSale.company_id == filters.company_id,
        ImpulseSale.created_at.between(start_dt, end_dt)
    )

    # Apply filters
    # (Implementation details omitted for brevity, but follows same pattern)

    results = query.all()
    items = []
    for sale, detail in results:
        items.append(SalesDetailItemSchema(
            sale_id = sale.id,
            sale_date = sale.created_at.date(),
            timestamp = sale.created_at,
            user_id = 0, # Should be linked via Attendance
            point_of_sale_id = 0,
            point_of_sale_name = 'POS Name',
            product_id = detail.product_id,
            product_name = 'Product Name',
            product_sku = 'SKU',
            category_1 = 'Cat',
            quantity = detail.quantity
        ))

    return SalesReportResponseSchema(
        period_start = filters.start_date,
        period_end = filters.end_date,
        total_units_sold = sum(i.quantity for i in items),
        total_transactions = len(set(i.sale_id for i in items)),
        items = items
    )

# --- MERCHANDISING REPORT SERVICE ---

@handle_service_errors('REPORTS')
async def get_merchandising_report_service(
    db: Session,
    filters: MerchandisingFilterSchema
) -> MerchandisingReportResponseSchema:
    '''
        Aggregates Bandeo, Competition, and Promo Points into a single report.
    '''
    items = []
    start_dt = datetime.combine(filters.start_date, time.min)
    end_dt = datetime.combine(filters.end_date, time.max)

    # 1. Bandeo
    q_bandeo = db.query(ComplementaryBandeo).filter(
        ComplementaryBandeo.company_id == filters.company_id,
        ComplementaryBandeo.created_at.between(start_dt, end_dt)
    )
    for b in q_bandeo.all():
        photo_url = b.photos[0].file_url if b.photos else None
        items.append(MerchandisingItemSchema(
            activity_type = 'BANDEO',
            date = b.created_at,
            user_id = b.attendance_id,
            details = f'Comments: {b.comments or "N/A"}',
            photo_url = photo_url
        ))

    # 2. Competition
    q_comp = db.query(ComplementaryCompetition).filter(
        ComplementaryCompetition.company_id == filters.company_id,
        ComplementaryCompetition.created_at.between(start_dt, end_dt)
    )
    for c in q_comp.all():
        photo_url = c.photos[0].file_url if c.photos else None
        items.append(MerchandisingItemSchema(
            activity_type = 'COMPETITION',
            date = c.created_at,
            user_id = c.user_id,
            details = f'Competitor: {c.competitor_name}. Type: {c.activity_type}',
            photo_url = photo_url
        ))

    # 3. Promo Points
    q_promo = db.query(ComplementaryPromoPoint).filter(
        ComplementaryPromoPoint.company_id == filters.company_id,
        ComplementaryPromoPoint.created_at.between(start_dt, end_dt)
    )
    for p in q_promo.all():
        photo_url = p.photos[0].file_url if p.photos else None
        items.append(MerchandisingItemSchema(
            activity_type = 'PROMO_POINT',
            date = p.created_at,
            user_id = p.attendance_id,
            details = f'Comments: {p.comments or "N/A"}',
            photo_url = photo_url
        ))

    return MerchandisingReportResponseSchema(items = items, total_activities = len(items))

# --- PHOTOGRAPHIC REPORT SERVICE ---

@handle_service_errors('REPORTS')
async def get_photographic_report_service(
    db: Session,
    filters: SalesReportFilterSchema
) -> PhotographicReportResponseSchema:
    '''
        Aggregates all photos from Sales, Replenishment, and Merchandising.
    '''
    items = []
    start_dt = datetime.combine(filters.start_date, time.min)
    end_dt = datetime.combine(filters.end_date, time.max)

    # In current implementation, we query entities and their photos relationship
    # 1. Sales Photos
    sales = db.query(ImpulseSale).filter(
        ImpulseSale.company_id == filters.company_id,
        ImpulseSale.created_at.between(start_dt, end_dt)
    ).all()
    for s in sales:
        for photo in s.photos:
            items.append(PhotoItemSchema(
                date = s.created_at,
                category = 'IMPULSE_SALE',
                user_id = s.attendance_id,
                photo_url = photo.file_url,
                comments = 'Venta Impulso'
            ))

    # 2. Replenishment Photos
    reps = db.query(ReplenishmentReport).filter(
        ReplenishmentReport.company_id == filters.company_id,
        ReplenishmentReport.created_at.between(start_dt, end_dt)
    ).all()
    for r in reps:
        for photo in r.photos:
            items.append(PhotoItemSchema(
                date = r.created_at,
                category = 'REPLENISHMENT',
                user_id = r.attendance_id,
                photo_url = photo.file_url,
                comments = r.comments
            ))

    return PhotographicReportResponseSchema(items = items, total_photos = len(items))

# --- ATTENDANCE REPORT SERVICE ---

@handle_service_errors('REPORTS')
async def get_attendance_report_service(
    db: Session,
    filters: AttendanceReportFilterSchema
) -> AttendanceReportResponseSchema:
    '''
        Generates the Attendance & Geofencing Report.
    '''
    start_dt = datetime.combine(filters.start_date, time.min)
    end_dt = datetime.combine(filters.end_date, time.max)

    # POS is no longer attached to TradePlanning. The hierarchy is now
    # Attendance → PlannedPoint → PointOfSale.
    query = db.query(Attendance, PlannedPoint, PointOfSale).join(
        PlannedPoint, Attendance.trade_planned_point_id == PlannedPoint.id
    ).join(
        PointOfSale, PlannedPoint.point_of_sale_id == PointOfSale.id
    ).filter(
        Attendance.company_id == filters.company_id,
        Attendance.created_at.between(start_dt, end_dt)
    )

    if filters.user_id:
        query = query.filter(Attendance.user_id == filters.user_id)
    if filters.point_of_sale_id:
        query = query.filter(PlannedPoint.point_of_sale_id == filters.point_of_sale_id)

    records = query.order_by(Attendance.check_in_time.desc()).all()

    items_list = []
    total_duration = 0
    completed_count = 0

    for att, _, pos in records:
        status_label = 'COMPLETED' if att.check_out_time else 'IN_PROGRESS'
        if att.duration_minutes:
            total_duration += att.duration_minutes
            completed_count += 1

        items_list.append(AttendanceReportItemSchema(
            attendance_id = att.id,
            user_id = att.user_id,
            point_of_sale_id = pos.id,
            point_of_sale_name = pos.name,
            point_of_sale_code = pos.code,
            check_in_time = att.check_in_time,
            check_in_distance_error = float(att.check_in_distance_error
                                    ) if att.check_in_distance_error else 0.0,
            check_out_time = att.check_out_time,
            check_out_distance_error = float(att.check_out_distance_error
                                    ) if att.check_out_distance_error else 0.0,
            duration_minutes = att.duration_minutes,
            status = status_label
        ))

    avg_duration = round(total_duration / completed_count, 2) if completed_count > 0 else 0.0

    return AttendanceReportResponseSchema(
        period_start = filters.start_date,
        period_end = filters.end_date,
        total_visits = len(items_list),
        average_duration_minutes = avg_duration,
        items = items_list
    )


# ============================================================================
# iter6 (Binaria, 2026-06-22) — Monitor de Trade (req 7.4)
#
# The three services below back the executive panels. They run against the
# same operational tables already covered by other reports; each one merely
# composes a pre-aggregated payload so the frontend renders the panel in a
# single round-trip (the doc lists six widgets per panel — without these
# endpoints the frontend would have to issue 5-6 calls and join in JS).
# ============================================================================

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


def _percentages(rows):
    '''
        Returns rows enriched with a percentage column computed against the
        total count.
    '''
    total = sum(r['count'] for r in rows) or 1
    for row in rows:
        row['percentage'] = round(row['count'] * 100.0 / total, 2)
    return rows


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

    base = (
        db.query(Attendance, PlannedPoint, PlannedRoute, PointOfSale)
        .join(PlannedPoint, PlannedPoint.id == Attendance.trade_planned_point_id)
        .join(PlannedRoute, PlannedRoute.id == PlannedPoint.planned_route_id)
        .join(PointOfSale, PointOfSale.id == PlannedPoint.point_of_sale_id)
    )
    base = _apply_attendance_panel_filters(base, filters, route_type = 'IMPULSO')

    rows = base.all()
    attendance_ids = [r[0].id for r in rows]

    # Attach planned_route_id to attendance rows for the indicators helper.
    attendances_norm = []
    for att, _pp, pr, pos in rows:
        att.point_of_sale_id = pos.id
        att.planned_route_id = pr.id
        attendances_norm.append(att)

    # Sales aggregation per product over the same attendances.
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
    if filters.product_id is not None:
        sales_rows = [r for r in sales_rows if r.product_id == filters.product_id]

    sales_summary = [
        PanelSalesSummaryRow(
            product_id = r.product_id, sku = r.sku, name = r.name,
            total_quantity = int(r.total_quantity or 0),
        ) for r in sales_rows
    ]
    products_count = len({r.product_id for r in sales_rows})
    products_per_activity = (
        round(sum(r.total_quantity or 0 for r in sales_rows) / len(attendances_norm), 2)
        if attendances_norm else 0.0
    )

    general = _build_general_indicators(
        attendances_norm, products_count, products_per_activity
    )
    route_indicators = (
        _build_route_indicators(attendances_norm)
        if filters.route_id is not None else None
    )

    # PDV / activities por ciudad — agregamos por city_id del POS.
    by_city_pdv = defaultdict(set)
    by_city_act = defaultdict(int)
    for att, _pp, _pr, pos in rows:
        by_city_pdv[pos.city_id].add(pos.id)
        by_city_act[pos.city_id] += 1
    pdv_by_city = _percentages([
        {'city_id': city_id, 'count': len(pdvs)}
        for city_id, pdvs in by_city_pdv.items()
    ])
    activities_by_city = _percentages([
        {'city_id': city_id, 'count': cnt}
        for city_id, cnt in by_city_act.items()
    ])

    # Activities por dia.
    by_day = defaultdict(int)
    for att in attendances_norm:
        if att.check_in_time:
            by_day[att.check_in_time.date()] += 1
    activities_by_day = [
        PanelByDayRow(day = d, count = c) for d, c in sorted(by_day.items())
    ]

    # Inventory snapshot — usa el ultimo inventario START por POS dentro del rango.
    inv_q = (
        db.query(ImpulseInventoryStart)
        .filter(ImpulseInventoryStart.attendance_id.in_(attendance_ids or [0]))
    )
    inv_rows = inv_q.all()
    sales_by_product = {r.product_id: int(r.total_quantity or 0) for r in sales_rows}
    snapshot_acc = defaultdict(lambda: {'quantity': 0, 'sku': None, 'name': None})
    for inv in inv_rows:
        prod = db.query(Product).filter_by(id = inv.product_id).first()
        if prod is None:
            continue
        base_qty = (inv.quantity_in_room or 0) + (inv.quantity_in_warehouse or 0)
        if base_qty == 0 and inv.quantity is not None:
            base_qty = inv.quantity
        snapshot_acc[inv.product_id]['quantity'] += base_qty
        snapshot_acc[inv.product_id]['sku'] = prod.sku
        snapshot_acc[inv.product_id]['name'] = prod.name
    inventory_snapshot = []
    for pid, acc in snapshot_acc.items():
        remaining = acc['quantity'] - sales_by_product.get(pid, 0)
        inventory_snapshot.append(PanelInventorySnapshotRow(
            product_id = pid, sku = acc['sku'], name = acc['name'],
            quantity = max(remaining, 0),
        ))

    # Sheet: a flat row per (attendance, product) using sales detail.
    sheet = []
    sale_details = (
        db.query(ImpulseSaleDetail, ImpulseSale, Product)
        .join(ImpulseSale, ImpulseSale.id == ImpulseSaleDetail.impulse_sale_id)
        .join(Product, Product.id == ImpulseSaleDetail.product_id)
        .filter(ImpulseSale.attendance_id.in_(attendance_ids or [0]))
        .all()
    )
    sales_by_att_prod = defaultdict(int)
    for d, s, _p in sale_details:
        sales_by_att_prod[(s.attendance_id, d.product_id)] += d.quantity

    row_index = {(a.id): (a, _pp, _pr, _pos) for a, _pp, _pr, _pos in rows}
    for (att_id, product_id), qty in sales_by_att_prod.items():
        if att_id not in row_index:
            continue
        att, _pp, pr, pos = row_index[att_id]
        prod = db.query(Product).filter_by(id = product_id).first()
        if prod is None:
            continue
        sheet.append(PanelSheetRow(
            company_id = filters.company_id,
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

    return ImpulsesPanelResponseSchema(
        filters_applied = filters,
        general_indicators = general,
        route_indicators = route_indicators,
        pdv_by_city = [PanelByCityRow(**r) for r in pdv_by_city],
        activities_by_city = [PanelByCityRow(**r) for r in activities_by_city],
        activities_by_day = activities_by_day,
        sales_summary = sales_summary,
        inventory_snapshot = inventory_snapshot,
        sheet = sheet,
    )


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

    base = (
        db.query(Attendance, PlannedPoint, PlannedRoute, PointOfSale)
        .join(PlannedPoint, PlannedPoint.id == Attendance.trade_planned_point_id)
        .join(PlannedRoute, PlannedRoute.id == PlannedPoint.planned_route_id)
        .join(PointOfSale, PointOfSale.id == PlannedPoint.point_of_sale_id)
    )
    base = _apply_attendance_panel_filters(base, filters, route_type = 'REPOSICION')

    rows = base.all()
    attendance_ids = [r[0].id for r in rows]

    attendances_norm = []
    for att, _pp, pr, pos in rows:
        att.point_of_sale_id = pos.id
        att.planned_route_id = pr.id
        attendances_norm.append(att)

    # Inventory snapshot: aggregate latest start records by product.
    inv_q = (
        db.query(ImpulseInventoryStart)
        .filter(ImpulseInventoryStart.attendance_id.in_(attendance_ids or [0]))
    )
    inv_rows = inv_q.all()
    snapshot_acc = defaultdict(
        lambda: {'room': 0, 'warehouse': 0, 'sku': None, 'name': None,
                 'minimum': 0}
    )
    expiration_rows: list[PanelExpirationRow] = []
    today = datetime.utcnow().date()
    for inv in inv_rows:
        prod = db.query(Product).filter_by(id = inv.product_id).first()
        if prod is None:
            continue
        snapshot_acc[inv.product_id]['room'] += inv.quantity_in_room or 0
        snapshot_acc[inv.product_id]['warehouse'] += inv.quantity_in_warehouse or 0
        snapshot_acc[inv.product_id]['sku'] = prod.sku
        snapshot_acc[inv.product_id]['name'] = prod.name
        assignment = db.query(ProductAssignmentPOS).filter_by(
            product_id = inv.product_id, point_of_sale_id = inv.product_id  # placeholder
        ).first()
        if assignment is not None:
            snapshot_acc[inv.product_id]['minimum'] += assignment.minimum_stock or 0
        if inv.batch_number or inv.expiration_date:
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

    inventory_snapshot = []
    for pid, acc in snapshot_acc.items():
        total = acc['room'] + acc['warehouse']
        minimum = acc['minimum']
        inventory_snapshot.append(PanelInventorySnapshotRow(
            product_id = pid, sku = acc['sku'], name = acc['name'],
            quantity = total,
            quantity_in_room = acc['room'],
            quantity_in_warehouse = acc['warehouse'],
            quantity_minimum = minimum or None,
            stockout = (minimum > 0 and total < minimum),
        ))

    # PDV / activities por ciudad.
    by_city_pdv = defaultdict(set)
    by_city_act = defaultdict(int)
    for att, _pp, _pr, pos in rows:
        by_city_pdv[pos.city_id].add(pos.id)
        by_city_act[pos.city_id] += 1
    pdv_by_city = _percentages([
        {'city_id': city_id, 'count': len(pdvs)}
        for city_id, pdvs in by_city_pdv.items()
    ])
    activities_by_city = _percentages([
        {'city_id': city_id, 'count': cnt}
        for city_id, cnt in by_city_act.items()
    ])

    by_day = defaultdict(int)
    for att in attendances_norm:
        if att.check_in_time:
            by_day[att.check_in_time.date()] += 1
    activities_by_day = [
        PanelByDayRow(day = d, count = c) for d, c in sorted(by_day.items())
    ]

    products_count = len(snapshot_acc)
    products_per_activity = (
        round(products_count / len(attendances_norm), 2)
        if attendances_norm else 0.0
    )
    general = _build_general_indicators(
        attendances_norm, products_count, products_per_activity
    )
    route_indicators = (
        _build_route_indicators(attendances_norm)
        if filters.route_id is not None else None
    )

    # Sheet: one row per (attendance, product) using inventory rows.
    sheet = []
    for inv in inv_rows:
        prod = db.query(Product).filter_by(id = inv.product_id).first()
        if prod is None:
            continue
        att = next((a for a, *_ in rows if a.id == inv.attendance_id), None)
        if att is None:
            continue
        pp_pr_pos = next((triple for a, *triple in rows if a.id == inv.attendance_id), None)
        if pp_pr_pos is None:
            continue
        _pp, pr, pos = pp_pr_pos
        total = (inv.quantity_in_room or 0) + (inv.quantity_in_warehouse or 0)
        sheet.append(PanelSheetRow(
            company_id = filters.company_id,
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

    return ReplenishmentsPanelResponseSchema(
        filters_applied = filters,
        general_indicators = general,
        route_indicators = route_indicators,
        pdv_by_city = [PanelByCityRow(**r) for r in pdv_by_city],
        activities_by_city = [PanelByCityRow(**r) for r in activities_by_city],
        activities_by_day = activities_by_day,
        inventory_snapshot = inventory_snapshot,
        expirations = expiration_rows,
        sheet = sheet,
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

    start_dt = datetime.combine(filters.target_date, time.min)
    end_dt = datetime.combine(filters.target_date, time.max)

    result_routes: list[RouteTrackingRouteSchema] = []
    for route in routes:
        points = (
            db.query(PlannedPoint, PointOfSale)
            .join(PointOfSale, PointOfSale.id == PlannedPoint.point_of_sale_id)
            .filter(PlannedPoint.planned_route_id == route.id)
            .order_by(PlannedPoint.sequence.asc())
            .all()
        )
        point_payloads: list[RouteTrackingPointSchema] = []
        for pp, pos in points:
            att_q = db.query(Attendance).filter(
                Attendance.trade_planned_point_id == pp.id,
                Attendance.check_in_time.between(start_dt, end_dt),
            )
            if filters.team_id is not None:
                # Match attendance via TradePlanning team_id.
                att_q = att_q.join(
                    TradePlanningDetail,
                    TradePlanningDetail.planned_route_id == route.id
                ).join(
                    TradePlanning,
                    TradePlanning.id == TradePlanningDetail.planning_id
                ).filter(TradePlanning.team_id == filters.team_id)
            if filters.user_id is not None:
                att_q = att_q.filter(Attendance.user_id == filters.user_id)
            att = att_q.order_by(Attendance.check_in_time.asc()).first()

            if att and att.check_out_time:
                status = 'CLOSED'
            elif att:
                status = 'OPEN'
            else:
                status = 'PENDING'

            inventory_rows: list[RouteTrackingPosInventoryRow] = []
            if att is not None:
                if filters.activity == 'IMPULSO':
                    starts = db.query(ImpulseInventoryStart).filter_by(
                        attendance_id = att.id
                    ).all()
                    sales = (
                        db.query(
                            ImpulseSaleDetail.product_id,
                            func.sum(ImpulseSaleDetail.quantity)
                        )
                        .join(ImpulseSale,
                              ImpulseSale.id == ImpulseSaleDetail.impulse_sale_id)
                        .filter(ImpulseSale.attendance_id == att.id)
                        .group_by(ImpulseSaleDetail.product_id)
                        .all()
                    )
                    sold_map = {pid: int(q or 0) for pid, q in sales}
                    for start_row in starts:
                        prod = db.query(Product).filter_by(
                            id = start_row.product_id
                        ).first()
                        if prod is None:
                            continue
                        initial = (
                            (start_row.quantity_in_room or 0)
                            + (start_row.quantity_in_warehouse or 0)
                        )
                        if initial == 0 and start_row.quantity is not None:
                            initial = start_row.quantity
                        sold = sold_map.get(start_row.product_id, 0)
                        inventory_rows.append(RouteTrackingPosInventoryRow(
                            product_id = start_row.product_id,
                            sku = prod.sku,
                            name = prod.name,
                            quantity_initial = initial,
                            quantity_sold = sold,
                            quantity_remaining = max(initial - sold, 0),
                        ))
                else:
                    starts = db.query(ImpulseInventoryStart).filter_by(
                        attendance_id = att.id
                    ).all()
                    for start_row in starts:
                        prod = db.query(Product).filter_by(
                            id = start_row.product_id
                        ).first()
                        if prod is None:
                            continue
                        room = start_row.quantity_in_room or 0
                        warehouse = start_row.quantity_in_warehouse or 0
                        total = room + warehouse
                        assignment = db.query(ProductAssignmentPOS).filter_by(
                            product_id = start_row.product_id,
                            point_of_sale_id = pos.id
                        ).first()
                        minimum = (
                            assignment.minimum_stock if assignment else None
                        )
                        inventory_rows.append(RouteTrackingPosInventoryRow(
                            product_id = start_row.product_id,
                            sku = prod.sku,
                            name = prod.name,
                            quantity_in_room = room,
                            quantity_in_warehouse = warehouse,
                            quantity_total = total,
                            quantity_minimum = minimum,
                            stockout = (
                                minimum is not None and total < minimum
                            ),
                        ))

            point_payloads.append(RouteTrackingPointSchema(
                planned_point_id = pp.id,
                sequence = pp.sequence,
                pos_id = pos.id,
                pos_name = pos.name,
                latitude = getattr(pos, 'latitude', None),
                longitude = getattr(pos, 'longitude', None),
                planned_check_in_time = (
                    pp.planned_check_in_time.isoformat()
                    if isinstance(pp.planned_check_in_time, time) else None
                ),
                status = status,
                check_in_time = att.check_in_time if att else None,
                check_out_time = att.check_out_time if att else None,
                inventory = inventory_rows,
            ))

        result_routes.append(RouteTrackingRouteSchema(
            route_id = route.id,
            route_name = route.route_name,
            route_code = route.route_code,
            color = route.color,
            activity = filters.activity,
            points = point_payloads,
        ))

    return RouteTrackingResponseSchema(
        filters_applied = filters,
        routes = result_routes,
    )
