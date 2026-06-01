'''
    Business Logic for POS.
'''
from datetime import datetime
from typing import Any, Dict, List, Tuple
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from services.products import get_product_id_by_sku
from services.crud import (
    delete_record,
    get_record,
    update_record
)
from services.exceptions import (
    InvalidInputError,
    RegisterAlreadyExistsError,
)
from services.logger_config import custom_logger as logger
from services.utils import (
    generic_bulk_processor,
    handle_service_errors,
    audit_event,
    perform_bulk_upload,
    sqlalchemy_object_as_dict
)
from models.pos import (
    PointOfSale,
    PointOfSaleInventory,
    PointOfSaleStatus
)
from models.trade import PlannedPoint
from models.products import Product, ProductAssignmentPOS
from schemas.pos import (
    POSFilterSchema,
    POSInventoryBulkCreateSchema,
    PointOfSaleBulkCreateSchema,
    PointOfSaleUpdateSchema,
    PointOfSaleCreateSchema,
    POSInventoryCreateSchema,
    POSInventoryUpdateSchema
)

def _process_pos_initial_inventory(
    db: Session,
    pos_id: int,
    company_id: int,
    inventory_items: List[Any]
) -> None:
    '''
        Helper to process initial inventory list for POS creation.
    '''
    for item in inventory_items:
        data = item.model_dump()
        sku = data.pop('product_sku')
        product_id = get_product_id_by_sku(db, company_id, sku)

        data.update({
            'product_id': product_id,
            'point_of_sale_id': pos_id,
            'company_id': company_id
        })
        db.add(PointOfSaleInventory(**data))

def _validate_mandatory_fields_for_active_status(pos_object: PointOfSale) -> List[str]:
    """
        Checks if all mandatory fields are present in a PointOfSale object for ACTIVE status.
        Returns a list of missing field names.
    """
    missing_fields = []
    if not pos_object.code:
        missing_fields.append('code')
    if not pos_object.name:
        missing_fields.append('name')
    if not pos_object.country_id:
        missing_fields.append('country_id')
    if not pos_object.city_id:
        missing_fields.append('city_id')
    if not pos_object.zone_id:
        missing_fields.append('zone_id')
    if not pos_object.address:
        missing_fields.append('address')
    if pos_object.latitude is None:
        missing_fields.append('latitude')
    if pos_object.longitude is None:
        missing_fields.append('longitude')
    if pos_object.max_checkin_distance is None:
        missing_fields.append('max_checkin_distance')
    if not pos_object.pos_type_id:
        missing_fields.append('pos_type_id')
    if not pos_object.channel_id:
        missing_fields.append('channel_id')
    return missing_fields

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSale', 'CREATE')
async def create_pos_with_inventory_service(
    db: Session,
    pos_data: PointOfSaleCreateSchema
) -> Tuple[PointOfSale, Dict[str, Any]]:
    '''
        Creates a new POS and its nested initial inventory records.
    '''
    message = f'Creating POS Code: {pos_data.code}, Name: {pos_data.name
            } for company: {pos_data.company_id}'
    logger.info(message)

    # 1. Validation for unique code and external_code within the company
    # The SQLAlchemy model's UniqueConstraint handles the actual database-level uniqueness.
    # This check is for providing a user-friendly error message before DB commit.
    if db.query(PointOfSale).filter(
        PointOfSale.company_id == pos_data.company_id,
        (PointOfSale.code == pos_data.code) |
        (pos_data.external_code is not None and PointOfSale.external_code == pos_data.external_code)
    ).first():
        raise RegisterAlreadyExistsError(
            detail = f'Point of Sale with code {pos_data.code} or external code '
                     f'{pos_data.external_code} already exists for this company.'
        )

    # 2. Create POS
    # Pydantic's model_dump with exclude will handle passing the new fields directly
    db_pos = PointOfSale(**pos_data.model_dump(exclude={'initial_inventory'}))
    db.add(db_pos)
    db.flush() # Flush to get db_pos.id before processing inventory

    # 3. Process Inventory (Extracted to reduce locals)
    if pos_data.initial_inventory:
        _process_pos_initial_inventory(
            db, db_pos.id, pos_data.company_id, pos_data.initial_inventory
        )

    db.commit()
    db.refresh(db_pos)
    return db_pos, {'new_values': sqlalchemy_object_as_dict(db_pos)}

@handle_service_errors('TRADE')
async def get_pos_by_id_service(
    db: Session, pos_id: int
) -> PointOfSale:
    '''
        Retrieves a PointOfSale record by ID with inventory.
    '''
    db_pos = get_record(
        db, PointOfSale, pos_id,
        eager_load_options = [
            joinedload(PointOfSale.inventory).joinedload(PointOfSaleInventory.product)
        ]
    )

    # Populate dynamic fields for Pydantic schema
    for item in db_pos.inventory:
        if item.product:
            setattr(item, 'product_sku', item.product.sku)
            setattr(item, 'product_name', item.product.name)

    return db_pos

@handle_service_errors('TRADE')
async def get_pos_list_service(
    db: Session, filters: POSFilterSchema, skip: int, limit: int
) -> Tuple[List[PointOfSale], int]:
    '''
        Retrieves a paginated and filtered list of Points of Sale.
    '''
    query = db.query(PointOfSale).options(
        joinedload(PointOfSale.inventory).joinedload(PointOfSaleInventory.product)
    )
    conditions = [PointOfSale.company_id == filters.company_id]

    if filters.code:
        conditions.append(PointOfSale.code == filters.code)
    if filters.name:
        conditions.append(PointOfSale.name.ilike(f'%{filters.name}%'))
    if filters.external_code:
        conditions.append(PointOfSale.external_code == filters.external_code)
    if filters.country_id:
        conditions.append(PointOfSale.country_id == filters.country_id)
    if filters.city_id:
        conditions.append(PointOfSale.city_id == filters.city_id)
    if filters.zone_id:
        conditions.append(PointOfSale.zone_id == filters.zone_id)
    if filters.pos_type_id:
        conditions.append(PointOfSale.pos_type_id == filters.pos_type_id)
    if filters.channel_id:
        conditions.append(PointOfSale.channel_id == filters.channel_id)
    if filters.status:
        conditions.append(PointOfSale.status == filters.status) # Filter by Enum value

    query = query.filter(and_(*conditions))
    total = query.count()
    items = query.offset(skip).limit(limit).all()

    # Populate dynamic fields for Pydantic schema in each POS inventory
    for pos in items:
        for item in pos.inventory:
            if item.product:
                setattr(item, 'product_sku', item.product.sku)
                setattr(item, 'product_name', item.product.name)

    return items, total

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSale', 'UPDATE')
async def update_pos_service(
    db: Session, pos_id: int, pos_data: PointOfSaleUpdateSchema
) -> Tuple[PointOfSale, Dict[str, Any]]:
    '''
        Updates an existing Point of Sale record.
        Includes validation for status transitions based on business rules.
    '''
    db_pos = get_record(db, PointOfSale, pos_id)
    old_values = sqlalchemy_object_as_dict(db_pos)

    # --- IN_CREATION edit gate (2026-05-28 Binaria) ---
    # Master/contact/location fields may only be edited while the POS is
    # still IN_CREATION. Once it has been ACTIVE or INACTIVE the only
    # change accepted on this endpoint is a status transition between
    # ACTIVE and INACTIVE; any other field change is rejected with 409.
    incoming_fields = pos_data.model_dump(exclude_unset = True)
    non_status_fields = {k: v for k, v in incoming_fields.items() if k != 'status'}
    if db_pos.status != PointOfSaleStatus.IN_CREATION and non_status_fields:
        raise InvalidInputError(
            detail = (
                f'POS {db_pos.code} can only have its master fields edited while '
                f'in IN_CREATION. Current status: {db_pos.status.value}. '
                f'Once the POS is ACTIVE/INACTIVE only the status field can be '
                f'updated via this endpoint.'
            )
        )

    # --- Status Transition Validation ---
    if pos_data.status is not None:
        new_status = pos_data.status
        current_status = db_pos.status

        # Rule: A POS can pass from ACTIVE to INACTIVE, but never return to IN_CREATION.
        error_msg = 'POS cant return to IN_CREATION status once it has been active or inactive.'
        if new_status == PointOfSaleStatus.IN_CREATION and current_status != \
                        PointOfSaleStatus.IN_CREATION:
            raise InvalidInputError(
                detail = error_msg
            )

        # Rule: Transition to ACTIVE requires all mandatory fields to be present.
        if new_status == PointOfSaleStatus.ACTIVE and current_status != PointOfSaleStatus.ACTIVE:
            # Temporarily apply updates from pos_data to a temporary object to
            # check for mandatory fields
            temp_db_pos = PointOfSale(**old_values) # Create a temp object from old values
            # Apply only the fields present in pos_data for the check
            for field, value in pos_data.model_dump(exclude_unset=True).items():
                if hasattr(temp_db_pos, field):
                    setattr(temp_db_pos, field, value)

            # Re-evaluate mandatory fields after applying potential updates using helper
            missing_fields = _validate_mandatory_fields_for_active_status(temp_db_pos)

            if missing_fields:
                raise InvalidInputError(
                    detail = f'Cannot set status to ACTIVE. Missing mandatory fields: {
                        ', '.join(missing_fields)}.'
                )

    db_pos = update_record(db, db_pos, pos_data)
    db.commit()
    db.refresh(db_pos)
    return db_pos, {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_pos)
    }

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSale', 'DELETE')
async def delete_pos_service(
    db: Session, pos_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a Point of Sale.
    '''
    db_pos = get_record(db, PointOfSale, pos_id)
    old_values = sqlalchemy_object_as_dict(db_pos)

    # 1. Cleanup Dependencies. After the planning refactor it is the planned
    # points (route stops) that hold the FK to POS with ON DELETE RESTRICT,
    # so we have to remove them first. Their cascade chain wipes any
    # attendances pointing to those points.
    db.query(PlannedPoint).filter(PlannedPoint.point_of_sale_id == pos_id).delete(
        synchronize_session = False
    )
    db.flush()

    # 2. Delete POS
    delete_record(
        db = db,
        model = PointOfSale,
        record_id = pos_id
    )
    db.commit()
    return pos_id, {'old_values': old_values, 'new_values': None}

# --- POS BULK HELPERS ---

# 2026-05-31 (Binaria): sentinel string values produced upstream by the
# shared generic_bulk_processor when a CSV cell is empty. Pandas converts
# blanks to NaN, FastAPI's JSON encoder normalizes them to None, then the
# bulk processor calls str(None) -> "None" before handing the row to
# Pydantic. The literal "None" / "nan" / "NaN" strings end up persisted
# in VARCHAR columns and break subsequent dedup checks against truly
# empty values. We treat them as empty here.
_EMPTY_STR_SENTINELS = frozenset(('none', 'nan', 'null', ''))


def _coerce_blank(value: Any) -> Any:
    '''
        Returns None when `value` is a sentinel string produced by the
        upstream bulk processor; otherwise returns the value as-is.
    '''
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in _EMPTY_STR_SENTINELS:
        return None
    return value


async def _insert_pos_bulk_data(
    db: Session,
    processed_data: List[PointOfSaleBulkCreateSchema],
    file_name: str, # pylint: disable=unused-argument
    auth_token: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Handles insertion of POS records in bulk. Existing combinations
        of (company_id, code) or (company_id, external_code) are skipped
        and reported back so the frontend can show the user exactly which
        rows did not land.
    '''
    pos_created = 0
    skipped_details: List[Dict[str, Any]] = []
    if not processed_data:
        return {
            'message': 'No valid POS data.',
            'created_records': 0,
            'skipped_records': 0,
            'skipped_details': [],
        }

    for item in processed_data:
        try:
            # Normalize the empty sentinels BEFORE running the dedup
            # query so we don't compare 'None' (the literal string) to
            # legacy rows that also stored 'None'. The Pydantic model is
            # frozen by default; we work off the model_dump copy.
            row_data = item.model_dump()
            row_data['code'] = _coerce_blank(row_data.get('code'))
            row_data['external_code'] = _coerce_blank(row_data.get('external_code'))

            # Check for conflict using the unique constraints:
            # (company_id, code) and (company_id, external_code).
            code_conflict = db.query(PointOfSale).filter_by(
                company_id = item.company_id,
                code = row_data['code']
            ).first() if row_data['code'] else None

            external_code_conflict = None
            if row_data['external_code']:
                external_code_conflict = db.query(PointOfSale).filter_by(
                    company_id = item.company_id,
                    external_code = row_data['external_code']
                ).first()

            if code_conflict or external_code_conflict:
                # Not an error: dedup by (company_id, code|external_code)
                # is part of the idempotent contract. Log at INFO and
                # record the row in the response so the frontend can show
                # the user exactly what was skipped and why.
                #
                # The matched record's ID and stored code are surfaced so
                # the caller can pinpoint the existing row in DB even when
                # MySQL collation hides case differences (utf8mb4_*_ci
                # treats 'cod08' and 'COD08' as equal).
                matched = code_conflict or external_code_conflict
                reason = (
                    'code already exists for this company'
                    if code_conflict
                    else 'external_code already exists for this company'
                )
                info_msg = (
                    f'POS skipped for company {item.company_id}: '
                    f'code={item.code!r}, external_code={item.external_code!r}. '
                    f'Reason: {reason}. '
                    f'Existing record: id={matched.id}, code={matched.code!r}, '
                    f'external_code={matched.external_code!r}.'
                )
                logger.info(info_msg)
                skipped_details.append({
                    'company_id': item.company_id,
                    'code': item.code,
                    'external_code': item.external_code,
                    'reason': reason,
                    'existing_id': matched.id,
                    'existing_code': matched.code,
                    'existing_external_code': matched.external_code,
                })
                continue

            with db.begin_nested():
                # Use the normalized row_data so blanks land in DB as
                # actual NULL instead of the literal 'None' string.
                db.add(PointOfSale(**row_data))
                db.flush()
                pos_created += 1

        except (IntegrityError, SQLAlchemyError) as e:
            error_msg = f'Error inserting POS Code: {item.code} or Name: {item.name}: {e}'
            logger.error(error_msg, exc_info = True)
            skipped_details.append({
                'company_id': item.company_id,
                'code': item.code,
                'external_code': item.external_code,
                'reason': 'database error during insert',
            })
            continue

    return {
        'message': 'Bulk POS completed.',
        'created_records': pos_created,
        'skipped_records': len(skipped_details),
        'skipped_details': skipped_details,
    }

@handle_service_errors('TRADE')
async def bulk_create_points_of_sale_service(
    db: Session, file_name: str, delimiter: str, auth_token: str
) -> Dict[str, Any]:
    '''
        Service wrapper for POS bulk upload.
    '''
    return await perform_bulk_upload(
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        bulk_schema = PointOfSaleBulkCreateSchema,
        processor_func = generic_bulk_processor,
        inserter_func =_insert_pos_bulk_data,
        delimiter = delimiter
    )

# --- INVENTORY SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSaleInventory', 'CREATE')
async def create_inventory_item_service(
    db: Session, pos_id: int, inventory_data: POSInventoryCreateSchema
) -> Tuple[PointOfSaleInventory, Dict[str, Any]]:
    '''
        Adds a new inventory item to a POS.
    '''
    message = f'Adding inventory to POS ID: {pos_id}'
    logger.info(message)

    # 1. Validation
    db_pos = get_record(db, PointOfSale, pos_id)
    product_id = get_product_id_by_sku(db, db_pos.company_id, inventory_data.product_sku)

    # Verify Assignment
    if not db.query(ProductAssignmentPOS).filter_by(
        point_of_sale_id = pos_id,
        product_id = product_id,
        status = 'ACTIVE'
    ).first():
        raise InvalidInputError(detail='SKU not assigned to this POS.')

    # Verify Duplicate
    if db.query(PointOfSaleInventory).filter_by(
        point_of_sale_id = pos_id,
        product_id = product_id,
        batch_number = inventory_data.batch_number,
        location = inventory_data.location
    ).first():
        raise RegisterAlreadyExistsError(detail='Inventory item already exists.')

    # 2. Create
    data = inventory_data.model_dump(exclude={'product_sku'})
    db_inv = PointOfSaleInventory(
        point_of_sale_id = pos_id,
        product_id = product_id,
        **data
    )
    db.add(db_inv)
    db.commit()
    db.refresh(db_inv)

    # Populate dynamic fields for schema
    if db_inv.product:
        setattr(db_inv, 'product_sku', db_inv.product.sku)
        setattr(db_inv, 'product_name', db_inv.product.name)

    return db_inv, {'new_values': sqlalchemy_object_as_dict(db_inv)}

@handle_service_errors('TRADE')
async def get_inventory_for_pos_service(
    db: Session, pos_id: int
) -> Tuple[List[PointOfSaleInventory], int]:
    '''
        Retrieves all inventory items for a POS.
    '''
    get_record(db, PointOfSale, pos_id) # Validates POS existence
    query = db.query(PointOfSaleInventory).filter_by(point_of_sale_id=pos_id)\
        .options(joinedload(PointOfSaleInventory.product))
    items = query.all()

    for item in items:
        if item.product:
            setattr(item, 'product_sku', item.product.sku)
            setattr(item, 'product_name', item.product.name)

    return items, query.count()

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSaleInventory', 'UPDATE')
async def update_inventory_item_service(
    db: Session, inventory_id: int, update_data: POSInventoryUpdateSchema
) -> Tuple[PointOfSaleInventory, Dict[str, Any]]:
    '''
        Updates an inventory item.
    '''
    db_item = get_record(db, PointOfSaleInventory, inventory_id)
    old_values = sqlalchemy_object_as_dict(db_item)

    data = update_data.model_dump(exclude_unset=True)
    if 'product_sku' in data:
        sku = data.pop('product_sku')
        data['product_id'] = get_product_id_by_sku(db, db_item.company_id, sku)

    for key, val in data.items():
        setattr(db_item, key, val)

    db.commit()
    db.refresh(db_item)

    # Populate dynamic fields for schema
    if db_item.product:
        setattr(db_item, 'product_sku', db_item.product.sku)
        setattr(db_item, 'product_name', db_item.product.name)

    return db_item, {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_item)
    }

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSaleInventory', 'DELETE')
async def delete_inventory_item_service(
    db: Session, inventory_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes an inventory item.
    '''
    db_item = get_record(db, PointOfSaleInventory, inventory_id)
    old_values = sqlalchemy_object_as_dict(db_item)
    delete_record(
        db = db,
        model = PointOfSaleInventory,
        record_id = inventory_id
    )
    db.commit()
    return inventory_id, {'old_values': old_values, 'new_values': None}

# --- INVENTORY BULK HELPERS ---

async def _insert_pos_inventory_bulk_data(
    db: Session,
    processed_data: List[POSInventoryBulkCreateSchema],
    file_name: str, # pylint: disable=unused-argument
    auth_token: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Handles transactional insertion of POS Inventory in bulk.
    '''
    if not processed_data:
        return {'message': 'No valid data.', 'created_records': 0}

    company_id = processed_data[0].company_id

    # Pre-fetch maps to avoid queries inside loop
    pos_map = {
        p.external_code: p.id for p in db.query(PointOfSale).filter(
            PointOfSale.company_id == company_id,
            PointOfSale.external_code.in_({i.pos_external_code for i in processed_data})
        ).all()
    }
    prod_map = {
        p.sku: p.id for p in db.query(Product).filter(
            Product.company_id == company_id,
            Product.sku.in_({i.product_sku for i in processed_data})
        ).all()
    }

    created = 0
    for item in processed_data:
        pos_id = pos_map.get(item.pos_external_code)
        pid = prod_map.get(item.product_sku)

        if not pos_id or not pid:
            continue

        try:
            # Check duplicate
            if db.query(PointOfSaleInventory).filter_by(
                point_of_sale_id=pos_id, product_id=pid,
                batch_number=item.batch_number, location=item.location
            ).first():
                continue

            with db.begin_nested():
                data = item.model_dump(exclude={'product_sku', 'pos_external_code'})
                data['expiration_date'] = datetime.strptime(data['expiration_date'], '%Y-%m-%d')
                db.add(PointOfSaleInventory(
                    point_of_sale_id=pos_id, product_id=pid, **data
                ))
                db.flush()
                created += 1

        except (ValueError, SQLAlchemyError) as e:
            error_msg = f'Bulk insert error: {e}'
            logger.error(error_msg, exc_info = True)

    return {'message': 'POS Inventory bulk completed.', 'created_records': created}

@handle_service_errors('TRADE')
async def bulk_create_pos_inventory_service(
    db: Session, file_name: str, delimiter: str, auth_token: str
) -> Dict[str, Any]:
    ''' Service wrapper for POS Inventory bulk upload. '''
    return await perform_bulk_upload(
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        bulk_schema = POSInventoryBulkCreateSchema,
        processor_func = generic_bulk_processor,
        inserter_func = _insert_pos_inventory_bulk_data,
        delimiter = delimiter
    )
