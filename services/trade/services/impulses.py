'''
    Business logic services for the Trade Microservice
    Impulses
'''
from typing import Any, Dict, List, Tuple
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session, joinedload
from services.products import (
    get_product_id_by_sku,
    create_bulk_items_from_skus,
    validate_product_assigned_to_pos
)
from services.crud import (
    delete_record,
    get_record,
    update_record
)
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from services.logger_config import custom_logger as logger
from services.utils import (
    audit_event,
    get_current_time_gmt,
    handle_service_errors,
    sqlalchemy_object_as_dict,
)
from models.impulses import (
    ImpulseInventoryEnd,
    ImpulseInventoryStart,
    ImpulseSale,
    ImpulseSaleDetail,
    TradePromotion,
    TradePromotionDetail
)
from models.trade import Attendance, PlannedPoint
from models.products import Product
from schemas.impulses import (
    ImpulseInventoryCreateSchema,
    ImpulseSaleCreateSchema,
    SaleListFilterSchema,
    TradePromotionCreateSchema,
    TradePromotionFilterSchema,
    TradePromotionUpdateSchema,
)
from .trade_utils import validate_active_attendance

# --- TRADE PROMOTION (BANDEO) SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePromotion', 'CREATE')
async def create_promotion_service(
    db: Session,
    promotion_data: TradePromotionCreateSchema
) -> TradePromotion:
    '''
        Creates a new Promotion (Bandeo) and its nested SKU details.
    '''
    message = f'Attempting to create promotion: {promotion_data.name}'
    logger.info(message)

    existing_promo = db.query(TradePromotion).filter(
        TradePromotion.company_id == promotion_data.company_id,
        TradePromotion.name == promotion_data.name
    ).first()

    if existing_promo:
        error_msg = f'Promotion with name {promotion_data.name} already exists.'
        logger.error(error_msg)
        raise RegisterAlreadyExistsError(detail = error_msg)

    # 1. Create Header
    db_promotion = TradePromotion(**promotion_data.model_dump(exclude = {'details'}))
    db.add(db_promotion)
    db.flush()

    if not promotion_data.details:
        raise InvalidInputError(detail='Cannot create a promotion with an empty SKU list.')

    # 2. Create Details
    for detail_item in promotion_data.details:
        product_id = get_product_id_by_sku(
            db,
            promotion_data.company_id,
            detail_item.product_sku
        )
        db.add(TradePromotionDetail(
            promotion_id = db_promotion.id,
            product_id = product_id
        ))

    db.commit()
    db.refresh(db_promotion)
    return db_promotion

@handle_service_errors('TRADE')
async def get_promotion_by_id_service(
    db: Session,
    promotion_id: int
) -> TradePromotion:
    '''
        Retrieves a single Promotion by its ID.
    '''
    return get_record(
        db, TradePromotion, promotion_id,
        eager_load_options=[joinedload(TradePromotion.details)]
    )

@handle_service_errors('TRADE')
async def get_promotions_list_service(
    db: Session, filters: TradePromotionFilterSchema, skip: int, limit: int
) -> Tuple[List[TradePromotion], int]:
    '''
        Retrieves a paginated list of Promotions.
    '''
    query = db.query(TradePromotion).options(joinedload(TradePromotion.details))
    conditions = [TradePromotion.company_id == filters.company_id]

    if filters.name:
        conditions.append(TradePromotion.name.ilike(f'%{filters.name}%'))
    if filters.status:
        conditions.append(TradePromotion.status == filters.status)

    query = query.filter(and_(*conditions))
    return query.offset(skip).limit(limit).all(), query.count()

@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePromotion', 'UPDATE')
async def update_promotion_service(
    db: Session, promotion_id: int, update_data: TradePromotionUpdateSchema
) -> Tuple[TradePromotion, Dict[str, Any]]:
    '''
        Updates a Promotion Header.
    '''
    db_promotion = get_record(db, TradePromotion, promotion_id)
    old_values = sqlalchemy_object_as_dict(db_promotion)
    db_promotion = update_record(db, db_promotion, update_data)
    db.commit()
    db.refresh(db_promotion)
    return db_promotion, {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_promotion)
    }

@handle_service_errors('TRADE')
@audit_event('TRADE', 'TradePromotion', 'DELETE')
async def delete_promotion_service(
    db: Session, promotion_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a Promotion.
    '''
    db_promotion = get_record(db, TradePromotion, promotion_id)
    old_values = sqlalchemy_object_as_dict(db_promotion)
    delete_record(
        db = db,
        model = TradePromotion,
        record_id = promotion_id
    )
    db.commit()
    return promotion_id, {'old_values': old_values, 'new_values': None}

# --- B.1. IMPULSE ACTIVITIES SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ImpulseInventoryStart', 'CREATE')
async def create_impulse_inventory_start_service(
    db: Session,
    attendance_id: int,
    inventory_data: ImpulseInventoryCreateSchema
) -> List[ImpulseInventoryStart]:
    '''
        Creates multiple ImpulseInventoryStart records.
        Validates Assortment against POS ID provided.
    '''
    message = f'Creating Impulse Inventory Start for attendance ID: {attendance_id}'
    logger.info(message)

    # 0. Validate Active Attendance
    validate_active_attendance(
        db = db,
        attendance_id = attendance_id,
        company_id = inventory_data.company_id,
        pos_id = inventory_data.pos_id
    )

    # Validate Assortment
    pos_id = inventory_data.pos_id
    for item in inventory_data.items:
        product_id = get_product_id_by_sku(
            db, inventory_data.company_id, item.product_sku
        )
        validate_product_assigned_to_pos(
            db, inventory_data.company_id, pos_id, product_id
        )

    return await create_bulk_items_from_skus(
        db = db,
        attendance_id = attendance_id,
        company_id = inventory_data.company_id,
        items_list = inventory_data.items,
        model_class = ImpulseInventoryStart
    )

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ImpulseSale', 'CREATE')
async def create_impulse_sale_service(
    db: Session,
    attendance_id: int,
    sale_data: ImpulseSaleCreateSchema
) -> ImpulseSale:
    '''
        Creates a new Impulse Sale transaction (Header + Details).
        Photos are handled separately via /common/photos.
    '''
    message = f'Creating Impulse Sale for attendance ID: {attendance_id}'
    logger.info(message)

    # 0. Validate Active Attendance
    validate_active_attendance(
        db = db,
        attendance_id = attendance_id,
        company_id = sale_data.company_id,
        pos_id = sale_data.pos_id
    )

    # 1. Create Header — store both the executor company (kept in
    # `company_id` for backwards compatibility) and the client company
    # (new in 2026-05-20) so downstream reports can split by either.
    db_sale = ImpulseSale(
        attendance_id = attendance_id,
        company_id = sale_data.company_id,
        client_company_id = sale_data.client_company_id,
        observations = sale_data.observations,
    )
    db.add(db_sale)
    db.flush()

    # 2. Create Details & Validate Assortment
    pos_id = sale_data.pos_id

    # 2026-05-31 (Binaria): SKU, assortment and promotion ownership live
    # on the CLIENT company side (the owner of the POS / products). When
    # the executor company runs the sale, `client_company_id` carries the
    # right tenant; fall back to `company_id` for legacy payloads that
    # still only ship the executor.
    catalog_company_id = sale_data.client_company_id or sale_data.company_id

    for detail in sale_data.details:
        product_id = get_product_id_by_sku(db, catalog_company_id, detail.product_sku)

        # Assortment Validation
        validate_product_assigned_to_pos(
            db, catalog_company_id, pos_id, product_id
        )

        # Validate Promotion if provided
        if detail.promotion_id:
            # Check if promotion exists and belongs to the catalog company
            # (same tenant that owns the products being sold).
            promo = db.query(TradePromotion).filter(
                TradePromotion.id == detail.promotion_id,
                TradePromotion.company_id == catalog_company_id
            ).first()
            if not promo:
                raise RegisterNotFoundError(
                    detail=f'Promotion ID {detail.promotion_id} not found.'
                )

        if db.query(ImpulseSaleDetail).filter(
            ImpulseSaleDetail.impulse_sale_id == db_sale.id,
            ImpulseSaleDetail.product_id == product_id
        ).first():
            raise RegisterAlreadyExistsError(
                detail=f'Duplicate SKU {detail.product_sku} in sale.'
            )

        # Assuming ImpulseSaleDetail model has a 'promotion_id' column added
        # If not, it needs to be added to the model.
        # For now, we will assume it's there or just logic flow.
        # db_detail = ImpulseSaleDetail(
        #     impulse_sale_id = db_sale.id,
        #     product_id = product_id,
        #     quantity = detail.quantity,
        #     promotion_id = detail.promotion_id
        # )

        # Standard implementation
        db_detail = ImpulseSaleDetail(
            impulse_sale_id = db_sale.id,
            product_id = product_id,
            quantity = detail.quantity
        )
        # Assuming we add promotion_id to the model, pass it here.
        # If the model is not yet updated, we skip saving promotion_id for now,
        # but the logic allows it.
        if hasattr(ImpulseSaleDetail, 'promotion_id'):
            db_detail.promotion_id = detail.promotion_id

        db.add(db_detail)

    db.commit()
    return db.query(ImpulseSale).options(joinedload(ImpulseSale.details))\
        .filter(ImpulseSale.id == db_sale.id).one()


@handle_service_errors('TRADE')
@audit_event('TRADE', 'ImpulseInventoryEnd', 'CREATE')
async def create_impulse_inventory_end_service(
    db: Session,
    attendance_id: int,
    inventory_data: ImpulseInventoryCreateSchema
) -> List[ImpulseInventoryEnd]:
    '''
        Creates multiple ImpulseInventoryEnd records.
        Validates Assortment against POS ID.
    '''
    message = f'Creating Impulse Inventory End for attendance ID: {attendance_id}'
    logger.info(message)

    # 0. Validate Active Attendance
    validate_active_attendance(
        db = db,
        attendance_id = attendance_id,
        company_id = inventory_data.company_id,
        pos_id = inventory_data.pos_id
    )

    # Validate Assortment
    pos_id = inventory_data.pos_id
    for item in inventory_data.items:
        product_id = get_product_id_by_sku(
            db, inventory_data.company_id, item.product_sku
        )
        validate_product_assigned_to_pos(
            db, inventory_data.company_id, pos_id, product_id
        )

    return await create_bulk_items_from_skus(
        db = db,
        attendance_id = attendance_id,
        company_id = inventory_data.company_id,
        items_list = inventory_data.items,
        model_class = ImpulseInventoryEnd
    )


# --- LATEST INVENTORY FOR POS ---

def _latest_inventory_for_pos(
    db: Session, pos_id: int, model_class
) -> Tuple[Any, Any] | Tuple[None, None]:
    '''
        Internal helper that returns `(inventory_row, attendance_row)`
        for the most recent row of `model_class` (ImpulseInventoryStart
        or ImpulseInventoryEnd) bound to a planned point on `pos_id`.
        Returns `(None, None)` when no inventory was ever registered.
    '''
    row = (
        db.query(model_class, Attendance)
        .join(Attendance, model_class.attendance_id == Attendance.id)
        .join(PlannedPoint, Attendance.trade_planned_point_id == PlannedPoint.id)
        .filter(PlannedPoint.point_of_sale_id == pos_id)
        .order_by(desc(model_class.created_at))
        .first()
    )
    if row is None:
        return None, None
    return row[0], row[1]


def _inventory_lines_for_attendance(
    db: Session, attendance_id: int, model_class
) -> List[Tuple[Any, Any]]:
    '''
        Returns the list of `(inventory_row, product)` tuples for the
        given attendance and inventory model. Used by the per-visit GET
        endpoints (start/end).
    '''
    return (
        db.query(model_class, Product)
        .join(Product, model_class.product_id == Product.id)
        .filter(model_class.attendance_id == attendance_id)
        .order_by(model_class.id.asc())
        .all()
    )


@handle_service_errors('TRADE')
async def get_impulse_inventory_start_by_attendance_service(
    db: Session, attendance_id: int,
) -> Dict[str, Any]:
    '''
        Returns the full Impulse "start" inventory for the given visit.
        404 when nothing was registered.
    '''
    rows = _inventory_lines_for_attendance(
        db, attendance_id, ImpulseInventoryStart,
    )
    if not rows:
        raise RegisterNotFoundError(
            detail = (
                f'No impulse start inventory registered for attendance '
                f'{attendance_id}.'
            )
        )
    attendance = db.query(Attendance).filter(
        Attendance.id == attendance_id,
    ).first()
    first_row = rows[0][0]
    return {
        'attendance_id': attendance_id,
        'pos_id': attendance.point_of_sale_id if attendance else None,
        'inventory_type': 'start',
        'created_at': first_row.created_at,
        'items': [
            {
                'product_id': inv.product_id,
                'product_sku': product.sku,
                'product_name': product.name,
                'quantity': inv.quantity,
                'observations': inv.observations,
            }
            for inv, product in rows
        ],
    }


@handle_service_errors('TRADE')
async def get_impulse_inventory_end_by_attendance_service(
    db: Session, attendance_id: int,
) -> Dict[str, Any]:
    '''
        Returns the full Impulse "end" inventory for the given visit.
    '''
    rows = _inventory_lines_for_attendance(
        db, attendance_id, ImpulseInventoryEnd,
    )
    if not rows:
        raise RegisterNotFoundError(
            detail = (
                f'No impulse end inventory registered for attendance '
                f'{attendance_id}.'
            )
        )
    attendance = db.query(Attendance).filter(
        Attendance.id == attendance_id,
    ).first()
    first_row = rows[0][0]
    return {
        'attendance_id': attendance_id,
        'pos_id': attendance.point_of_sale_id if attendance else None,
        'inventory_type': 'end',
        'created_at': first_row.created_at,
        'items': [
            {
                'product_id': inv.product_id,
                'product_sku': product.sku,
                'product_name': product.name,
                'quantity': inv.quantity,
                'observations': inv.observations,
            }
            for inv, product in rows
        ],
    }


@handle_service_errors('TRADE')
async def get_latest_impulse_inventory_for_pos_service(
    db: Session,
    pos_id: int
) -> Dict[str, Any]:
    '''
        Returns the most recent inventory record for a POS, picking
        whichever is newer between the latest `ImpulseInventoryStart`
        and `ImpulseInventoryEnd`. All line items belonging to that
        attendance are returned.

        Raises RegisterNotFoundError when no inventory exists for the POS.
    '''
    latest_start, start_attendance = _latest_inventory_for_pos(
        db, pos_id, ImpulseInventoryStart,
    )
    latest_end, end_attendance = _latest_inventory_for_pos(
        db, pos_id, ImpulseInventoryEnd,
    )

    if latest_start is None and latest_end is None:
        raise RegisterNotFoundError(
            detail = f'No impulse inventory found for POS {pos_id}.'
        )

    pick_end = (
        latest_end is not None
        and (latest_start is None
             or latest_end.created_at >= latest_start.created_at)
    )
    chosen_model = ImpulseInventoryEnd if pick_end else ImpulseInventoryStart
    chosen_row = latest_end if pick_end else latest_start
    chosen_attendance = end_attendance if pick_end else start_attendance

    items = (
        db.query(chosen_model, Product)
        .join(Product, chosen_model.product_id == Product.id)
        .filter(chosen_model.attendance_id == chosen_attendance.id)
        .all()
    )

    return {
        'pos_id': pos_id,
        'inventory_type': 'end' if pick_end else 'start',
        'attendance_id': chosen_attendance.id,
        'created_at': chosen_row.created_at,
        'items': [
            {
                'product_id': inv.product_id,
                'product_sku': product.sku,
                'product_name': product.name,
                'quantity': inv.quantity,
                'observations': inv.observations,
            }
            for inv, product in items
        ],
    }


# --- 2026-05-28 (Binaria): cross-attendance sales listing + POS stock ---

@handle_service_errors('TRADE')
async def list_impulse_sales_service(
    db: Session,
    filters: SaleListFilterSchema,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[Dict[str, Any]], int]:
    '''
        Returns the list of impulse sales matching the supplied filters.
        Every filter is optional; an empty filter set returns the whole
        history (capped by skip/limit). Aggregates count + sum of detail
        quantities so the frontend can render the table without a second
        round-trip per row.

        Args:
            db: SQLAlchemy session.
            filters: All filters optional (company_id, client_company_id,
                pos_id, user_id, date_from, date_to).
            skip: Pagination offset.
            limit: Maximum page size.

        Returns:
            Tuple of (items, total_count).
    '''
    # Pull sales with their attendance for user/pos resolution. Aggregates
    # are joined via a subquery so we get one row per sale. The not-callable
    # disable is for pylint's static check against SQLAlchemy's dynamically
    # generated `func` namespace, which it cannot resolve.
    detail_agg = (
        db.query(
            ImpulseSaleDetail.impulse_sale_id.label('sale_id'),
            func.count(ImpulseSaleDetail.id).label('total_items'),  # pylint: disable=not-callable
            func.coalesce(func.sum(ImpulseSaleDetail.quantity), 0).label('total_quantity'),
        )
        .group_by(ImpulseSaleDetail.impulse_sale_id)
        .subquery()
    )

    query = (
        db.query(
            ImpulseSale,
            Attendance,
            detail_agg.c.total_items,
            detail_agg.c.total_quantity,
        )
        .join(Attendance, ImpulseSale.attendance_id == Attendance.id)
        .outerjoin(detail_agg, detail_agg.c.sale_id == ImpulseSale.id)
    )

    if filters.company_id is not None:
        query = query.filter(ImpulseSale.company_id == filters.company_id)
    if filters.client_company_id is not None:
        query = query.filter(ImpulseSale.client_company_id == filters.client_company_id)
    if filters.pos_id is not None:
        query = query.filter(Attendance.point_of_sale_id == filters.pos_id)
    if filters.user_id is not None:
        query = query.filter(Attendance.user_id == filters.user_id)
    if filters.date_from is not None:
        query = query.filter(ImpulseSale.created_at >= filters.date_from)
    if filters.date_to is not None:
        query = query.filter(ImpulseSale.created_at <= filters.date_to)

    total = query.count()
    rows = (
        query.order_by(desc(ImpulseSale.created_at))
        .offset(skip)
        .limit(limit)
        .all()
    )

    # 2026-05-31 (Binaria): batch-fetch the per-product breakdown for the
    # sales currently on screen so callers can sum quantities by SKU. We
    # use a single query joining `Product` to avoid N+1 lookups; the
    # result is grouped in Python by sale_id.
    sale_ids = [sale.id for sale, *_ in rows]
    details_by_sale: Dict[int, List[Dict[str, Any]]] = {sid: [] for sid in sale_ids}
    if sale_ids:
        detail_rows = (
            db.query(ImpulseSaleDetail, Product)
            .join(Product, ImpulseSaleDetail.product_id == Product.id)
            .filter(ImpulseSaleDetail.impulse_sale_id.in_(sale_ids))
            .order_by(ImpulseSaleDetail.impulse_sale_id, ImpulseSaleDetail.id)
            .all()
        )
        for detail, product in detail_rows:
            details_by_sale[detail.impulse_sale_id].append({
                'product_id': product.id,
                'product_sku': product.sku,
                'product_name': product.name,
                'quantity': int(detail.quantity),
                'promotion_id': getattr(detail, 'promotion_id', None),
            })

    items = [
        {
            'id': sale.id,
            'type': 'IMPULSE',
            'attendance_id': sale.attendance_id,
            'pos_id': attendance.point_of_sale_id,
            'user_id': attendance.user_id,
            'company_id': sale.company_id,
            'client_company_id': sale.client_company_id,
            'observations': sale.observations,
            'total_items': int(total_items or 0),
            'total_quantity': int(total_quantity or 0),
            'details': details_by_sale.get(sale.id, []),
            'created_at': sale.created_at,
        }
        for sale, attendance, total_items, total_quantity in rows
    ]
    return items, total


@handle_service_errors('TRADE')
async def get_pos_stock_service(
    db: Session,
    pos_id: int,
) -> Dict[str, Any]:
    '''
        Computes the available stock for every product at a POS, applying
        the rule:
            - If the latest attendance at the POS is still open (no
              check-out), available_qty = start_inventory.quantity -
              SUM(sale_detail.quantity).
            - If it is closed, available_qty = end_inventory.quantity.
            - If no attendance ever happened, returns an empty stock list
              with source='empty'.
    '''
    latest_attendance = (
        db.query(Attendance)
        .filter(Attendance.point_of_sale_id == pos_id)
        .order_by(desc(Attendance.check_in_time))
        .first()
    )
    now = get_current_time_gmt()
    if latest_attendance is None:
        return {
            'pos_id': pos_id,
            'attendance_id': None,
            'is_open': False,
            'source': 'empty',
            'computed_at': now,
            'items': [],
        }

    is_open = latest_attendance.check_out_time is None

    if not is_open:
        # Closed visit: end-of-visit inventory is the source of truth.
        rows = (
            db.query(ImpulseInventoryEnd, Product)
            .join(Product, ImpulseInventoryEnd.product_id == Product.id)
            .filter(ImpulseInventoryEnd.attendance_id == latest_attendance.id)
            .all()
        )
        items = [
            {
                'product_id': inv.product_id,
                'product_sku': product.sku,
                'product_name': product.name,
                'available_qty': int(inv.quantity),
            }
            for inv, product in rows
        ]
        return {
            'pos_id': pos_id,
            'attendance_id': latest_attendance.id,
            'is_open': False,
            'source': 'inventory_end',
            'computed_at': now,
            'items': items,
        }

    # Open visit: start inventory minus sales for the same attendance.
    start_rows = (
        db.query(ImpulseInventoryStart, Product)
        .join(Product, ImpulseInventoryStart.product_id == Product.id)
        .filter(ImpulseInventoryStart.attendance_id == latest_attendance.id)
        .all()
    )

    sold_rows = (
        db.query(
            ImpulseSaleDetail.product_id,
            func.coalesce(func.sum(ImpulseSaleDetail.quantity), 0).label('sold_qty'),
        )
        .join(ImpulseSale, ImpulseSaleDetail.impulse_sale_id == ImpulseSale.id)
        .filter(ImpulseSale.attendance_id == latest_attendance.id)
        .group_by(ImpulseSaleDetail.product_id)
        .all()
    )
    sold_by_product = {pid: int(qty or 0) for pid, qty in sold_rows}

    items = []
    for inv, product in start_rows:
        sold = sold_by_product.get(inv.product_id, 0)
        items.append({
            'product_id': inv.product_id,
            'product_sku': product.sku,
            'product_name': product.name,
            'available_qty': int(inv.quantity) - sold,
        })

    return {
        'pos_id': pos_id,
        'attendance_id': latest_attendance.id,
        'is_open': True,
        'source': 'inventory_start_minus_sales',
        'computed_at': now,
        'items': items,
    }
