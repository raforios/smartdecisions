'''
    Reports Service
    Contains the business logic for calculating KPIs and aggregating report data.
'''
from datetime import datetime, time
from sqlalchemy.orm import Session

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


def _empty_compliance_response(
    filters: ComplianceFilterSchema
) -> ComplianceReportResponseSchema:
    '''
        Zeroed compliance response used when no planned points match.
    '''
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


def _group_attendances_by_point(attendances) -> dict:
    '''
        Groups attendances by their planned-point id.
    '''
    grouped: dict[int, list] = {}
    for att in attendances:
        grouped.setdefault(att.trade_planned_point_id, []).append(att)
    return grouped


def _accumulate_compliance_bucket(bucket: dict, point, executed: bool) -> None:
    '''
        Adds one planned point to a compliance bucket (team or user). `executed`
        lets the user cut require a check-out while the team cut does not.
    '''
    bucket['planned'] += 1
    bucket['planned_mins'] += point.planned_workload_minutes or 0
    if point.is_adhoc:
        bucket['adhoc'] += 1
    if point.status == 'COMPLETED' and executed:
        bucket['executed'] += 1
        bucket['actual_minutes'] += point.actual_workload_minutes or 0
    elif point.status == 'CANCELLED':
        bucket['justified'] += 1
    else:
        bucket['pending'] += 1


def _aggregate_compliance(rows, attendances_by_point, filters):
    '''
        Walks every planned point building the team and user aggregation
        buckets. Team aggregation always counts; user aggregation only when a
        matching Attendance exists.
    '''
    team_data: dict[int, dict] = {}
    user_data: dict[tuple[int, int], dict] = {}
    team_users: dict[int, set[int]] = {}

    for point, team_id, _date_of_day in rows:
        team_bucket = team_data.setdefault(team_id, _empty_stats())
        _accumulate_compliance_bucket(team_bucket, point, executed = True)

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
            user_bucket = user_data.setdefault((team_id, att.user_id), _empty_stats())
            _accumulate_compliance_bucket(
                user_bucket, point, executed = att.check_out_time is not None
            )

    return team_data, user_data, team_users


def _compliance_team_details(team_data, team_users):
    '''
        Builds the per-team detail rows and the planned / executed totals.
    '''
    details: list[ComplianceTeamStatsSchema] = []
    total_planned = 0
    total_executed = 0
    for tid, stats in team_data.items():
        comp_pct = (stats['executed'] / stats['planned'] * 100) if stats['planned'] > 0 else 0
        total_planned += stats['planned']
        total_executed += stats['executed']
        details.append(ComplianceTeamStatsSchema(
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
    return details, total_planned, total_executed


def _compliance_user_details(user_data):
    '''
        Builds the per-user detail rows.
    '''
    details: list[ComplianceUserStatsSchema] = []
    for (tid, uid), stats in user_data.items():
        comp_pct = (stats['executed'] / stats['planned'] * 100) if stats['planned'] > 0 else 0
        details.append(ComplianceUserStatsSchema(
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
    return details


def _compliance_global_stats(team_data, user_data, total_planned, total_executed):
    '''
        Builds the global compliance stats block.
    '''
    global_pct = (total_executed / total_planned * 100) if total_planned > 0 else 0
    return ComplianceGlobalStatsSchema(
        total_teams = len(team_data),
        total_users = len(user_data),
        global_compliance_percentage = round(global_pct, 2),
        total_planned_visits = total_planned,
        total_executed_visits = total_executed
    )


@handle_service_errors('REPORTS')
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

    # 1. Build the planning query joined through the full hierarchy. The date
    # range applies to TradePlanningDetail.date_of_day (the day the route is
    # meant to be executed).
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
        return _empty_compliance_response(filters)

    # 2. Attribute execution to the operator through the Attendance rows.
    point_ids = [p.id for (p, _t, _d) in rows]
    attendances = db.query(Attendance).filter(
        Attendance.trade_planned_point_id.in_(point_ids),
        Attendance.company_id == filters.company_id
    ).all()
    attendances_by_point = _group_attendances_by_point(attendances)

    # 3. Aggregate per team and per user, then build the detail cuts.
    team_data, user_data, team_users = _aggregate_compliance(
        rows, attendances_by_point, filters
    )
    team_details, total_planned, total_executed = _compliance_team_details(
        team_data, team_users
    )
    user_details = _compliance_user_details(user_data)

    return ComplianceReportResponseSchema(
        period_start = filters.start_date,
        period_end = filters.end_date,
        global_stats = _compliance_global_stats(
            team_data, user_data, total_planned, total_executed
        ),
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
