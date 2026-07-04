'''
    Reports Schemas (Request/Response)
    Separated from transactional schemas to maintain Clean Architecture.
'''
from typing import List, Optional
from datetime import date, datetime
from fastapi import Query
from pydantic import BaseModel, Field

from services.utils import get_current_time_gmt

class ReportBaseSchema(BaseModel):
    '''
        Base schema for reports.
        Reports usually don't need from_attributes=True because 
        they are constructed from aggregations, not direct ORM mapping.
    '''

# --- 1. COMPLIANCE REPORT (CUMPLIMIENTO DE AGENDA) ---

class ComplianceFilterSchema(BaseModel):
    '''
        Input filters for the Compliance Report.
    '''
    company_id: int = Query(
        ...,
        description = 'Company ID to generate the report for.'
    )
    start_date: date = Query(
        ...,
        description = 'Start date of the period (YYYY-MM-DD).'
    )
    end_date: date = Query(
        ...,
        description = 'End date of the period (YYYY-MM-DD).'
    )
    user_id: Optional[int] = Query(
        None,
        description = 'Optional: Filter by specific User ID (operator from frontend).'
    )
    team_id: Optional[int] = Query(
        None,
        description = 'Optional: Filter by specific Team ID (from frontend).'
    )

    class Config: # pylint: disable=too-few-public-methods
        '''
            Allow arbitrary types if needed for query params
        '''
        arbitrary_types_allowed = True

class ComplianceUserStatsSchema(ReportBaseSchema):
    '''
        Row details: Compliance statistics per User.

        A user appears in this list only when at least one Attendance record
        exists for them in the period. Planned points without any Attendance
        cannot be attributed to a user and are reported at the team level.
    '''
    team_id: int = Field(..., description = 'Team the user belongs to.')
    user_id: int = Field(..., description = 'User ID (operator from frontend).')

    # Contadores de Visitas
    total_planned: int = Field(..., description = 'Total visits initially planned.')
    total_executed: int = Field(..., description = 'Total visits completed (Check-out).')
    total_pending: int = Field(..., description = 'Visits still pending.')
    total_adhoc: int = Field(..., description = 'Unplanned visits created on the fly.')
    total_justified: int = Field(..., description = 'Visits not performed with justification.')

    # KPIs de Efectividad
    compliance_percentage: float = Field(
        ...,
        description = 'Effectiveness % (Executed / Planned * 100).'
    )

    # Análisis de Carga Horaria
    total_planned_minutes: int = Field(..., description = 'Sum of planned workload.')
    total_actual_minutes: int = Field(..., description = 'Sum of actual workload.')
    workload_gap_minutes: int = Field(..., description = 'Difference (Actual - Planned).')

class ComplianceTeamStatsSchema(ReportBaseSchema):
    '''
        Row details: Compliance statistics per Team. Includes every planned
        point belonging to the team, regardless of whether it was executed.
    '''
    team_id: int = Field(..., description = 'Team ID (from frontend).')
    total_users: int = Field(..., description = 'Distinct users that executed visits in the team.')

    total_planned: int = Field(..., description = 'Total visits planned for the team.')
    total_executed: int = Field(..., description = 'Total visits completed.')
    total_pending: int = Field(..., description = 'Visits still pending.')
    total_adhoc: int = Field(..., description = 'Unplanned visits created on the fly.')
    total_justified: int = Field(..., description = 'Visits not performed with justification.')

    # Planned points with no Attendance at all → cannot be attributed to any
    # user. Useful to surface orphan/uncovered planning.
    unassigned_planned: int = Field(
        ...,
        description = 'Planned points without any Attendance (no user attribution).'
    )

    compliance_percentage: float = Field(
        ...,
        description = 'Effectiveness % (Executed / Planned * 100).'
    )

    total_planned_minutes: int = Field(..., description = 'Sum of planned workload.')
    total_actual_minutes: int = Field(..., description = 'Sum of actual workload.')
    workload_gap_minutes: int = Field(..., description = 'Difference (Actual - Planned).')

class ComplianceGlobalStatsSchema(ReportBaseSchema):
    '''
        Header details: Aggregated statistics for the whole query.
    '''
    total_teams: int = Field(..., description = 'Number of teams in this report.')
    total_users: int = Field(..., description = 'Number of users in this report.')
    global_compliance_percentage: float = Field(..., description = 'Average compliance %.')
    total_planned_visits: int = Field(..., description = 'Sum of all planned visits.')
    total_executed_visits: int = Field(..., description = 'Sum of all executed visits.')

class ComplianceReportResponseSchema(ReportBaseSchema):
    '''
        Final Response: Contains the global summary, team breakdown, and
        per-user breakdown.
    '''
    period_start: date
    period_end: date
    global_stats: ComplianceGlobalStatsSchema
    team_details: List[ComplianceTeamStatsSchema]
    details: List[ComplianceUserStatsSchema]

# --- 2. INVENTORY ALERTS REPORT ---

class InventoryAlertFilterSchema(BaseModel):
    '''
        Filters for the Inventory Alerts Report.
    '''
    company_id: int = Query(
        ...,
        description = 'Company ID to scan for alerts.'
    )
    point_of_sale_id: Optional[int] = Query(
        None,
        description = 'Optional: Filter by specific Point of Sale.'
    )
    alert_type: Optional[str] = Query(
        'ALL', 
        pattern = '^(ALL|STOCKOUT|SHORT_DATE)$',
        description = 'Type of alert to fetch: ALL, STOCKOUT, or SHORT_DATE.'
    )

class InventoryAlertItemSchema(ReportBaseSchema):
    '''
        Row details: A specific product batch with an alert.
    '''
    point_of_sale_name: str = Field(..., description = 'Name of the POS.')
    product_name: str = Field(..., description = 'Name of the Product.')
    # Como el SKU completo es construido, por ahora devolvemos los códigos o el ID.
    # Si tienes un campo 'sku' persistido en Product, úsalo aquí.
    category_1_code: str = Field(..., description = 'Main category code.')

    location: str = Field(..., description = 'Storage location (Sala/Almacen).')
    batch_number: str = Field(..., description = 'Batch number.')
    expiration_date: date = Field(..., description = 'Expiration date.')
    quantity: int = Field(..., description = 'Current stock quantity.')

    alert_label: str = Field(..., description = 'Alert type: "STOCKOUT" or "SHORT_DATE".')
    severity: str = Field(..., description = 'Visual hint: "RED" (Critical) or "YELLOW" (Warning).')

class InventoryAlertResponseSchema(ReportBaseSchema):
    '''
        Response wrapper for the list of alerts.
    '''
    generated_at: datetime = Field(default_factory = get_current_time_gmt)
    total_alerts: int
    items: List[InventoryAlertItemSchema]

# --- 3. SALES REPORT (DASHBOARD/PIVOT) ---

class SalesReportFilterSchema(BaseModel):
    '''
        Filters for the Sales Report.
    '''
    company_id: int = Query(..., description = 'Company ID.')
    start_date: date = Query(..., description = 'Start date (YYYY-MM-DD).')
    end_date: date = Query(..., description = 'End date (YYYY-MM-DD).')

    point_of_sale_id: Optional[int] = Query(None, description = 'Filter by POS.')
    user_id: Optional[int] = Query(None, description = 'Filter by User.')
    product_id: Optional[int] = Query(None, description = 'Filter by Product.')

    class Config: # pylint: disable=too-few-public-methods
        ''' 
            Pydantic config
        '''
        arbitrary_types_allowed = True

class SalesDetailItemSchema(ReportBaseSchema):
    '''
        Row details: Represents a single line of sale (Product + Qty + Context).
        Designed to be fed into a Frontend Pivot Table or Chart.
    '''
    sale_id: int
    sale_date: date = Field(..., description = 'Date of the sale.')
    timestamp: datetime = Field(..., description = 'Exact timestamp.')

    user_id: int
    point_of_sale_id: int
    point_of_sale_name: str

    product_id: int
    product_name: str
    product_sku: str
    category_1: str = Field(..., description = 'Main category for grouping.')

    quantity: int = Field(..., description = 'Quantity sold.')

class SalesReportResponseSchema(ReportBaseSchema):
    '''
        Response wrapper for the Sales Report.
    '''
    generated_at: datetime = Field(default_factory = get_current_time_gmt)
    period_start: date
    period_end: date

    total_units_sold: int = Field(..., description = 'Grand total of units in this period.')
    total_transactions: int = Field(..., description = 'Number of sale headers.')

    items: List[SalesDetailItemSchema]

# --- 4. MERCHANDISING REPORT ---
class MerchandisingFilterSchema(BaseModel):
    '''
        Request MerchandisingFilterSchema.
    '''
    company_id: int = Query(...)
    start_date: date = Query(...)
    end_date: date = Query(...)

class MerchandisingItemSchema(ReportBaseSchema):
    '''
        Response MerchandisingItemSchema.
    '''
    activity_type: str = Field(...,
                        description='BANDEO, COMPETITION, PROMO_POINT')
    date: datetime
    user_id: int
    details: str
    photo_url: Optional[str]

class MerchandisingReportResponseSchema(ReportBaseSchema):
    '''
        Response MerchandisingReportResponseSchema.
    '''
    items: List[MerchandisingItemSchema]
    total_activities: int

# --- 5. PHOTOGRAPHIC REPORT ---
class PhotoFilterSchema(BaseModel):
    '''
        Filters for the Photographic Gallery Report.
    '''
    company_id: int = Query(
        ...,
        description = 'Company ID to filter photos.'
    )
    start_date: date = Query(
        ...,
        description = 'Start date (YYYY-MM-DD).'
    )
    end_date: date = Query(
        ...,
        description = 'End date (YYYY-MM-DD).'
    )
    user_id: Optional[int] = Query(
        None,
        description = 'Optional: Filter by User ID.'
    )
    point_of_sale_id: Optional[int] = Query(
        None,
        description = 'Optional: Filter by Point of Sale ID.'
    )
    category: Optional[str] = Query(
        None,
        pattern = '^(IMPULSE_SALE|REPLENISHMENT|BANDEO|COMPETITION|PROMO_POINT)$',
        description = 'Optional: Filter by specific category.'
    )

    class Config: # pylint: disable=too-few-public-methods
        ''' Pydantic config '''
        arbitrary_types_allowed = True

class PhotoItemSchema(ReportBaseSchema):
    '''
        Request PhotoItemSchema.
    '''
    date: datetime
    category: str # SALE, REPLENISHMENT, BANDEO, etc.
    user_id: int
    photo_url: str
    comments: Optional[str]

class PhotographicReportResponseSchema(ReportBaseSchema):
    '''
        Response PhotographicReportResponseSchema.
    '''
    items: List[PhotoItemSchema]
    total_photos: int

# --- 6. ATTENDANCE & GEOFENCING REPORT ---

class AttendanceReportFilterSchema(BaseModel):
    '''
        Input filters for the Attendance & Geofencing Report.
    '''
    company_id: int = Query(..., description = 'Company ID.')
    start_date: date = Query(..., description = 'Start date (YYYY-MM-DD).')
    end_date: date = Query(..., description = 'End date (YYYY-MM-DD).')
    user_id: Optional[int] = Query(None, description = 'Filter by User.')
    point_of_sale_id: Optional[int] = Query(None, description = 'Filter by POS.')

    class Config: # pylint: disable=too-few-public-methods
        ''' Pydantic config '''
        arbitrary_types_allowed = True

class AttendanceReportItemSchema(ReportBaseSchema):
    '''
        Row details: Represents a single visit with execution data.
    '''
    attendance_id: int
    user_id: int
    point_of_sale_id: int
    point_of_sale_name: str
    point_of_sale_code: str

    check_in_time: Optional[datetime]
    check_in_distance_error: Optional[float] = Field(...,
                            description = 'Distance from POS at Check-In (meters).')

    check_out_time: Optional[datetime]
    check_out_distance_error: Optional[float] = Field(...,
                            description = 'Distance from POS at Check-Out (meters).')

    duration_minutes: Optional[int] = Field(..., description = 'Total time spent at POS.')
    status: str = Field(..., description = 'Status of the visit (COMPLETED, IN_PROGRESS).')

class AttendanceReportResponseSchema(ReportBaseSchema):
    '''
        Response wrapper for the Attendance Report.
    '''
    generated_at: datetime = Field(default_factory = get_current_time_gmt)
    period_start: date
    period_end: date
    total_visits: int
    average_duration_minutes: float
    items: List[AttendanceReportItemSchema]


# ============================================================================
# iter6 (Binaria, 2026-06-22): Monitor de Trade (req 7.4)
# ----------------------------------------------------------------------------
# Three aggregated endpoints power the executive panels demanded by the
# requirement document. Each one consolidates the metrics that today the
# frontend would have to assemble from 4-5 round-trips.
# ============================================================================

class PanelFilterSchema(BaseModel):
    '''
        Common filter shape for the Impulses and Replenishments panels.
        Mirrors req 7.4.1 / 7.4.3: company is mandatory, the rest are
        optional; missing = "all values".
    '''
    company_id: int = Query(..., description = 'Mandatory company filter.')
    client_company_id: Optional[int] = Query(None)
    date_from: date = Query(..., description = 'Inclusive lower date.')
    date_to: date = Query(..., description = 'Inclusive upper date.')
    country_id: Optional[int] = Query(None)
    city_id: Optional[int] = Query(None)
    pos_type_id: Optional[int] = Query(None)
    channel_id: Optional[int] = Query(None)
    pos_id: Optional[int] = Query(None)
    route_id: Optional[int] = Query(None)
    team_id: Optional[int] = Query(None)
    user_id: Optional[int] = Query(None)
    product_id: Optional[int] = Query(None)

    class Config:  # pylint: disable=too-few-public-methods
        '''Arbitrary types allowed for FastAPI query parsing.'''
        arbitrary_types_allowed = True


class PanelGeneralIndicatorsSchema(BaseModel):
    '''
        Cuadro "Indicadores generales" (7.4.1 / 7.4.3).
    '''
    pdv_count: int = 0
    activity_count: int = 0
    activities_per_pdv: float = 0.0
    products_count: int = 0
    products_per_activity: float = 0.0
    avg_time_per_pdv_minutes: float = 0.0


class PanelRouteIndicatorsSchema(BaseModel):
    '''
        Cuadro "Indicadores de ruta" (7.4.1 / 7.4.3). Returned only when
        at least one route filter is applied.
    '''
    pdv_per_route: float = 0.0
    avg_time_per_route_minutes: float = 0.0
    avg_time_per_pdv_minutes: float = 0.0
    avg_time_between_pdv_minutes: float = 0.0


class PanelByCityRow(BaseModel):
    '''
        One row of a "X por ciudad" pie chart.
    '''
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    count: int
    percentage: float


class PanelByDayRow(BaseModel):
    '''
        One row of a "X por dia" line chart.
    '''
    day: date
    count: int


class PanelSalesSummaryRow(BaseModel):
    '''
        Sales aggregation per SKU for the panel "Datos de ventas" cell.
    '''
    product_id: int
    sku: Optional[str] = None
    name: Optional[str] = None
    total_quantity: int = 0
    unit_of_measure: Optional[str] = None


class PanelInventorySnapshotRow(BaseModel):
    '''
        Inventory snapshot per SKU. For Impulses uses Q_initial - Q_sold;
        for Replenishments splits into room/warehouse with breakage flag.
    '''
    product_id: int
    sku: Optional[str] = None
    name: Optional[str] = None
    quantity: int = 0
    quantity_in_room: Optional[int] = None
    quantity_in_warehouse: Optional[int] = None
    quantity_minimum: Optional[int] = None
    stockout: bool = False
    unit_of_measure: Optional[str] = None


class PanelExpirationRow(BaseModel):
    '''
        One row of the Replenishments panel "Datos de vencimientos" table.
    '''
    product_id: int
    sku: Optional[str] = None
    name: Optional[str] = None
    location: Optional[str] = None
    batch_number: Optional[str] = None
    expiration_date: Optional[date] = None
    days_remaining: Optional[int] = None
    is_short_dated: bool = False


class PanelSheetRow(BaseModel):
    '''
        Flat row of the "Planilla" tab, ready to export to CSV/Excel.
    '''
    company_id: int
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    country_id: Optional[int] = None
    city_id: Optional[int] = None
    route_id: Optional[int] = None
    route_name: Optional[str] = None
    pos_id: Optional[int] = None
    pos_name: Optional[str] = None
    product_id: Optional[int] = None
    sku: Optional[str] = None
    product_name: Optional[str] = None
    quantity_initial: Optional[int] = None
    quantity_sold: Optional[int] = None
    quantity_final: Optional[int] = None
    user_id: Optional[int] = None


class ImpulsesPanelResponseSchema(BaseModel):
    '''
        Response for GET /v1/reports/panel/impulses (req 7.4.1).
    '''
    generated_at: datetime = Field(default_factory = get_current_time_gmt)
    filters_applied: PanelFilterSchema
    general_indicators: PanelGeneralIndicatorsSchema
    route_indicators: Optional[PanelRouteIndicatorsSchema] = None
    pdv_by_city: List[PanelByCityRow] = []
    activities_by_city: List[PanelByCityRow] = []
    activities_by_day: List[PanelByDayRow] = []
    sales_summary: List[PanelSalesSummaryRow] = []
    inventory_snapshot: List[PanelInventorySnapshotRow] = []
    sheet: List[PanelSheetRow] = []


class ReplenishmentsPanelResponseSchema(BaseModel):
    '''
        Response for GET /v1/reports/panel/replenishments (req 7.4.3).
    '''
    generated_at: datetime = Field(default_factory = get_current_time_gmt)
    filters_applied: PanelFilterSchema
    general_indicators: PanelGeneralIndicatorsSchema
    route_indicators: Optional[PanelRouteIndicatorsSchema] = None
    pdv_by_city: List[PanelByCityRow] = []
    activities_by_city: List[PanelByCityRow] = []
    activities_by_day: List[PanelByDayRow] = []
    inventory_snapshot: List[PanelInventorySnapshotRow] = []
    expirations: List[PanelExpirationRow] = []
    sheet: List[PanelSheetRow] = []


# ----------------------------------------------------------------------------
# Route tracking (req 7.4.4)
# ----------------------------------------------------------------------------

# RouteTrackingActivity = 'IMPULSO'  # default; literal validation done below

class RouteTrackingFilterSchema(BaseModel):
    '''
        Filters for GET /v1/reports/route-tracking (req 7.4.4).
    '''
    company_id: int = Query(...)
    activity: str = Query(
        'IMPULSO',
        description = 'Object: IMPULSO or REPOSICION.'
    )
    route_id: Optional[int] = Query(
        None,
        description = (
            'Route to render on the map. If omitted, returns every route '
            'matching the other filters.'
        )
    )
    target_date: date = Query(..., description = 'Day to render.')
    team_id: Optional[int] = Query(None)
    user_id: Optional[int] = Query(None)

    class Config:  # pylint: disable=too-few-public-methods
        '''Arbitrary types allowed for FastAPI query parsing.'''
        arbitrary_types_allowed = True


class RouteTrackingPosInventoryRow(BaseModel):
    '''
        Per-product line shown on the POS popup of the map.
    '''
    product_id: int
    sku: Optional[str] = None
    name: Optional[str] = None
    quantity_initial: Optional[int] = None
    quantity_sold: Optional[int] = None
    quantity_remaining: Optional[int] = None
    quantity_in_room: Optional[int] = None
    quantity_in_warehouse: Optional[int] = None
    quantity_total: Optional[int] = None
    quantity_minimum: Optional[int] = None
    unit_of_measure: Optional[str] = None
    stockout: bool = False


class RouteTrackingPointSchema(BaseModel):
    '''
        One PDV on the route track. Status:
          PENDING -> red pin (no check-in nor check-out)
          OPEN    -> yellow pin (check-in only)
          CLOSED  -> green pin (check-in + check-out)
    '''
    planned_point_id: int
    sequence: int
    pos_id: int
    pos_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    planned_check_in_time: Optional[str] = None
    status: str = 'PENDING'
    check_in_time: Optional[datetime] = None
    check_out_time: Optional[datetime] = None
    inventory: List[RouteTrackingPosInventoryRow] = []


class RouteTrackingRouteSchema(BaseModel):
    '''
        One route to render on the map.
    '''
    route_id: int
    route_name: Optional[str] = None
    route_code: Optional[str] = None
    color: Optional[str] = None
    activity: str
    points: List[RouteTrackingPointSchema] = []


class RouteTrackingResponseSchema(BaseModel):
    '''
        Response for GET /v1/reports/route-tracking (req 7.4.4).
    '''
    generated_at: datetime = Field(default_factory = get_current_time_gmt)
    filters_applied: RouteTrackingFilterSchema
    routes: List[RouteTrackingRouteSchema] = []
