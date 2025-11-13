'''
    Business logic for Reports.
    Handles complex aggregations and calculations for dashboards.
'''
from typing import List, Dict, Any
from datetime import datetime, time
from collections import defaultdict
import requests

from sqlalchemy.orm import Session
from sqlalchemy import or_

from services.utils import handle_service_errors
from services.logger_config import custom_logger as logger
from services.environment import load_and_validate_env_vars

# Imports de Modelos
from models.trade import TradePlanning
from models.pos import PointOfSale, PointOfSaleInventory
from models.products import Product
from models.impulses import ImpulseSale, ImpulseSaleDetail

# Imports de Schemas
from schemas.reports import (
    ComplianceFilterSchema,
    ComplianceReportResponseSchema,
    ComplianceUserStatsSchema,
    ComplianceGlobalStatsSchema,
    InventoryAlertFilterSchema,
    InventoryAlertResponseSchema,
    InventoryAlertItemSchema,
    SalesReportFilterSchema,
    SalesReportResponseSchema,
    SalesDetailItemSchema
)

# --- CONFIGURACIÓN DE ENTORNO ---
ENV_VARS = load_and_validate_env_vars({
    'LOCALIZATION_SERVICE_URL': str
})

LOCALIZATION_SERVICE_URL = ENV_VARS['LOCALIZATION_SERVICE_URL']


# --- HELPERS PARA HTTP REQUESTS (Comunicación entre Microservicios) ---

def _fetch_attendances_from_localization(
    auth_token: str,
    attendance_ids: List[int]
) -> Dict[int, Dict[str, Any]]:
    '''
        Helper to fetch attendance details (User, POS) from LOCALIZATION microservice.
        Uses a Batch/Search pattern to avoid N+1 HTTP calls.
    '''
    if not LOCALIZATION_SERVICE_URL:
        logger.warning('LOCALIZATION_SERVICE_URL not set. Cannot fetch attendance details.')
        return {}

    if not attendance_ids:
        return {}

    url = f'{LOCALIZATION_SERVICE_URL}/v1/localization/attendances/search'
    
    # Preparamos los headers y body
    headers = {
        'Authorization': auth_token if auth_token.startswith('Bearer ') else f'Bearer {auth_token}',
        'Content-Type': 'application/json'
    }
    payload = {'attendance_ids': attendance_ids}

    try:
        # NOTA: Asumimos que LOCALIZATION tendrá este endpoint para búsqueda masiva
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Esperamos una lista de objetos Attendance
        attendances_list = response.json()
        
        # Convertimos a Diccionario para búsqueda rápida: { attendance_id: {data} }
        return {item['id']: item for item in attendances_list}

    except requests.RequestException as e:
        logger.error(f'Error fetching data from LOCALIZATION: {e}')
        # En caso de error, retornamos dict vacío para no romper todo el reporte,
        # aunque los campos saldrán vacíos.
        return {}


# --- HELPERS PARA COMPLIANCE (Refactorizado previamente) ---

def _update_record_stats(record: TradePlanning, stats: Dict[str, int]) -> None:
    ''' Helper for Compliance Report logic '''
    if record.is_adhoc:
        stats['total_adhoc'] += 1
        if record.status == 'COMPLETED':
            stats['total_executed'] += 1
    else:
        stats['total_planned'] += 1
        if record.status == 'COMPLETED':
            stats['total_executed'] += 1
        elif record.status == 'PENDING':
            stats['total_pending'] += 1
        elif record.status == 'NO_VISIT':
            stats['total_justified'] += 1

    if not record.is_adhoc:
        stats['planned_minutes'] += (record.planned_workload_minutes or 0)
    
    stats['actual_minutes'] += (record.actual_workload_minutes or 0)


def _calculate_user_kpis(uid: int, stats: Dict[str, int]) -> ComplianceUserStatsSchema:
    ''' Helper for Compliance Report logic '''
    planned = stats['total_planned']
    executed = stats['total_executed']
    
    compliance_pct = round((executed / planned) * 100, 2) if planned > 0 else 0.0
    workload_gap = stats['actual_minutes'] - stats['planned_minutes']

    return ComplianceUserStatsSchema(
        user_id = uid,
        total_planned = planned,
        total_executed = executed,
        total_pending = stats['total_pending'],
        total_adhoc = stats['total_adhoc'],
        total_justified = stats['total_justified'],
        compliance_percentage = compliance_pct,
        total_planned_minutes = stats['planned_minutes'],
        total_actual_minutes = stats['actual_minutes'],
        workload_gap_minutes = workload_gap
    )

# --- REPORT SERVICES ---

@handle_service_errors('REPORTS')
async def get_compliance_report_service(
    db: Session,
    filters: ComplianceFilterSchema
) -> ComplianceReportResponseSchema:
    '''
        Generates the Compliance Report (Planificación vs Realidad).
    '''
    message = f'Generating Compliance Report for Company: {filters.company_id}'
    logger.info(message)

    start_dt = datetime.combine(filters.start_date, time.min)
    end_dt = datetime.combine(filters.end_date, time.max)

    query = db.query(TradePlanning).filter(
        TradePlanning.company_id == filters.company_id,
        TradePlanning.created_at >= start_dt,
        TradePlanning.created_at <= end_dt
    )

    if filters.user_id:
        query = query.filter(TradePlanning.user_id == filters.user_id)

    records = query.all()

    user_stats_map = defaultdict(lambda: {
        'total_planned': 0, 'total_executed': 0, 'total_pending': 0,
        'total_adhoc': 0, 'total_justified': 0,
        'planned_minutes': 0, 'actual_minutes': 0
    })

    for record in records:
        _update_record_stats(record, user_stats_map[record.user_id])

    details_list: List[ComplianceUserStatsSchema] = []
    g_total_planned = 0
    g_total_executed = 0

    for uid, stats in user_stats_map.items():
        user_schema = _calculate_user_kpis(uid, stats)
        details_list.append(user_schema)
        g_total_planned += user_schema.total_planned
        g_total_executed += user_schema.total_executed

    global_compliance = round((g_total_executed / g_total_planned) * 100, 2) if g_total_planned > 0 else 0.0

    global_stats = ComplianceGlobalStatsSchema(
        total_users = len(details_list),
        global_compliance_percentage = global_compliance,
        total_planned_visits = g_total_planned,
        total_executed_visits = g_total_executed
    )

    return ComplianceReportResponseSchema(
        period_start = filters.start_date,
        period_end = filters.end_date,
        global_stats = global_stats,
        details = details_list
    )


@handle_service_errors('REPORTS')
async def get_inventory_alerts_service(
    db: Session,
    filters: InventoryAlertFilterSchema
) -> InventoryAlertResponseSchema:
    '''
        Generates the Inventory Alerts Report (Stockouts & Short Dates).
    '''
    message = f'Generating Inventory Alerts for Company: {filters.company_id}'
    logger.info(message)

    query = db.query(PointOfSaleInventory).join(
        PointOfSale, PointOfSaleInventory.point_of_sale_id == PointOfSale.id
    ).join(
        Product, PointOfSaleInventory.product_id == Product.id
    ).filter(
        PointOfSaleInventory.company_id == filters.company_id
    )

    if filters.point_of_sale_id:
        query = query.filter(PointOfSaleInventory.point_of_sale_id == filters.point_of_sale_id)

    condition_stockout = (PointOfSaleInventory.quantity <= 0)
    # pylint: disable=singleton-comparison
    condition_short_date = (PointOfSaleInventory.is_short_date.is_(True))

    if filters.alert_type == 'STOCKOUT':
        query = query.filter(condition_stockout)
    elif filters.alert_type == 'SHORT_DATE':
        query = query.filter(condition_short_date, PointOfSaleInventory.quantity > 0)
    else:
        query = query.filter(or_(condition_stockout, condition_short_date))

    records = query.order_by(PointOfSaleInventory.expiration_date.asc()).all()

    alert_items: List[InventoryAlertItemSchema] = []

    for record in records:
        if record.quantity <= 0:
            label, severity = 'STOCKOUT', 'RED'
        else:
            label, severity = 'SHORT_DATE', 'YELLOW'

        alert_items.append(InventoryAlertItemSchema(
            point_of_sale_name = record.point_of_sale.name,
            product_name = record.product.name,
            category_1_code = record.product.category_1_code,
            location = record.location,
            batch_number = record.batch_number,
            expiration_date = record.expiration_date.date(),
            quantity = record.quantity,
            alert_label = label,
            severity = severity
        ))

    return InventoryAlertResponseSchema(
        total_alerts = len(alert_items),
        items = alert_items
    )


@handle_service_errors('REPORTS')
async def get_sales_report_service(
    db: Session,
    filters: SalesReportFilterSchema,
    auth_token: str # Necesario para llamar a LOCALIZATION
) -> SalesReportResponseSchema:
    '''
        Generates the detailed Sales Report by fetching local sales data
        and enriching it with User/POS data from LOCALIZATION microservice.
    '''
    message = f'Generating Sales Report for Company: {filters.company_id}'
    logger.info(message)

    start_dt = datetime.combine(filters.start_date, time.min)
    end_dt = datetime.combine(filters.end_date, time.max)

    # 1. Query Local Sales (Header + Details + Products)
    # No unimos con PointOfSale local todavía, porque no tenemos el ID aquí.
    query = db.query(ImpulseSale, ImpulseSaleDetail, Product).join(
        ImpulseSaleDetail, ImpulseSale.id == ImpulseSaleDetail.impulse_sale_id
    ).join(
        Product, ImpulseSaleDetail.product_id == Product.id
    ).filter(
        ImpulseSaleDetail.product_id == Product.id, # Explicit join check
        Product.company_id == filters.company_id,   # Filter by product company as proxy
        ImpulseSale.created_at >= start_dt,
        ImpulseSale.created_at <= end_dt
    )
    
    if filters.product_id:
        query = query.filter(ImpulseSaleDetail.product_id == filters.product_id)

    raw_records = query.order_by(ImpulseSale.created_at.desc()).all()

    if not raw_records:
        # Retorno rápido si no hay ventas
        return SalesReportResponseSchema(
            period_start=filters.start_date, period_end=filters.end_date,
            total_units_sold=0, total_transactions=0, items=[]
        )

    # 2. Extract Attendance IDs to fetch context
    attendance_ids = list({row[0].attendance_id for row in raw_records})

    # 3. Call LOCALIZATION Service (Bulk Fetch)
    # Devuelve map: { attendance_id: { 'user_id': 1, 'point_of_sale_id': 5, ... } }
    attendance_map = _fetch_attendances_from_localization(auth_token, attendance_ids)

    # 4. Extract POS IDs needed from TRADE (if we want POS Names)
    pos_ids_needed = {
        att['point_of_sale_id'] 
        for att in attendance_map.values() 
        if 'point_of_sale_id' in att
    }
    
    # Fetch POS names from local DB
    pos_map = {}
    if pos_ids_needed:
        pos_records = db.query(PointOfSale).filter(PointOfSale.id.in_(pos_ids_needed)).all()
        pos_map = {pos.id: pos.name for pos in pos_records}

    # 5. Build Report Items
    items_list: List[SalesDetailItemSchema] = []
    total_units = 0
    unique_transactions = set()

    for header, detail, prod in raw_records:
        
        # Contexto desde Localization
        att_data = attendance_map.get(header.attendance_id, {})
        user_id = att_data.get('user_id', 0) # 0 or None if missing
        pos_id = att_data.get('point_of_sale_id', 0)
        
        # Filtros en Memoria (User / POS)
        # Como la data viene de otro servicio, filtramos aquí
        if filters.user_id and user_id != filters.user_id:
            continue
        if filters.point_of_sale_id and pos_id != filters.point_of_sale_id:
            continue

        pos_name = pos_map.get(pos_id, 'Unknown POS')

        qty = detail.quantity
        total_units += qty
        unique_transactions.add(header.id)

        items_list.append(SalesDetailItemSchema(
            sale_id = header.id,
            sale_date = header.created_at.date(),
            timestamp = header.created_at,
            user_id = user_id,
            point_of_sale_id = pos_id,
            point_of_sale_name = pos_name,
            product_id = prod.id,
            product_name = prod.name,
            product_sku = prod.sku,
            category_1 = prod.category_1_code,
            quantity = qty
        ))

    return SalesReportResponseSchema(
        period_start = filters.start_date,
        period_end = filters.end_date,
        total_units_sold = total_units,
        total_transactions = len(unique_transactions),
        items = items_list
    )
