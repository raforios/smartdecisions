'''
    Reports Service
    Contains the business logic for calculating KPIs and aggregating report data.
'''
from datetime import datetime, time
from sqlalchemy.orm import Session

from models.trade import TradePlanning, Attendance
from models.pos import PointOfSale
from models.impulses import ImpulseSale, ImpulseSaleDetail
from models.replenishments import (
    ReplenishmentReport,
    ReplenishmentInventory,
    ComplementaryBandeo,
    ComplementaryCompetition,
    ComplementaryPromoPoint
)
from schemas.reports import (
    ComplianceFilterSchema,
    ComplianceReportResponseSchema,
    ComplianceUserStatsSchema,
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
    AttendanceReportItemSchema
)
from services.logger_config import custom_logger as logger
from services.utils import handle_service_errors

# --- COMPLIANCE REPORT SERVICE ---

@handle_service_errors('REPORTS')
async def get_compliance_report_service(
    db: Session,
    filters: ComplianceFilterSchema
) -> ComplianceReportResponseSchema:
    '''
        Calculates Compliance KPIs: Planned vs. Executed visits.
    '''
    message = f'Generating Compliance Report for Company: {filters.company_id}'
    logger.info(message)

    # 1. Define time range
    start_dt = datetime.combine(filters.start_date, time.min)
    end_dt = datetime.combine(filters.end_date, time.max)

    # 2. Base Query for Planning
    query = db.query(TradePlanning).filter(
        TradePlanning.company_id == filters.company_id,
        TradePlanning.created_at.between(start_dt, end_dt)
    )

    if filters.user_id:
        query = query.filter(TradePlanning.user_id == filters.user_id)

    plans = query.all()

    # 3. Group by User
    user_data = {}
    for p in plans:
        uid = p.user_id
        if uid not in user_data:
            user_data[uid] = {
                'planned': 0, 'executed': 0, 'pending': 0, 'adhoc': 0, 'justified': 0,
                'planned_mins': 0, 'actual_minutes': 0
            }

        user_data[uid]['planned'] += 1
        user_data[uid]['planned_mins'] += p.planned_workload_minutes

        if p.status == 'COMPLETED':
            user_data[uid]['executed'] += 1
            user_data[uid]['actual_minutes'] += (p.actual_workload_minutes or 0)
        elif p.status == 'CANCELLED':
            user_data[uid]['justified'] += 1
        else:
            user_data[uid]['pending'] += 1

        if p.is_adhoc:
            user_data[uid]['adhoc'] += 1

    # 4. Build Detail List
    details = []
    total_planned = 0
    total_executed = 0

    for uid, stats in user_data.items():
        comp_pct = (stats['executed'] / stats['planned'] * 100) if stats['planned'] > 0 else 0
        total_planned += stats['planned']
        total_executed += stats['executed']

        details.append(ComplianceUserStatsSchema(
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

    # 5. Global Stats
    global_pct = (total_executed / total_planned * 100) if total_planned > 0 else 0
    global_stats = ComplianceGlobalStatsSchema(
        total_users = len(user_data),
        global_compliance_percentage = round(global_pct, 2),
        total_planned_visits = total_planned,
        total_executed_visits = total_executed
    )

    return ComplianceReportResponseSchema(
        period_start = filters.start_date,
        period_end = filters.end_date,
        global_stats = global_stats,
        details = details
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
    # Simplified scan logic
    # In a real scenario, we would filter by expiration_date <= today + threshold
    _ = db.query(PointOfSale, ReplenishmentInventory).join(
        ReplenishmentInventory, PointOfSale.id == ReplenishmentInventory.attendance_id
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

    query = db.query(Attendance, TradePlanning, PointOfSale).join(
        TradePlanning, Attendance.trade_planning_id == TradePlanning.id
    ).join(
        PointOfSale, TradePlanning.point_of_sale_id == PointOfSale.id
    ).filter(
        Attendance.company_id == filters.company_id,
        Attendance.created_at.between(start_dt, end_dt)
    )

    if filters.user_id:
        query = query.filter(Attendance.user_id == filters.user_id)
    if filters.point_of_sale_id:
        query = query.filter(TradePlanning.point_of_sale_id == filters.point_of_sale_id)

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
