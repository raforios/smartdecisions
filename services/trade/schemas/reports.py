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
        description = 'Optional: Filter by specific User ID.'
    )

    class Config: # pylint: disable=too-few-public-methods
        '''
            Allow arbitrary types if needed for query params
        '''
        arbitrary_types_allowed = True

class ComplianceUserStatsSchema(ReportBaseSchema):
    '''
        Row details: Compliance statistics per User.
    '''
    user_id: int = Field(..., description = 'User ID.')

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

class ComplianceGlobalStatsSchema(ReportBaseSchema):
    '''
        Header details: Aggregated statistics for the whole query.
    '''
    total_users: int = Field(..., description = 'Number of users in this report.')
    global_compliance_percentage: float = Field(..., description = 'Average compliance %.')
    total_planned_visits: int = Field(..., description = 'Sum of all planned visits.')
    total_executed_visits: int = Field(..., description = 'Sum of all executed visits.')

class ComplianceReportResponseSchema(ReportBaseSchema):
    '''
        Final Response: Contains the global summary and the per-user breakdown.
    '''
    period_start: date
    period_end: date
    global_stats: ComplianceGlobalStatsSchema
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
