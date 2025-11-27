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
    PointOfSaleInventory
)
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

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSale', 'CREATE')
async def create_pos_with_inventory_service(
    db: Session,
    pos_data: PointOfSaleCreateSchema
) -> Tuple[PointOfSale, Dict[str, Any]]:
    '''
        Creates a new POS and its nested initial inventory records.
    '''
    message = f'Creating POS: {pos_data.name} for company: {pos_data.company_id}'
    logger.info(message)

    # 1. Validation
    if pos_data.external_code:
        if db.query(PointOfSale).filter(
            PointOfSale.company_id == pos_data.company_id,
            PointOfSale.external_code == pos_data.external_code
        ).first():
            raise RegisterAlreadyExistsError(
                detail = f'POS code {pos_data.external_code} exists.'
            )

    # 2. Create POS
    db_pos = PointOfSale(**pos_data.model_dump(exclude={'initial_inventory'}))
    db.add(db_pos)
    db.flush()

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
    return get_record(
        db, PointOfSale, pos_id,
        eager_load_options = [
            joinedload(PointOfSale.inventory).joinedload(PointOfSaleInventory.product)
        ]
    )

@handle_service_errors('TRADE')
async def get_pos_list_service(
    db: Session, filters: POSFilterSchema, skip: int, limit: int
) -> Tuple[List[PointOfSale], int]:
    '''
        Retrieves a paginated and filtered list of Points of Sale.
    '''
    query = db.query(PointOfSale).options(joinedload(PointOfSale.inventory))
    conditions = [PointOfSale.company_id == filters.company_id]

    if filters.name:
        conditions.append(PointOfSale.name.ilike(f'%{filters.name}%'))
    if filters.external_code:
        conditions.append(PointOfSale.external_code == filters.external_code)
    if filters.is_active is not None:
        conditions.append(PointOfSale.is_active == filters.is_active)

    query = query.filter(and_(*conditions))
    return query.offset(skip).limit(limit).all(), query.count()

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSale', 'UPDATE')
async def update_pos_service(
    db: Session, pos_id: int, pos_data: PointOfSaleUpdateSchema
) -> Tuple[PointOfSale, Dict[str, Any]]:
    '''
        Updates an existing Point of Sale record.
    '''
    db_pos = get_record(db, PointOfSale, pos_id)
    old_values = sqlalchemy_object_as_dict(db_pos)
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
    delete_record(
        db = db,
        model = PointOfSale,
        record_id = pos_id
    )
    db.commit()
    return pos_id, {'old_values': old_values, 'new_values': None}

# --- POS BULK HELPERS ---

async def _insert_pos_bulk_data(
    db: Session,
    processed_data: List[PointOfSaleBulkCreateSchema],
    file_name: str, # pylint: disable=unused-argument
    auth_token: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Handles insertion of POS records in bulk.
    '''
    pos_created = 0
    if not processed_data:
        return {'message': 'No valid POS data.', 'created_records': 0}

    for item in processed_data:
        try:
            # Check for conflict (Name OR External Code)
            conflict = db.query(PointOfSale).filter(
                PointOfSale.company_id == item.company_id,
                (PointOfSale.name == item.name) |
                (PointOfSale.external_code == item.external_code
                 if item.external_code else False)
            ).first()

            if conflict:
                error_msg = f'POS conflict: {item.name}/{item.external_code}. Skipping.'
                logger.warning(error_msg)
                continue

            with db.begin_nested():
                db.add(PointOfSale(**item.model_dump()))
                db.flush()
                pos_created += 1

        except (IntegrityError, SQLAlchemyError) as e:
            error_msg = f'Error inserting POS {item.name}: {e}'
            logger.error(error_msg, exc_info = True)
            continue

    return {'message': 'Bulk POS completed.', 'created_records': pos_created}

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
    return query.all(), query.count()

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
