'''
    Business logic services for the Trade Microservice
    Replenishments

    Iter 5 (Binaria, 2026-06-20):
        - CREATE services now persist client_company_id everywhere it was
          missing, `reviewed` on ReplenishmentReport, the split
          quantity_in_room + quantity_in_warehouse on ReplenishmentInventory
          (with `quantity` legacy column kept populated as the aggregated
          sum for back-compat) and batch_number + expiration_date on
          ReplenishmentReception.
        - Three new LIST services back the new GET endpoints requested by
          Binaria: paginated listing of reports, of per-visit inventory and
          of per-visit reception.
'''
from typing import List, Tuple
from datetime import datetime
from sqlalchemy import desc
from sqlalchemy.orm import Session
from services.products import (
    get_product_id_by_sku,
    validate_product_assigned_to_pos
)
from services.logger_config import custom_logger as logger
from services.exceptions import RegisterAlreadyExistsError
from services.utils import handle_service_errors, audit_event
from services.exceptions import (
    InvalidInputError,
    RegisterNotFoundError,
)

from models.replenishments import (
    ComplementaryBandeo,
    ComplementaryBandeoDetail,
    ComplementaryCompetition,
    ComplementaryPromoPoint,
    ReplenishmentInventory,                   # Binaria 2026-07-08
    ReplenishmentReception,
    ReplenishmentReport,
    ReplenishmentReportDetail,
)
from models.trade import Attendance
from schemas.replenishments import (
    ReplenishmentInventoryCreateSchema,       # Binaria 2026-07-08
    ReplenishmentInventoryQuerySchema,        # Binaria 2026-07-08
    ReplenishmentReceptionCreateSchema,
    ReplenishmentReceptionQuerySchema,
    ReplenishmentReportCreateSchema,
    ReplenishmentReportQuerySchema,
    ComplementaryBandeoReceiveSchema,    # iter6
    ComplementaryBandeoReturnSchema,     # iter6
    ComplementaryCompetitionCreateSchema,
    ComplementaryCompetitionQuerySchema,      # Binaria 2026-07-07
    ComplementaryPromoPointCreateSchema,
    ComplementaryPromoPointQuerySchema,       # Binaria 2026-07-07
)
from .trade_utils import (
    create_visit_items,
    filter_query_by_attendance,
    validate_active_attendance,
)

# --- B.2. REPLENISHMENT ACTIVITIES SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ReplenishmentReport', 'CREATE')
async def create_replenishment_report_service(
    db: Session,
    attendance_id: int,
    report_data: ReplenishmentReportCreateSchema
) -> ReplenishmentReport:
    '''
        Creates a new Replenishment Report metadata.

        iter5: persists `client_company_id` and `reviewed`.
    '''
    message = f'Creating Replenishment Report meta for attendance ID: {attendance_id}'
    logger.info(message)

    # 0. Validate Active Attendance
    validate_active_attendance(
        db = db,
        attendance_id = attendance_id,
        company_id = report_data.company_id,
        pos_id = report_data.pos_id
    )

    db_report = ReplenishmentReport(
        attendance_id = attendance_id,
        company_id = report_data.company_id,
        client_company_id = report_data.client_company_id,  # iter5
        comments = report_data.comments,
        reviewed = report_data.reviewed  # iter5
    )
    db.add(db_report)
    db.flush()  # obtain db_report.id before attaching the product detail

    # Binaria, 2026-07-07: per-product replaced yes/no detail. Each SKU is
    # resolved to its product_id and validated against the POS assortment,
    # mirroring the reception flow.
    for item in report_data.details:
        product_id = get_product_id_by_sku(db, report_data.company_id, item.product_sku)
        validate_product_assigned_to_pos(
            db, report_data.company_id, report_data.pos_id, product_id
        )
        db.add(ReplenishmentReportDetail(
            report_id = db_report.id,
            product_id = product_id,
            replaced = item.replaced,
            quantity = item.quantity,
            comments = item.comments,
        ))

    db.commit()
    db.refresh(db_report)

    return db_report

@handle_service_errors('TRADE')
async def list_replenishment_reports_service(
    db: Session,
    query: ReplenishmentReportQuerySchema
) -> Tuple[List[ReplenishmentReport], int]:
    '''
        Paginated listing of Replenishment reports. Mirrors the filter shape
        of GET /v1/impulses/sales: company / client_company / pos / attendance
        / reviewed / created_at range.

        Returns (items, total_matching_filters_before_pagination).
    '''
    message = f'Listing replenishment reports with filters: {query.model_dump(exclude_none=True)}'
    logger.info(message)

    base_query = db.query(ReplenishmentReport)
    if query.company_id is not None:
        base_query = base_query.filter(ReplenishmentReport.company_id == query.company_id)
    if query.client_company_id is not None:
        base_query = base_query.filter(
            ReplenishmentReport.client_company_id == query.client_company_id
        )
    if query.attendance_id is not None:
        base_query = base_query.filter(
            ReplenishmentReport.attendance_id == query.attendance_id
        )
    if query.reviewed is not None:
        base_query = base_query.filter(ReplenishmentReport.reviewed == query.reviewed)
    if query.date_from is not None:
        base_query = base_query.filter(ReplenishmentReport.created_at >= query.date_from)
    if query.date_to is not None:
        base_query = base_query.filter(ReplenishmentReport.created_at <= query.date_to)
    # Binaria, 2026-07-07: pos_id / user_id live on the visit attendance.
    if query.pos_id is not None or query.user_id is not None:
        base_query = base_query.join(
            Attendance, ReplenishmentReport.attendance_id == Attendance.id
        )
        if query.pos_id is not None:
            base_query = base_query.filter(Attendance.point_of_sale_id == query.pos_id)
        if query.user_id is not None:
            base_query = base_query.filter(Attendance.user_id == query.user_id)

    total = base_query.count()
    items = (
        base_query
            .order_by(ReplenishmentReport.created_at.desc())
            .offset(query.offset)
            .limit(query.limit)
            .all()
    )
    return items, total

# iter5 (Binaria, 2026-06-20): Replenishment inventory services removed.
# Inventory is now stored in the unified Impulses tables. Use the existing
# `services.impulses.create_impulse_inventory_start_service` /
# `create_impulse_inventory_end_service` for writes and
# `list_impulse_inventory_*` for reads.

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ReplenishmentReception', 'CREATE')
async def create_replenishment_reception_service(
    db: Session,
    attendance_id: int,
    reception_data: ReplenishmentReceptionCreateSchema
) -> List[ReplenishmentReception]:
    '''
        Creates multiple ReplenishmentReception records.

        iter5: persists batch_number + expiration_date (per item) and
        client_company_id (from parent payload via extra_fields).
    '''
    message = f'Creating Replenishment Reception for attendance ID: {attendance_id}'
    logger.info(message)

    return await create_visit_items(
        db = db,
        attendance_id = attendance_id,
        payload = reception_data,
        model_class = ReplenishmentReception,
        extra_fields = {  # iter5
            'client_company_id': reception_data.client_company_id
        }
    )

@handle_service_errors('TRADE')
async def list_replenishment_reception_service(
    db: Session,
    attendance_id: int,
    query: ReplenishmentReceptionQuerySchema
) -> Tuple[List[ReplenishmentReception], int]:
    '''
        iter5: lists reception rows for a given visit. Useful to inspect
        expirations registered for incoming batches on a single visit.
    '''
    message = (
        f'Listing replenishment reception for attendance {attendance_id} '
        f'with filters {query.model_dump(exclude_none=True)}'
    )
    logger.info(message)

    base_query = db.query(ReplenishmentReception).filter(
        ReplenishmentReception.attendance_id == attendance_id
    )
    if query.client_company_id is not None:
        base_query = base_query.filter(
            ReplenishmentReception.client_company_id == query.client_company_id
        )
    if query.product_id is not None:
        base_query = base_query.filter(
            ReplenishmentReception.product_id == query.product_id
        )
    if query.batch_number:
        base_query = base_query.filter(
            ReplenishmentReception.batch_number == query.batch_number
        )
    total = base_query.count()
    items = (
        base_query
            .order_by(ReplenishmentReception.created_at.desc())
            .offset(query.offset)
            .limit(query.limit)
            .all()
    )
    return items, total

# --- Replenishment Inventory services (Binaria, 2026-07-08, line-free) ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ReplenishmentInventory', 'CREATE')
async def create_replenishment_inventory_service(
    db: Session,
    attendance_id: int,
    inventory_data: ReplenishmentInventoryCreateSchema
) -> List[ReplenishmentInventory]:
    '''
        Registers a line-free replenishment inventory for a visit. The same
        product may appear on several lines (different batch / expiration /
        location); no uniqueness is enforced.
    '''
    message = f'Creating Replenishment Inventory for attendance ID: {attendance_id}'
    logger.info(message)

    return await create_visit_items(
        db = db,
        attendance_id = attendance_id,
        payload = inventory_data,
        model_class = ReplenishmentInventory,
        extra_fields = {'client_company_id': inventory_data.client_company_id}
    )

@handle_service_errors('TRADE')
async def get_latest_replenishment_inventory_service(
    db: Session,
    pos_id: int
) -> Tuple[List[ReplenishmentInventory], int]:
    '''
        Returns every line of the most recent replenishment inventory count
        registered at a POS (product + batch + expiration detail).
    '''
    latest = (
        db.query(ReplenishmentInventory)
        .join(Attendance, ReplenishmentInventory.attendance_id == Attendance.id)
        .filter(Attendance.point_of_sale_id == pos_id)
        .order_by(desc(ReplenishmentInventory.created_at))
        .first()
    )
    if latest is None:
        raise RegisterNotFoundError(
            detail = f'No replenishment inventory registered for POS {pos_id}.'
        )
    items = (
        db.query(ReplenishmentInventory)
        .filter(ReplenishmentInventory.attendance_id == latest.attendance_id)
        .order_by(ReplenishmentInventory.id.asc())
        .all()
    )
    return items, len(items)

@handle_service_errors('TRADE')
async def list_replenishment_inventory_service(
    db: Session,
    query: ReplenishmentInventoryQuerySchema
) -> Tuple[List[ReplenishmentInventory], int]:
    '''
        Paginated listing of replenishment inventory lines. company_id /
        pos_id / user_id are resolved through the visit attendance; the batch /
        expiration detail comes on every line.
    '''
    message = (
        f'Listing replenishment inventory with filters '
        f'{query.model_dump(exclude_none = True)}'
    )
    logger.info(message)

    base_query = db.query(ReplenishmentInventory).join(
        Attendance, ReplenishmentInventory.attendance_id == Attendance.id
    )
    base_query = filter_query_by_attendance(base_query, query)
    if query.client_company_id is not None:
        base_query = base_query.filter(
            ReplenishmentInventory.client_company_id == query.client_company_id
        )
    if query.date_from is not None:
        base_query = base_query.filter(ReplenishmentInventory.created_at >= query.date_from)
    if query.date_to is not None:
        base_query = base_query.filter(ReplenishmentInventory.created_at <= query.date_to)

    total = base_query.count()
    items = (
        base_query
        .order_by(desc(ReplenishmentInventory.created_at))
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )
    return items, total

# --- B.3. COMPLEMENTARY ACTIVITIES SERVICES ---

# iter6 (Binaria, 2026-06-22): Bandeo en ejecucion (req 7.3.4.1).
# The legacy one-shot create_complementary_bandeo_service was replaced by
# a 2-stage flow plus listing/lookup helpers:
#   * receive_complementary_bandeo_service  -> Recibir step  (status RECEIVED)
#   * return_complementary_bandeo_service   -> Devolver step (status RETURNED)
#   * list_complementary_bandeos_for_visit_service
#   * get_complementary_bandeo_by_id_service

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryBandeo', 'RECEIVE')
async def receive_complementary_bandeo_service(
    db: Session,
    attendance_id: int,
    bandeo_data: ComplementaryBandeoReceiveSchema
) -> ComplementaryBandeo:
    '''
        Recibir step: registers the products received for one planned
        bandeo in the visit and flips the header to status=RECEIVED.

        A single visit may register multiple bandeos, one per planned
        promotion; uniqueness is enforced on (attendance_id, promotion_id).
    '''
    message = (
        f'Receiving Bandeo (attendance {attendance_id}, '
        f'promotion {bandeo_data.promotion_id}).'
    )
    logger.info(message)

    validate_active_attendance(
        db = db,
        attendance_id = attendance_id,
        company_id = bandeo_data.company_id,
        pos_id = bandeo_data.pos_id
    )

    existing = db.query(ComplementaryBandeo).filter(
        ComplementaryBandeo.attendance_id == attendance_id,
        ComplementaryBandeo.promotion_id == bandeo_data.promotion_id,
    ).first()
    if existing:
        raise RegisterAlreadyExistsError(
            detail = (
                f'Bandeo already registered for visit {attendance_id} and '
                f'promotion {bandeo_data.promotion_id}.'
            )
        )

    now = datetime.utcnow()
    db_header = ComplementaryBandeo(
        attendance_id = attendance_id,
        company_id = bandeo_data.company_id,
        client_company_id = bandeo_data.client_company_id,
        promotion_id = bandeo_data.promotion_id,
        status = 'RECEIVED',
        received_at = now,
        comments = bandeo_data.comments,
    )
    db.add(db_header)
    db.flush()

    pos_id = bandeo_data.pos_id
    for item in bandeo_data.details:
        product_id = get_product_id_by_sku(
            db, bandeo_data.company_id, item.product_sku
        )
        validate_product_assigned_to_pos(
            db, bandeo_data.company_id, pos_id, product_id
        )
        db.add(ComplementaryBandeoDetail(
            bandeo_header_id = db_header.id,
            product_id = product_id,
            quantity_planned = item.quantity_planned,
            quantity_received = item.quantity_received,
            unit_of_measure = item.unit_of_measure,
        ))

    db.commit()
    db.refresh(db_header)
    return db_header


@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryBandeo', 'RETURN')
async def return_complementary_bandeo_service(
    db: Session,
    bandeo_id: int,
    return_data: ComplementaryBandeoReturnSchema
) -> ComplementaryBandeo:
    '''
        Devolver step: persists quantity_used / quantity_returned /
        observations per detail row and flips the header to
        status=RETURNED. Enforces the per-row controls demanded by req
        7.3.4.1 (qty_used <= qty_received, qty_returned <= qty_received,
        observations mandatory when overriding the default).
    '''
    db_header = db.query(ComplementaryBandeo).filter_by(id = bandeo_id).first()
    if not db_header:
        raise RegisterNotFoundError(detail = f'Bandeo {bandeo_id} not found.')

    if db_header.status != 'RECEIVED':
        raise InvalidInputError(
            detail = (
                f'Bandeo {bandeo_id} cannot be returned from status '
                f'{db_header.status!r}; expected RECEIVED.'
            )
        )

    details_by_id = {d.id: d for d in db_header.details}
    payload_ids = {row.id for row in return_data.details}
    if payload_ids != set(details_by_id):
        raise InvalidInputError(
            detail = (
                'Return payload must include every detail row of the '
                'bandeo header exactly once.'
            )
        )

    for row in return_data.details:
        detail = details_by_id[row.id]
        if row.quantity_used > detail.quantity_received:
            raise InvalidInputError(
                detail = (
                    f'quantity_used ({row.quantity_used}) exceeds '
                    f'quantity_received ({detail.quantity_received}) on '
                    f'detail {row.id}.'
                )
            )
        if row.quantity_returned > detail.quantity_received:
            raise InvalidInputError(
                detail = (
                    f'quantity_returned ({row.quantity_returned}) exceeds '
                    f'quantity_received ({detail.quantity_received}) on '
                    f'detail {row.id}.'
                )
            )
        default_returned = detail.quantity_received - row.quantity_used
        if row.quantity_returned != default_returned and not row.observations:
            raise InvalidInputError(
                detail = (
                    f'observations is required on detail {row.id} when '
                    f'quantity_returned ({row.quantity_returned}) differs '
                    f'from the calculated default ({default_returned}).'
                )
            )
        detail.quantity_used = row.quantity_used
        detail.quantity_returned = row.quantity_returned
        detail.observations = row.observations

    db_header.status = 'RETURNED'
    db_header.returned_at = datetime.utcnow()

    db.commit()
    db.refresh(db_header)
    return db_header


@handle_service_errors('TRADE')
async def list_complementary_bandeos_for_visit_service(
    db: Session,
    attendance_id: int
) -> Tuple[List[ComplementaryBandeo], int]:
    '''
        Returns every bandeo header registered for one visit, ordered
        oldest-first so the frontend can render them in execution order.
    '''
    query = db.query(ComplementaryBandeo).filter_by(
        attendance_id = attendance_id
    )
    total = query.count()
    items = query.order_by(ComplementaryBandeo.created_at.asc()).all()
    return items, total


@handle_service_errors('TRADE')
async def get_complementary_bandeo_by_id_service(
    db: Session,
    bandeo_id: int
) -> ComplementaryBandeo:
    '''
        Fetches one bandeo header with its details, used by the frontend
        when the operator re-enters the screen to keep editing while the
        visit remains open.
    '''
    db_header = db.query(ComplementaryBandeo).filter_by(id = bandeo_id).first()
    if not db_header:
        raise RegisterNotFoundError(detail = f'Bandeo {bandeo_id} not found.')
    return db_header

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryPromoPoint', 'CREATE')
async def create_complementary_promo_point_service(
    db: Session,
    attendance_id: int,
    promo_point_data: ComplementaryPromoPointCreateSchema
) -> ComplementaryPromoPoint:
    '''
        Creates a new Complementary Promotional Point report metadata.

        iter6: persists opening_time, closing_time and description in
        addition to the iter5 client_company_id.
    '''
    message = f'Creating Promo Point for attendance ID: {attendance_id}'
    logger.info(message)

    validate_active_attendance(
        db = db,
        attendance_id = attendance_id,
        company_id = promo_point_data.company_id,
        pos_id = promo_point_data.pos_id
    )

    if promo_point_data.closing_time <= promo_point_data.opening_time:
        raise InvalidInputError(
            detail = (
                'closing_time must be later than opening_time on the '
                'promotional point report.'
            )
        )

    db_report = ComplementaryPromoPoint(
        attendance_id = attendance_id,
        company_id = promo_point_data.company_id,
        client_company_id = promo_point_data.client_company_id,
        opening_time = promo_point_data.opening_time,
        closing_time = promo_point_data.closing_time,
        description = promo_point_data.description,
        comments = promo_point_data.comments,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

@handle_service_errors('TRADE')
async def list_complementary_promo_points_service(
    db: Session,
    query: ComplementaryPromoPointQuerySchema
) -> Tuple[List[ComplementaryPromoPoint], int]:
    '''
        Binaria, 2026-07-07: paginated listing of promotional-point reports.
        pos_id / user_id are resolved through the visit attendance.
    '''
    message = f'Listing promo points with filters {query.model_dump(exclude_none=True)}'
    logger.info(message)

    base_query = db.query(ComplementaryPromoPoint)
    if query.company_id is not None:
        base_query = base_query.filter(ComplementaryPromoPoint.company_id == query.company_id)
    if query.client_company_id is not None:
        base_query = base_query.filter(
            ComplementaryPromoPoint.client_company_id == query.client_company_id
        )
    if query.date_from is not None:
        base_query = base_query.filter(ComplementaryPromoPoint.created_at >= query.date_from)
    if query.date_to is not None:
        base_query = base_query.filter(ComplementaryPromoPoint.created_at <= query.date_to)
    if query.pos_id is not None or query.user_id is not None:
        base_query = base_query.join(
            Attendance, ComplementaryPromoPoint.attendance_id == Attendance.id
        )
        if query.pos_id is not None:
            base_query = base_query.filter(Attendance.point_of_sale_id == query.pos_id)
        if query.user_id is not None:
            base_query = base_query.filter(Attendance.user_id == query.user_id)

    total = base_query.count()
    items = (
        base_query
        .order_by(ComplementaryPromoPoint.created_at.desc())
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )
    return items, total

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryCompetition', 'CREATE')
async def create_complementary_competition_service(
    db: Session,
    competition_data: ComplementaryCompetitionCreateSchema
) -> ComplementaryCompetition:
    '''
        Creates a new general Competition Report metadata.

        iter6 (Binaria, 2026-06-22): persists price + latitude/longitude
        + location_description per req 7.3.4.3. When the operator is not
        inside an open POS, location_description is mandatory and the
        latitude/longitude must be provided to anchor the PC on the map.
    '''
    logger.info('Creating Competition Report')

    if competition_data.pos_id is None:
        if not competition_data.location_description:
            raise InvalidInputError(
                detail = (
                    'location_description is required on the Competition '
                    'Report when no POS is associated.'
                )
            )
        if (competition_data.latitude is None
                or competition_data.longitude is None):
            raise InvalidInputError(
                detail = (
                    'latitude and longitude are required on the Competition '
                    'Report when no POS is associated.'
                )
            )

    data = competition_data.model_dump()
    if 'pos_id' in data:
        data['point_of_sale_id'] = data.pop('pos_id')

    db_report = ComplementaryCompetition(
        **data
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report

@handle_service_errors('TRADE')
async def list_complementary_competitions_service(
    db: Session,
    query: ComplementaryCompetitionQuerySchema
) -> Tuple[List[ComplementaryCompetition], int]:
    '''
        Binaria, 2026-07-07: paginated listing of competition reports. These
        are not tied to an attendance, so user_id is filtered directly.
    '''
    message = f'Listing competition reports with filters {query.model_dump(exclude_none=True)}'
    logger.info(message)

    base_query = db.query(ComplementaryCompetition)
    if query.company_id is not None:
        base_query = base_query.filter(ComplementaryCompetition.company_id == query.company_id)
    if query.client_company_id is not None:
        base_query = base_query.filter(
            ComplementaryCompetition.client_company_id == query.client_company_id
        )
    if query.user_id is not None:
        base_query = base_query.filter(ComplementaryCompetition.user_id == query.user_id)
    if query.date_from is not None:
        base_query = base_query.filter(ComplementaryCompetition.created_at >= query.date_from)
    if query.date_to is not None:
        base_query = base_query.filter(ComplementaryCompetition.created_at <= query.date_to)

    total = base_query.count()
    items = (
        base_query
        .order_by(ComplementaryCompetition.created_at.desc())
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )
    return items, total
