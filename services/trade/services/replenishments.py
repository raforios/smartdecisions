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
from sqlalchemy.orm import Session, joinedload
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
from models.impulses import TradePromotion  # Binaria 2026-07-17
from schemas.replenishments import (
    ReplenishmentInventoryCreateSchema,       # Binaria 2026-07-08
    ReplenishmentInventoryQuerySchema,        # Binaria 2026-07-08
    ReplenishmentReceptionCreateSchema,
    ReplenishmentReceptionGlobalQuerySchema,
    ReplenishmentReceptionQuerySchema,
    ReplenishmentReportCreateSchema,
    ReplenishmentReportQuerySchema,
    ComplementaryBandeoGlobalQuerySchema,     # Binaria 2026-07-17
    ComplementaryBandeoPlanSchema,            # Binaria 2026-07-17
    ComplementaryBandeoReceiveSchema,    # iter6
    ComplementaryBandeoReturnSchema,     # iter6
    ComplementaryCompetitionCreateSchema,
    ComplementaryCompetitionQuerySchema,      # Binaria 2026-07-07
    ComplementaryPromoPointCreateSchema,
    ComplementaryPromoPointQuerySchema,       # Binaria 2026-07-07
)
from .trade_utils import (
    attach_visit_fields,
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

    # Binaria 2026-07-08: always join the visit attendance so pos_id / user_id
    # can both filter and be exposed in the response.
    base_query = db.query(ReplenishmentReport, Attendance).join(
        Attendance, ReplenishmentReport.attendance_id == Attendance.id
    )
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
    if query.pos_id is not None:
        base_query = base_query.filter(Attendance.point_of_sale_id == query.pos_id)
    if query.user_id is not None:
        base_query = base_query.filter(Attendance.user_id == query.user_id)

    total = base_query.count()
    rows = (
        base_query
            .order_by(ReplenishmentReport.created_at.desc())
            .offset(query.offset)
            .limit(query.limit)
            .all()
    )
    items = [attach_visit_fields(report, attendance) for report, attendance in rows]
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

    created = await create_visit_items(
        db = db,
        attendance_id = attendance_id,
        payload = reception_data,
        model_class = ReplenishmentReception,
        extra_fields = {  # iter5
            'client_company_id': reception_data.client_company_id
        }
    )
    # Binaria 2026-07-08: expose company/pos/user (via attendance) in the response.
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    return [attach_visit_fields(row, attendance) for row in created]

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

    base_query = db.query(ReplenishmentReception, Attendance).join(
        Attendance, ReplenishmentReception.attendance_id == Attendance.id
    ).filter(ReplenishmentReception.attendance_id == attendance_id)
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
    rows = (
        base_query
            .order_by(ReplenishmentReception.created_at.desc())
            .offset(query.offset)
            .limit(query.limit)
            .all()
    )
    items = [attach_visit_fields(row, attendance) for row, attendance in rows]
    return items, total


@handle_service_errors('TRADE')
async def list_all_replenishment_receptions_service(
    db: Session,
    query: ReplenishmentReceptionGlobalQuerySchema
) -> Tuple[List[ReplenishmentReception], int]:
    '''
        Binaria 2026-07-08: paginated listing of supplier reception rows across
        all visits, filtered by company_id / client_company_id / pos_id /
        user_id (via the visit attendance) and a created_at range.
    '''
    message = (
        f'Listing all replenishment receptions with filters '
        f'{query.model_dump(exclude_none = True)}'
    )
    logger.info(message)

    base_query = db.query(ReplenishmentReception, Attendance).join(
        Attendance, ReplenishmentReception.attendance_id == Attendance.id
    )
    base_query = filter_query_by_attendance(base_query, query)
    if query.client_company_id is not None:
        base_query = base_query.filter(
            ReplenishmentReception.client_company_id == query.client_company_id
        )
    if query.date_from is not None:
        base_query = base_query.filter(ReplenishmentReception.created_at >= query.date_from)
    if query.date_to is not None:
        base_query = base_query.filter(ReplenishmentReception.created_at <= query.date_to)

    total = base_query.count()
    rows = (
        base_query
        .order_by(desc(ReplenishmentReception.created_at))
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )
    items = [attach_visit_fields(row, attendance) for row, attendance in rows]
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

    created = await create_visit_items(
        db = db,
        attendance_id = attendance_id,
        payload = inventory_data,
        model_class = ReplenishmentInventory,
        extra_fields = {'client_company_id': inventory_data.client_company_id}
    )
    # Binaria 2026-07-08: expose company/pos/user (via attendance) in the response.
    attendance = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    return [attach_visit_fields(row, attendance) for row in created]

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
    attendance = db.query(Attendance).filter(
        Attendance.id == latest.attendance_id
    ).first()
    items = (
        db.query(ReplenishmentInventory)
        .filter(ReplenishmentInventory.attendance_id == latest.attendance_id)
        .order_by(ReplenishmentInventory.id.asc())
        .all()
    )
    items = [attach_visit_fields(row, attendance) for row in items]
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

    base_query = db.query(ReplenishmentInventory, Attendance).join(
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
    rows = (
        base_query
        .order_by(desc(ReplenishmentInventory.created_at))
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )
    items = [attach_visit_fields(row, attendance) for row, attendance in rows]
    return items, total

# --- B.3. COMPLEMENTARY ACTIVITIES SERVICES ---

# iter6 (Binaria, 2026-06-22): Bandeo en ejecucion (req 7.3.4.1).
# The legacy one-shot create_complementary_bandeo_service was replaced by
# a 2-stage flow plus listing/lookup helpers:
#   * receive_complementary_bandeo_service  -> Recibir step  (status RECEIVED)
#   * return_complementary_bandeo_service   -> Devolver step (status RETURNED)
#   * list_complementary_bandeos_for_visit_service
#   * get_complementary_bandeo_by_id_service

def _attach_bandeo_skus(header: ComplementaryBandeo) -> ComplementaryBandeo:
    '''
        Binaria 2026-07-17: exposes each detail's product_sku (from the linked
        Product) so the bandeo response carries the SKU per line.
    '''
    for detail in header.details:
        detail.product_sku = detail.product.sku if detail.product else None
    return header


@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryBandeo', 'PLAN')
async def plan_complementary_bandeo_service(
    db: Session,
    plan_data: ComplementaryBandeoPlanSchema
) -> ComplementaryBandeo:
    '''
        Plan step (Binaria 2026-07-17): assigns a promotion to a POS for a
        planned visit date. Creates the header with status=PENDING and one
        detail per SKU, where quantity_planned = promotion_quantity *
        sku_quantity (from the promotion definition). attendance_id is filled
        later at the Receive step. Uniqueness: (pos_id, planned_date, promotion).
    '''
    message = (
        f'Planning Bandeo (pos {plan_data.pos_id}, promotion '
        f'{plan_data.promotion_id}, date {plan_data.planned_date}).'
    )
    logger.info(message)

    promotion = db.query(TradePromotion).options(
        joinedload(TradePromotion.details)
    ).filter(
        TradePromotion.id == plan_data.promotion_id,
        TradePromotion.company_id == plan_data.company_id,
    ).first()
    if not promotion:
        raise RegisterNotFoundError(
            detail = (
                f'Promotion {plan_data.promotion_id} not found for company '
                f'{plan_data.company_id}.'
            )
        )
    sku_quantity_by_product = {
        detail.product_id: detail.sku_quantity for detail in promotion.details
    }

    existing = db.query(ComplementaryBandeo).filter(
        ComplementaryBandeo.pos_id == plan_data.pos_id,
        ComplementaryBandeo.planned_date == plan_data.planned_date,
        ComplementaryBandeo.promotion_id == plan_data.promotion_id,
    ).first()
    if existing:
        raise RegisterAlreadyExistsError(
            detail = (
                f'A bandeo is already planned for POS {plan_data.pos_id}, '
                f'promotion {plan_data.promotion_id} on {plan_data.planned_date}.'
            )
        )

    db_header = ComplementaryBandeo(
        company_id = plan_data.company_id,
        client_company_id = plan_data.client_company_id,
        pos_id = plan_data.pos_id,
        planned_date = plan_data.planned_date,
        promotion_id = plan_data.promotion_id,
        promotion_quantity = plan_data.promotion_quantity,
        status = 'PENDING',
        comments = plan_data.comments,
    )
    db.add(db_header)
    db.flush()

    for item in plan_data.details:
        product_id = get_product_id_by_sku(db, plan_data.company_id, item.product_sku)
        validate_product_assigned_to_pos(
            db, plan_data.company_id, plan_data.pos_id, product_id
        )
        sku_quantity = sku_quantity_by_product.get(product_id)
        if sku_quantity is None:
            raise InvalidInputError(
                detail = (
                    f'SKU {item.product_sku} is not part of promotion '
                    f'{plan_data.promotion_id}.'
                )
            )
        db.add(ComplementaryBandeoDetail(
            bandeo_header_id = db_header.id,
            product_id = product_id,
            quantity_planned = plan_data.promotion_quantity * sku_quantity,
            quantity_received = 0,
            unit_of_measure = item.unit_of_measure,
        ))

    db.commit()
    db.refresh(db_header)
    return _attach_bandeo_skus(db_header)


@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryBandeo', 'RECEIVE')
async def receive_complementary_bandeo_service(
    db: Session,
    attendance_id: int,
    bandeo_id: int,
    bandeo_data: ComplementaryBandeoReceiveSchema
) -> ComplementaryBandeo:
    '''
        Recibir step (Binaria 2026-07-17): links a PLANNED bandeo to the visit
        and persists the quantity received per SKU, flipping status to RECEIVED.
        quantity_planned is NOT touched (fixed at the Plan step).
    '''
    message = f'Receiving Bandeo {bandeo_id} on visit {attendance_id}.'
    logger.info(message)

    db_header = db.query(ComplementaryBandeo).filter_by(id = bandeo_id).first()
    if not db_header:
        raise RegisterNotFoundError(detail = f'Bandeo {bandeo_id} not found.')
    if db_header.status != 'PENDING':
        raise InvalidInputError(
            detail = (
                f'Bandeo {bandeo_id} cannot be received from status '
                f'{db_header.status!r}; expected PENDING.'
            )
        )

    validate_active_attendance(
        db = db,
        attendance_id = attendance_id,
        company_id = bandeo_data.company_id,
        pos_id = bandeo_data.pos_id
    )

    details_by_product = {detail.product_id: detail for detail in db_header.details}
    for item in bandeo_data.details:
        product_id = get_product_id_by_sku(db, bandeo_data.company_id, item.product_sku)
        detail = details_by_product.get(product_id)
        if detail is None:
            raise InvalidInputError(
                detail = (
                    f'SKU {item.product_sku} is not part of the planned bandeo '
                    f'{bandeo_id}.'
                )
            )
        detail.quantity_received = item.quantity_received

    db_header.attendance_id = attendance_id
    db_header.status = 'RECEIVED'
    db_header.received_at = datetime.utcnow()

    db.commit()
    db.refresh(db_header)
    return _attach_bandeo_skus(db_header)


@handle_service_errors('TRADE')
@audit_event('TRADE', 'ComplementaryBandeo', 'RETURN')
async def return_complementary_bandeo_service(
    db: Session,
    attendance_id: int,
    bandeo_id: int,
    return_data: ComplementaryBandeoReturnSchema
) -> ComplementaryBandeo:
    '''
        Devolver step (Binaria 2026-07-17): persists quantity_used /
        quantity_returned / observations per SKU and flips the header to
        status=RETURNED. Rows are matched by product_sku. Enforces the per-row
        controls (qty_used <= qty_received, qty_returned <= qty_received,
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
    if db_header.attendance_id != attendance_id:
        raise InvalidInputError(
            detail = (
                f'Bandeo {bandeo_id} was received in visit '
                f'{db_header.attendance_id}, not {attendance_id}.'
            )
        )

    details_by_product = {detail.product_id: detail for detail in db_header.details}
    seen_products = set()
    for row in return_data.details:
        product_id = get_product_id_by_sku(db, db_header.company_id, row.product_sku)
        detail = details_by_product.get(product_id)
        if detail is None:
            raise InvalidInputError(
                detail = (
                    f'SKU {row.product_sku} is not part of bandeo {bandeo_id}.'
                )
            )
        seen_products.add(product_id)
        if row.quantity_used > detail.quantity_received:
            raise InvalidInputError(
                detail = (
                    f'quantity_used ({row.quantity_used}) exceeds '
                    f'quantity_received ({detail.quantity_received}) on SKU '
                    f'{row.product_sku}.'
                )
            )
        if row.quantity_returned > detail.quantity_received:
            raise InvalidInputError(
                detail = (
                    f'quantity_returned ({row.quantity_returned}) exceeds '
                    f'quantity_received ({detail.quantity_received}) on SKU '
                    f'{row.product_sku}.'
                )
            )
        default_returned = detail.quantity_received - row.quantity_used
        if row.quantity_returned != default_returned and not row.observations:
            raise InvalidInputError(
                detail = (
                    f'observations is required on SKU {row.product_sku} when '
                    f'quantity_returned ({row.quantity_returned}) differs from '
                    f'the calculated default ({default_returned}).'
                )
            )
        detail.quantity_used = row.quantity_used
        detail.quantity_returned = row.quantity_returned
        detail.observations = row.observations

    if seen_products != set(details_by_product):
        raise InvalidInputError(
            detail = 'Return payload must include every SKU of the bandeo exactly once.'
        )

    db_header.status = 'RETURNED'
    db_header.returned_at = datetime.utcnow()

    db.commit()
    db.refresh(db_header)
    return _attach_bandeo_skus(db_header)


def _bandeo_query_with_details(db: Session):
    '''Base ComplementaryBandeo query eager-loading details+product and photos.'''
    return db.query(ComplementaryBandeo).options(
        joinedload(ComplementaryBandeo.details).joinedload(ComplementaryBandeoDetail.product),
        joinedload(ComplementaryBandeo.photos),
    )


@handle_service_errors('TRADE')
async def list_complementary_bandeos_for_visit_service(
    db: Session,
    attendance_id: int
) -> Tuple[List[ComplementaryBandeo], int]:
    '''
        Returns every bandeo header registered for one visit, ordered
        oldest-first, with its details (all four quantities) and photos.
    '''
    query = _bandeo_query_with_details(db).filter(
        ComplementaryBandeo.attendance_id == attendance_id
    )
    total = query.count()
    items = query.order_by(ComplementaryBandeo.created_at.asc()).all()
    items = [_attach_bandeo_skus(header) for header in items]
    return items, total


@handle_service_errors('TRADE')
async def get_complementary_bandeo_by_id_service(
    db: Session,
    bandeo_id: int
) -> ComplementaryBandeo:
    '''
        Fetches one bandeo header with its details and photos. Works whether or
        not a visit is open (usable both for in-field editing and later
        consultation).
    '''
    db_header = _bandeo_query_with_details(db).filter(
        ComplementaryBandeo.id == bandeo_id
    ).first()
    if not db_header:
        raise RegisterNotFoundError(detail = f'Bandeo {bandeo_id} not found.')
    return _attach_bandeo_skus(db_header)


@handle_service_errors('TRADE')
async def list_all_complementary_bandeos_service(
    db: Session,
    query: ComplementaryBandeoGlobalQuerySchema
) -> Tuple[List[ComplementaryBandeo], int]:
    '''
        Binaria 2026-07-17: paginated listing of complete bandeo records across
        POS / visits, filtered by company / client / pos / user / status and a
        created_at range. pos_id lives on the header; user_id is resolved
        through the visit attendance (planned bandeos with no visit are excluded
        only when user_id is supplied).
    '''
    message = (
        f'Listing all bandeos with filters {query.model_dump(exclude_none = True)}'
    )
    logger.info(message)

    base_query = _bandeo_query_with_details(db).outerjoin(
        Attendance, ComplementaryBandeo.attendance_id == Attendance.id
    )
    if query.company_id is not None:
        base_query = base_query.filter(ComplementaryBandeo.company_id == query.company_id)
    if query.client_company_id is not None:
        base_query = base_query.filter(
            ComplementaryBandeo.client_company_id == query.client_company_id
        )
    if query.pos_id is not None:
        base_query = base_query.filter(ComplementaryBandeo.pos_id == query.pos_id)
    if query.user_id is not None:
        base_query = base_query.filter(Attendance.user_id == query.user_id)
    if query.status is not None:
        base_query = base_query.filter(ComplementaryBandeo.status == query.status)
    if query.date_from is not None:
        base_query = base_query.filter(ComplementaryBandeo.created_at >= query.date_from)
    if query.date_to is not None:
        base_query = base_query.filter(ComplementaryBandeo.created_at <= query.date_to)

    total = base_query.count()
    items = (
        base_query
        .order_by(desc(ComplementaryBandeo.created_at))
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )
    items = [_attach_bandeo_skus(header) for header in items]
    return items, total

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

    # Binaria 2026-07-08: always join the visit attendance so pos_id / user_id
    # can both filter and be exposed in the response.
    base_query = db.query(ComplementaryPromoPoint, Attendance).join(
        Attendance, ComplementaryPromoPoint.attendance_id == Attendance.id
    )
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
    if query.pos_id is not None:
        base_query = base_query.filter(Attendance.point_of_sale_id == query.pos_id)
    if query.user_id is not None:
        base_query = base_query.filter(Attendance.user_id == query.user_id)

    total = base_query.count()
    rows = (
        base_query
        .order_by(ComplementaryPromoPoint.created_at.desc())
        .offset(query.offset)
        .limit(query.limit)
        .all()
    )
    items = [attach_visit_fields(row, attendance) for row, attendance in rows]
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
