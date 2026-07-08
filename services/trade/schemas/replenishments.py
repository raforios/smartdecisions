'''
    Replenishments Schemas (Request/Response).

    Iter 5 (Binaria, 2026-06-20) additions are marked with `# iter5:` comments
    so the diff against production is easy to audit. The same iteration also
    introduces query/list schemas that previously did not exist for
    Replenishment reports, inventory and reception.
'''
from typing import List, Literal, Optional
from datetime import datetime, time
from decimal import Decimal
from pydantic import Field
from schemas.common import BaseSchema, PhotoResponseSchema

# --- B.2. REPLENISHMENT ACTIVITIES SCHEMAS ---

# --- Schemas for Replenishment Report ---

class ReplenishmentReportDetailCreateSchema(BaseSchema):
    '''
        Per-product line of a Replenishment Report (Binaria, 2026-07-07):
        marks whether the product was replaced, with an optional replaced
        quantity and a per-product comment.
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) of the product.'
    )
    replaced: bool = Field(
        ...,
        description = 'Whether this product was replaced during the visit (repuesto sí/no).'
    )
    quantity: Optional[int] = Field(
        None, ge = 0,
        description = 'Optional quantity replaced for this product.'
    )
    comments: Optional[str] = Field(
        None,
        description = 'Optional comment for this specific product.'
    )

class ReplenishmentReportCreateSchema(BaseSchema):
    '''
        Schema for creating a Replenishment Report (Success Photos).
        The attendance_id will be passed in the URL path.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company for this transaction.'
    )
    # iter5: cliente (marca / producto) cuyo reporte se está registrando.
    client_company_id: Optional[int] = Field(
        None,
        description = 'ID of the client company (brand / product owner).'
    )
    pos_id: int = Field(
        ...,
        description = 'ID of the POS (sent by frontend) to validate assortment and attendance.'
    )
    comments: Optional[str] = Field(
        None,
        description = 'Optional comments from the user.'
    )
    # iter5: marcador de revisión. Default False (pendiente).
    reviewed: bool = Field(
        False,
        description = 'Marker for review / approval workflow. Defaults to False.'
    )
    # Binaria, 2026-07-07: per-product replaced yes/no detail. Optional so
    # existing header-only callers keep working.
    details: List[ReplenishmentReportDetailCreateSchema] = Field(
        default_factory = list,
        description = 'Per-product detail marking whether each product was replaced.'
    )

class ReplenishmentReportDetailResponseSchema(BaseSchema):
    '''
        Response schema for a single Replenishment Report product line.
    '''
    id: int
    product_id: int
    replaced: bool
    quantity: Optional[int] = None
    comments: Optional[str] = None

class ReplenishmentReportResponseSchema(BaseSchema):
    '''
        Response schema for a created Replenishment Report.
    '''
    id: int
    company_id: Optional[int] = None
    client_company_id: Optional[int] = None  # iter5
    attendance_id: int
    comments: Optional[str]
    reviewed: bool = False  # iter5
    details: List[ReplenishmentReportDetailResponseSchema] = []  # Binaria 2026-07-07
    photos: List[PhotoResponseSchema] = []
    created_at: Optional[datetime]

# iter5: query + list schemas for the new GET endpoint.
class ReplenishmentReportQuerySchema(BaseSchema):
    '''
        Filters for GET /v1/replenishment/reports. Mirrors the pattern of
        GET /v1/impulses/sales (filtering, optional reviewed flag, pagination).
    '''
    company_id: Optional[int] = Field(None, description = 'Operator company filter.')
    client_company_id: Optional[int] = Field(None, description = 'Brand / client filter.')
    pos_id: Optional[int] = Field(None, description = 'POS filter (via the visit attendance).')
    user_id: Optional[int] = Field(
        None, description = 'Operator filter (via the visit attendance).'
    )
    attendance_id: Optional[int] = Field(None, description = 'Visit filter.')
    reviewed: Optional[bool] = Field(None, description = 'Only reviewed (True) or pending (False).')
    date_from: Optional[datetime] = Field(None, description = 'created_at >= this datetime.')
    date_to: Optional[datetime] = Field(None, description = 'created_at <= this datetime.')
    limit: int = Field(50, ge = 1, le = 500)
    offset: int = Field(0, ge = 0)

class ReplenishmentReportListResponseSchema(BaseSchema):
    '''
        Wrapper for the report listing endpoint. The plural key is `items`
        per project convention (mirrors impulses, planning, POS, etc.).
    '''
    items: List[ReplenishmentReportResponseSchema]
    total: int

# iter5 (Binaria, 2026-06-20): Replenishment Inventory schemas removed.
# Inventory is now a single physical concept shared with Impulses. To
# register inventory during a Replenishment visit, use the existing
# Impulses endpoints, which now carry batch + expiration + sala/almacén:
#   POST /v1/impulses/visit/{attendance_id}/inventory-start
#   POST /v1/impulses/visit/{attendance_id}/inventory-end
#   GET  /v1/impulses/visit/{attendance_id}/inventory-start
#   GET  /v1/impulses/visit/{attendance_id}/inventory-end
# See schemas.impulses.ImpulseInventoryItemSchema for the payload shape.

# --- Schemas for Replenishment Reception ---

class ReplenishmentReceptionItemSchema(BaseSchema):
    '''
        Base schema for a single item received from a supplier.

        iter5: batch_number + expiration_date added so the operator can
        register expirations of every incoming batch.
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) received.'
    )
    quantity_received: int = Field(
        ...,
        ge = 0,
        description = 'Quantity received for this SKU.'
    )
    batch_number: Optional[str] = Field(  # iter5
        None,
        max_length = 50,
        description = 'Batch / lot number of the received product.'
    )
    expiration_date: Optional[str] = Field(  # iter5
        None,
        description = 'Expiration date of the received batch (YYYY-MM-DD).'
    )
    comments: Optional[str] = Field(
        None,
        description = 'Optional comments for this specific item.'
    )

class ReplenishmentReceptionCreateSchema(BaseSchema):
    '''
        Schema for creating a list of received items (Supplier Reception).
        Includes pos_id for Assortment Validation.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company (needed for SKU lookup).'
    )
    client_company_id: Optional[int] = Field(  # iter5
        None,
        description = 'ID of the client company (brand / product owner).'
    )
    pos_id: int = Field(
        ...,
        description = 'ID of the POS (sent by frontend) to validate assortment.'
    )
    items: List[ReplenishmentReceptionItemSchema] = Field(
        ...,
        min_length = 1,
        description = 'List of SKUs and quantities received.'
    )

class ReplenishmentReceptionResponseItemSchema(BaseSchema):
    '''
        Response schema for a single created reception item.
    '''
    id: int
    attendance_id: int
    product_id: int
    client_company_id: Optional[int] = None  # iter5
    quantity_received: int
    batch_number: Optional[str] = None  # iter5
    expiration_date: Optional[datetime] = None  # iter5
    comments: Optional[str]
    created_at: Optional[datetime]

class ReplenishmentReceptionListResponseSchema(BaseSchema):
    '''
        Response schema for a bulk creation OR a GET listing of reception items.
    '''
    items: List[ReplenishmentReceptionResponseItemSchema]
    total: int

# iter5: query schema for the new GET reception-per-visit endpoint.
class ReplenishmentReceptionQuerySchema(BaseSchema):
    '''
        Filters for GET /v1/replenishment/visit/{attendance_id}/reception.
    '''
    client_company_id: Optional[int] = Field(None)
    product_id: Optional[int] = Field(None)
    batch_number: Optional[str] = Field(None, max_length = 50)
    limit: int = Field(200, ge = 1, le = 1000)
    offset: int = Field(0, ge = 0)

# --- Schemas for Replenishment Inventory (Binaria, 2026-07-08, line-free) ---

class ReplenishmentInventoryItemSchema(BaseSchema):
    '''
        A single line-free inventory line: the same product may appear on
        several lines with different quantity / batch / expiration / location.
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) being counted.'
    )
    quantity: int = Field(
        ..., ge = 0,
        description = 'Quantity counted for this line.'
    )
    batch_number: Optional[str] = Field(
        None, max_length = 50,
        description = 'Batch / lot number of this line.'
    )
    expiration_date: Optional[str] = Field(
        None,
        description = 'Expiration date of this line (YYYY-MM-DD).'
    )
    location: Literal['SALA', 'ALMACEN'] = Field(
        ...,
        description = 'Physical location of this line: SALA or ALMACEN.'
    )
    observations: Optional[str] = Field(
        None,
        description = 'Optional notes for this line.'
    )

class ReplenishmentInventoryCreateSchema(BaseSchema):
    '''
        Schema for registering a replenishment inventory (one count per visit,
        many lines). pos_id is used for assortment validation.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company (needed for SKU lookup).'
    )
    client_company_id: Optional[int] = Field(
        None,
        description = 'ID of the client company (brand / product owner).'
    )
    pos_id: int = Field(
        ...,
        description = 'ID of the POS (sent by frontend) to validate assortment.'
    )
    items: List[ReplenishmentInventoryItemSchema] = Field(
        ...,
        min_length = 1,
        description = 'Inventory lines (line-free: repeat a product for other batches).'
    )

class ReplenishmentInventoryResponseItemSchema(BaseSchema):
    '''
        Response schema for a single replenishment inventory line.
    '''
    id: int
    attendance_id: int
    product_id: int
    client_company_id: Optional[int] = None
    quantity: int
    batch_number: Optional[str] = None
    expiration_date: Optional[datetime] = None
    location: str
    observations: Optional[str] = None
    created_at: Optional[datetime]

class ReplenishmentInventoryListResponseSchema(BaseSchema):
    '''
        Wrapper for replenishment inventory listings (bulk create, latest and
        the paginated list share this shape).
    '''
    items: List[ReplenishmentInventoryResponseItemSchema]
    total: int

class ReplenishmentInventoryQuerySchema(BaseSchema):
    '''
        Filters for GET /v1/replenishment/inventory. pos_id / user_id are
        resolved through the visit attendance.
    '''
    company_id: Optional[int] = Field(None, description = 'Operator company filter.')
    client_company_id: Optional[int] = Field(None, description = 'Brand / client filter.')
    pos_id: Optional[int] = Field(
        None, description = 'POS filter (via the visit attendance).'
    )
    user_id: Optional[int] = Field(
        None, description = 'Operator filter (via the visit attendance).'
    )
    date_from: Optional[datetime] = Field(None, description = 'created_at >= this datetime.')
    date_to: Optional[datetime] = Field(None, description = 'created_at <= this datetime.')
    limit: int = Field(100, ge = 1, le = 1000)
    offset: int = Field(0, ge = 0)

# --- B.3. COMPLEMENTARY ACTIVITIES SCHEMAS ---

# --- Schemas for Bandeo Report (iter6, Binaria 2026-06-22) ---
#
# Two-stage flow per req 7.3.4.1:
#   1) RECEIVE  -> POST .../bandeo/receive
#                  operator confirms qty received against the plan
#   2) RETURN   -> PATCH .../bandeo/{id}/return
#                  operator splits received qty into used + returned,
#                  with observations mandatory when overriding the
#                  calculated `quantity_returned`.

BandeoStatus = Literal['PENDING', 'RECEIVED', 'RETURNED']


class ComplementaryBandeoReceiveDetailSchema(BaseSchema):
    '''
        Item line registered when the operator confirms the products
        received for the bandeo (Recibir step).
    '''
    product_sku: str = Field(
        ...,
        description = 'Internal SKU code (XXX.YYY.ZZZ.WWW.SEC) of the bandeo product.'
    )
    quantity_planned: int = Field(
        ..., ge = 0,
        description = 'Q plan: qty of this SKU prescribed by the planned bandeo.'
    )
    quantity_received: int = Field(
        ..., ge = 0,
        description = 'Q recibida: qty actually delivered to the operator.'
    )
    unit_of_measure: Optional[str] = Field(
        None, max_length = 20,
        description = 'UM tomada de la planificacion del bandeo.'
    )


class ComplementaryBandeoReceiveSchema(BaseSchema):
    '''
        Schema for the Receive step. Creates a bandeo header bound to a
        planned promotion, with status=RECEIVED and one detail row per SKU
        of the bandeo.
    '''
    company_id: int = Field(
        ...,
        description = 'Executor company (needed for SKU lookup).'
    )
    client_company_id: Optional[int] = Field(
        None,
        description = 'Client company (brand / product owner).'
    )
    pos_id: int = Field(
        ...,
        description = 'POS where the bandeo is being assembled.'
    )
    promotion_id: int = Field(
        ...,
        description = 'Planned bandeo (TradePromotion.id) being executed.'
    )
    comments: Optional[str] = Field(
        None,
        description = 'Optional comments at the header level.'
    )
    details: List[ComplementaryBandeoReceiveDetailSchema] = Field(
        ...,
        min_length = 1,
        description = 'One row per SKU received for this bandeo.'
    )


class ComplementaryBandeoReturnDetailSchema(BaseSchema):
    '''
        Item line registered on the Devolver step. quantity_returned
        defaults to (quantity_received - quantity_used) and is editable;
        if the operator overrides it, observations is required.
    '''
    id: int = Field(
        ...,
        description = 'Detail row id returned by the Receive step.'
    )
    quantity_used: int = Field(
        ..., ge = 0,
        description = 'Q utilizada (must be <= quantity_received).'
    )
    quantity_returned: int = Field(
        ..., ge = 0,
        description = 'Q devuelta (must be <= quantity_received).'
    )
    observations: Optional[str] = Field(
        None,
        description = (
            'Observation. Mandatory when quantity_returned differs from the '
            'default (quantity_received - quantity_used).'
        )
    )


class ComplementaryBandeoReturnSchema(BaseSchema):
    '''
        Schema for the Devolver step. Transitions the header to
        status=RETURNED and persists used/returned per product line.
    '''
    details: List[ComplementaryBandeoReturnDetailSchema] = Field(
        ...,
        min_length = 1,
        description = 'One row per detail to finalize the bandeo.'
    )


class ComplementaryBandeoDetailResponseSchema(BaseSchema):
    '''
        Response schema for a single bandeo detail row.
    '''
    id: int
    bandeo_header_id: int
    product_id: int
    quantity_planned: int
    quantity_received: int
    quantity_used: Optional[int] = None
    quantity_returned: Optional[int] = None
    unit_of_measure: Optional[str] = None
    observations: Optional[str] = None


class ComplementaryBandeoResponseSchema(BaseSchema):
    '''
        Response schema for a bandeo header with its details.
    '''
    id: int
    company_id: Optional[int] = None
    client_company_id: Optional[int] = None
    attendance_id: int
    promotion_id: Optional[int] = None
    status: BandeoStatus
    received_at: Optional[datetime] = None
    returned_at: Optional[datetime] = None
    comments: Optional[str] = None
    created_at: Optional[datetime] = None
    photos: List[PhotoResponseSchema] = []
    details: List[ComplementaryBandeoDetailResponseSchema] = []


class ComplementaryBandeoListResponseSchema(BaseSchema):
    '''
        Wrapper for the per-visit bandeo listing.
    '''
    items: List[ComplementaryBandeoResponseSchema]
    total: int

# --- Schemas for Promotional Point Report (iter6, req 7.3.4.2) ---

class ComplementaryPromoPointCreateSchema(BaseSchema):
    '''
        Schema for creating a Promotional Point Report.

        iter6 (Binaria, 2026-06-22): adds opening_time / closing_time /
        description per req 7.3.4.2. opening_time, closing_time and
        description are mandatory; comments stays optional.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company for this transaction.'
    )
    client_company_id: Optional[int] = Field(
        None,
        description = 'ID of the client company (brand / product owner).'
    )
    pos_id: int = Field(
        ...,
        description = 'ID of the POS (sent by frontend) to validate assortment and attendance.'
    )
    opening_time: time = Field(
        ...,
        description = 'Hora de apertura del punto promocional (HH:MM[:SS]).'
    )
    closing_time: time = Field(
        ...,
        description = 'Hora de cierre del punto promocional (HH:MM[:SS]).'
    )
    description: str = Field(
        ..., min_length = 1,
        description = (
            'Descripcion del punto promocional, materiales utilizados y '
            'cualquier observacion adicional.'
        )
    )
    comments: Optional[str] = Field(
        None,
        description = 'Optional extra notes.'
    )

class ComplementaryPromoPointResponseSchema(BaseSchema):
    '''
        Response schema for a created Promotional Point Report.
    '''
    id: int
    attendance_id: int
    company_id: Optional[int] = None
    client_company_id: Optional[int] = None
    opening_time: Optional[time] = None
    closing_time: Optional[time] = None
    description: Optional[str] = None
    comments: Optional[str] = None
    photos: List[PhotoResponseSchema] = []
    created_at: Optional[datetime] = None

# --- Schemas for Competition Report ---

class ComplementaryCompetitionCreateSchema(BaseSchema):
    '''
        Schema for creating a general Competition Report.
        This is not tied to a specific attendance_id.
    '''
    company_id: int = Field(
        ...,
        description = 'ID of the company this report belongs to.'
    )
    user_id: int = Field(
        ...,
        description = 'ID of the user creating the report (from frontend session).'
    )
    # Binaria, 2026-07-07: brand / client the competition report belongs to,
    # so the listing can be filtered by client_company_id.
    client_company_id: Optional[int] = Field(
        None,
        description = 'ID of the client company (brand / product owner).'
    )
    pos_id: Optional[int] = Field(
        None,
        description = 'Optional: ID of the POS where the activity was observed.'
    )
    competitor_name: str = Field(
        ...,
        max_length = 255,
        description = 'Name of the competitor.'
    )
    activity_type: Optional[str] = Field(
        None,
        max_length = 255,
        description = (
            'Type of activity observed. Per req 7.3.4.3 typical values are '
            'PRODUCT, BANDEO, PROMOTIONAL_ACTIVITY.'
        )
    )
    product_name: Optional[str] = Field(
        None,
        max_length = 255,
        description = "Competitor's product name, if applicable."
    )
    details: Optional[str] = Field(
        None,
        description = 'General comments or details about the activity.'
    )
    # iter6 additions (req 7.3.4.3)
    price: Optional[Decimal] = Field(
        None, ge = 0,
        description = 'Observed price (2 decimals). Optional.',
        max_digits = 12, decimal_places = 2
    )
    latitude: Optional[float] = Field(
        None,
        description = 'Geolocation of the Competition Point (PC).'
    )
    longitude: Optional[float] = Field(
        None,
        description = 'Geolocation of the Competition Point (PC).'
    )
    location_description: Optional[str] = Field(
        None,
        description = (
            'Free-text description of the place (address). Mandatory '
            'when no open POS context is available; the service enforces '
            'this rule when pos_id is null.'
        )
    )

class ComplementaryCompetitionResponseSchema(BaseSchema):
    '''
        Response schema for a created Competition Report.
    '''
    id: int
    user_id: int
    company_id: int
    client_company_id: Optional[int] = None  # Binaria 2026-07-07
    pos_id: Optional[int]
    competitor_name: str
    activity_type: Optional[str]
    product_name: Optional[str]
    details: Optional[str]
    # iter6 additions
    price: Optional[Decimal] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_description: Optional[str] = None
    photos: List[PhotoResponseSchema] = []
    created_at: Optional[datetime]


# --- Binaria, 2026-07-07: LIST schemas for promo points and competition ---

class ComplementaryPromoPointQuerySchema(BaseSchema):
    '''
        Filters for GET /v1/replenishment/complementary/promo-points. pos_id
        and user_id are resolved through the visit attendance.
    '''
    company_id: Optional[int] = Field(None, description = 'Operator company filter.')
    client_company_id: Optional[int] = Field(None, description = 'Brand / client filter.')
    pos_id: Optional[int] = Field(None, description = 'POS filter (via the visit attendance).')
    user_id: Optional[int] = Field(
        None, description = 'Operator filter (via the visit attendance).'
    )
    date_from: Optional[datetime] = Field(None, description = 'created_at >= this datetime.')
    date_to: Optional[datetime] = Field(None, description = 'created_at <= this datetime.')
    limit: int = Field(50, ge = 1, le = 500)
    offset: int = Field(0, ge = 0)

class ComplementaryPromoPointListResponseSchema(BaseSchema):
    '''
        Wrapper for the promotional-point listing endpoint.
    '''
    items: List[ComplementaryPromoPointResponseSchema]
    total: int

class ComplementaryCompetitionQuerySchema(BaseSchema):
    '''
        Filters for GET /v1/replenishment/complementary/competition. Competition
        reports are not tied to an attendance, so user_id is filtered directly.
    '''
    company_id: Optional[int] = Field(None, description = 'Operator company filter.')
    client_company_id: Optional[int] = Field(None, description = 'Brand / client filter.')
    user_id: Optional[int] = Field(None, description = 'Operator filter.')
    date_from: Optional[datetime] = Field(None, description = 'created_at >= this datetime.')
    date_to: Optional[datetime] = Field(None, description = 'created_at <= this datetime.')
    limit: int = Field(50, ge = 1, le = 500)
    offset: int = Field(0, ge = 0)

class ComplementaryCompetitionListResponseSchema(BaseSchema):
    '''
        Wrapper for the competition-report listing endpoint.
    '''
    items: List[ComplementaryCompetitionResponseSchema]
    total: int
