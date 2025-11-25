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

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSale', 'CREATE')
async def create_pos_with_inventory_service(
    db: Session,
    pos_data: PointOfSaleCreateSchema
) -> Tuple[PointOfSale, Dict[str, Any]]:
    '''
        Creates a new Point of Sale (POS) and its nested initial inventory records
        in a transactional block.
    '''
    message = f'Attempting to create POS with name: {pos_data.name} for company ID: {
        pos_data.company_id}'
    logger.info(message)

    if pos_data.external_code:
        existing_pos = db.query(PointOfSale).filter(
            PointOfSale.company_id == pos_data.company_id,
            PointOfSale.external_code == pos_data.external_code
        ).first()

        if existing_pos:
            error_msg = f'Point of Sale with external code {pos_data.external_code
                } already exists for company {pos_data.company_id}.'
            logger.error(error_msg)
            raise RegisterAlreadyExistsError(detail = error_msg)

    pos_dict = pos_data.model_dump(exclude = {'initial_inventory'})
    db_pos = PointOfSale(**pos_dict)
    db.add(db_pos)
    db.flush()

    if pos_data.initial_inventory:
        message = f'Processing initial inventory for POS ID: {db_pos.id} and company ID: {
            pos_data.company_id}'
        logger.info(message)

        for inventory_item in pos_data.initial_inventory:

            inventory_data = inventory_item.model_dump()

            sku = inventory_data.pop('product_sku')

            product_id = get_product_id_by_sku(db, pos_data.company_id, sku)

            inventory_data['product_id'] = product_id
            inventory_data['point_of_sale_id'] = db_pos.id
            inventory_data['company_id'] = pos_data.company_id

            db_inventory = PointOfSaleInventory(**inventory_data)
            db.add(db_inventory)

    db.commit()
    db.refresh(db_pos)

    return db_pos, {'new_values': sqlalchemy_object_as_dict(db_pos)}

@handle_service_errors('TRADE')
async def get_pos_by_id_service(
    db: Session,
    pos_id: int
) -> PointOfSale:
    '''
        Retrieves a PointOfSale record by its unique ID,
        including its nested inventory details.
    '''
    message = f'Attempting to retrieve Point of Sale with ID: {pos_id}'
    logger.info(message)

    eager_load_options = [
        joinedload(PointOfSale.inventory).joinedload(PointOfSaleInventory.product)
    ]

    db_pos = get_record(
        db = db,
        model = PointOfSale,
        record_id = pos_id,
        eager_load_options = eager_load_options
    )
    return db_pos

@handle_service_errors('TRADE')
async def get_pos_list_service(
    db: Session,
    filters: POSFilterSchema,
    skip: int,
    limit: int
) -> Tuple[List[PointOfSale], int]:
    '''
        Retrieves a paginated and filtered list of Points of Sale.
    '''
    message = f'Attempting to retrieve POS list for company {filters.company_id}'
    logger.info(message)

    query = db.query(PointOfSale).options(joinedload(PointOfSale.inventory))

    conditions = [PointOfSale.company_id == filters.company_id]

    if filters.name:
        conditions.append(PointOfSale.name.ilike(f'%{filters.name}%'))
    if filters.external_code:
        conditions.append(PointOfSale.external_code == filters.external_code)
    if filters.is_active is not None:
        conditions.append(PointOfSale.is_active == filters.is_active)

    query = query.filter(and_(*conditions))

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return items, total

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSale', 'UPDATE')
async def update_pos_service(
    db: Session,
    pos_id: int,
    pos_data: PointOfSaleUpdateSchema
) -> Tuple[PointOfSale, Dict[str, Any]]:
    '''
        Updates an existing Point of Sale record.
        NOTE: This does not update nested inventory, only POS parent fields.
    '''
    message = f'Attempting to update POS ID: {pos_id}'
    logger.info(message)

    db_pos = get_record(db, PointOfSale, pos_id)
    old_values = sqlalchemy_object_as_dict(db_pos)

    db_pos = update_record(db, db_pos, pos_data)

    db.commit()
    db.refresh(db_pos)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_pos)
    }

    return db_pos, auditable_data

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSale', 'DELETE')
async def delete_pos_service(
    db: Session,
    pos_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a Point of Sale and its cascaded inventory.
    '''
    message = f'Attempting to delete POS ID: {pos_id}'
    logger.info(message)

    db_pos = get_record(db, PointOfSale, pos_id)
    old_values = sqlalchemy_object_as_dict(db_pos)

    delete_record(
        db = db,
        model = PointOfSale,
        record_id = pos_id
    )

    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return pos_id, auditable_data

# --- POS BULK HELPERS ---

async def _insert_pos_bulk_data(
    db: Session,
    processed_data: List[PointOfSaleBulkCreateSchema],
    file_name: str, # pylint: disable=unused-argument
    auth_token: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Handles the insertion of Point of Sale records in bulk.
        Uses row-level transactions to skip duplicates and process valid records.
    '''
    pos_created = 0

    if not processed_data:
        return {'message': 'No valid POS data to insert.', 'created_records': 0}

    for item in processed_data:
        try:
            existing_pos_query = db.query(PointOfSale).filter(
                PointOfSale.company_id == item.company_id,
                (PointOfSale.name == item.name) |
                (PointOfSale.external_code == item.external_code if item.external_code else False)
            )

            if existing_pos_query.first():
                error_msg = f'POS conflict detected (name: {item.name}, code: {
                    item.external_code}) for company {item.company_id}. Skipping record.'
                logger.warning(error_msg)
                continue

            with db.begin_nested():
                new_pos = PointOfSale(**item.model_dump())
                db.add(new_pos)
                db.flush()
                pos_created += 1

        except IntegrityError as e:
            error_msg = f'POS creation failed (Integrity): {e}'
            logger.warning(error_msg)
            continue
        except (SQLAlchemyError, InvalidInputError) as e:
            error_msg = f'Unexpected error during POS bulk insertion for {item.name}: {e}'
            logger.error(error_msg, exc_info = True)
            continue

    return {
        'message': 'Point of Sale bulk insertion completed.',
        'created_records': pos_created
    }

@handle_service_errors('TRADE')
async def bulk_create_points_of_sale_service(
    db: Session,
    file_name: str,
    delimiter: str,
    auth_token: str,
) -> Dict[str, Any]:
    '''
        Service wrapper function to handle the bulk upload of Points of Sale.
    '''
    result = await perform_bulk_upload(
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        bulk_schema = PointOfSaleBulkCreateSchema,
        processor_func = generic_bulk_processor,
        inserter_func = _insert_pos_bulk_data,
        delimiter = delimiter
    )

    return result

# --- INVENTORY ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSaleInventory', 'CREATE')
async def create_inventory_item_service(
    db: Session,
    pos_id: int,
    inventory_data: POSInventoryCreateSchema
) -> Tuple[PointOfSaleInventory, Dict[str, Any]]:
    '''
        Adds a new inventory item (SKU) to an existing Point of Sale.
    '''
    message = f'Attempting to add inventory to POS ID: {pos_id}'
    logger.info(message)

    db_pos = get_record(db, PointOfSale, pos_id)
    company_id = db_pos.company_id
    sku = inventory_data.product_sku

    product_id = get_product_id_by_sku(db, company_id, sku)

    assignment = db.query(ProductAssignmentPOS).filter(
        ProductAssignmentPOS.point_of_sale_id == pos_id,
        ProductAssignmentPOS.product_id == product_id,
        ProductAssignmentPOS.status == 'ACTIVE'
    ).first()

    if not assignment:
        error_msg = f'Validation failed: Product SKU {sku} (ID: {
                    product_id}) is not assigned to POS ID: {pos_id}.'
        logger.warning(error_msg)
        raise InvalidInputError(
            detail = f'El producto con SKU {sku} no está asignado (activo) a este Punto de Venta.'
        )

    existing_inventory = db.query(PointOfSaleInventory).filter(
        PointOfSaleInventory.point_of_sale_id == pos_id,
        PointOfSaleInventory.product_id == product_id,
        PointOfSaleInventory.batch_number == inventory_data.batch_number,
        PointOfSaleInventory.location == inventory_data.location
    ).first()

    if existing_inventory:
        error_msg = f'An inventory item with this SKU ({sku}), Batch ({
                inventory_data.batch_number}) and Location ({inventory_data.location
                }) already exists for this POS.'
        logger.error(error_msg)
        raise RegisterAlreadyExistsError(detail = error_msg)

    # 5. Crear el registro
    inventory_dict = inventory_data.model_dump()
    inventory_dict.pop('product_sku')

    inventory_dict['product_id'] = product_id
    inventory_dict['point_of_sale_id'] = pos_id

    db_inventory = PointOfSaleInventory(**inventory_dict)
    db.add(db_inventory)
    db.commit()
    db.refresh(db_inventory)

    return db_inventory, {'new_values': sqlalchemy_object_as_dict(db_inventory)}

@handle_service_errors('TRADE')
async def get_inventory_for_pos_service(
    db: Session,
    pos_id: int
) -> Tuple[List[PointOfSaleInventory], int]:
    '''
        Retrieves all inventory items for a specific Point of Sale.
    '''
    message = f'Attempting to retrieve inventory for POS ID: {pos_id}'
    logger.info(message)

    # 1. Validar que el POS existe
    _ = get_record(db, PointOfSale, pos_id)

    # 2. Consultar inventario
    query = db.query(PointOfSaleInventory).filter(
        PointOfSaleInventory.point_of_sale_id == pos_id
    ).options(
        joinedload(PointOfSaleInventory.product)
    )

    total = query.count()
    items = query.all()

    return items, total

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSaleInventory', 'UPDATE')
async def update_inventory_item_service(
    db: Session,
    inventory_id: int,
    update_data: POSInventoryUpdateSchema
) -> Tuple[PointOfSaleInventory, Dict[str, Any]]:
    '''
        Updates an existing inventory item (e.g., quantity, batch).
    '''
    message = f'Attempting to update inventory item ID: {inventory_id}'
    logger.info(message)

    db_item = get_record(db, PointOfSaleInventory, inventory_id)
    old_values = sqlalchemy_object_as_dict(db_item)

    update_dict = update_data.model_dump(exclude_unset = True)

    if 'product_sku' in update_dict:
        sku = update_dict.pop('product_sku')
        product_id = get_product_id_by_sku(db, db_item.company_id, sku)
        update_dict['product_id'] = product_id

    for key, value in update_dict.items():
        if hasattr(db_item, key):
            setattr(db_item, key, value)
        else:
            error_message = f'Skipping update for unknown attribute: {key}'
            logger.warning(error_message)

    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_item)
    }
    return db_item, auditable_data

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSaleInventory', 'DELETE')
async def delete_inventory_item_service(
    db: Session,
    inventory_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a specific inventory item from a POS.
    '''
    message = f'Attempting to delete inventory item ID: {inventory_id}'
    logger.info(message)
    db_item = get_record(db, PointOfSaleInventory, inventory_id)
    old_values = sqlalchemy_object_as_dict(db_item)

    delete_record(
        db = db,
        model = PointOfSaleInventory,
        record_id = inventory_id
    )

    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return inventory_id, auditable_data

# --- INVENTORY BULK HELPERS ---

# pylint: disable=too-many-locals, duplicate-code
async def _insert_pos_inventory_bulk_data(
    db: Session,
    processed_data: List[POSInventoryBulkCreateSchema],
    file_name: str, # pylint: disable=unused-argument
    auth_token: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Handles the transactional insertion of POS Inventory records in bulk.
        Includes Pre-Check to avoid duplicate entries.
    '''
    inventory_created = 0

    if not processed_data:
        return {'message': 'No valid inventory data to insert.', 'created_records': 0}

    company_id = processed_data[0].company_id

    # 1. Pre-fetch and map POS IDs
    pos_codes = {item.pos_external_code for item in processed_data}
    pos_to_id_map = {
        pos.external_code: pos.id
        for pos in db.query(PointOfSale).filter(
            PointOfSale.company_id == company_id,
            PointOfSale.external_code.in_(pos_codes)
        ).all()
    }

    # 2. Pre-fetch and map Product IDs
    skus = {item.product_sku for item in processed_data}
    sku_to_id_map = {
        product.sku: product.id
        for product in db.query(Product).filter(
            Product.company_id == company_id,
            Product.sku.in_(skus)
        ).all()
    }

    for item in processed_data:
        pos_id = pos_to_id_map.get(item.pos_external_code)
        product_id = sku_to_id_map.get(item.product_sku)

        if not pos_id:
            error_msg = f'POS external code {item.pos_external_code} not found. Skipping.'
            logger.warning(error_msg)
            continue

        if not product_id:
            error_msg = f'Product SKU {item.product_sku} not found. Skipping.'
            logger.warning(error_msg)
            continue

        try:
            existing_inv = db.query(PointOfSaleInventory).filter(
                PointOfSaleInventory.point_of_sale_id == pos_id,
                PointOfSaleInventory.product_id == product_id,
                PointOfSaleInventory.batch_number == item.batch_number,
                PointOfSaleInventory.location == item.location
            ).first()

            if existing_inv:
                error_msg = f'Inventory conflict: SKU {item.product_sku}, Batch {item.batch_number
                        } already exists at POS {item.pos_external_code}. Skipping.'
                logger.warning(error_msg)
                continue

            with db.begin_nested():
                record_dict = item.model_dump(exclude = {'product_sku', 'pos_external_code'})

                record_dict['expiration_date'] = datetime.strptime(
                    record_dict['expiration_date'], '%Y-%m-%d'
                )

                record_dict['point_of_sale_id'] = pos_id
                record_dict['product_id'] = product_id

                new_inv = PointOfSaleInventory(**record_dict)
                db.add(new_inv)
                db.flush()
                inventory_created += 1

        except ValueError as e:
            error_msg = f'Date format error for {item.product_sku}. Error: {e}. Skipping.'
            logger.error(error_msg, exc_info = True)
            continue
        except (SQLAlchemyError, InvalidInputError) as e:
            error_msg = f'Unexpected error inserting inventory: {e}'
            logger.error(error_msg, exc_info = True)
            continue

    return {
        'message': 'POS Inventory bulk insertion completed.',
        'created_records': inventory_created
    }

@handle_service_errors('TRADE')
async def bulk_create_pos_inventory_service(
    db: Session,
    file_name: str,
    delimiter: str,
    auth_token: str,
) -> Dict[str, Any]:
    '''
        Service wrapper function to handle the bulk upload of POS Inventory.
    '''
    message = 'Starting POS Inventory bulk upload process.'
    logger.info(message)

    result = await perform_bulk_upload(
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        bulk_schema = POSInventoryBulkCreateSchema,
        processor_func = generic_bulk_processor,
        inserter_func = _insert_pos_inventory_bulk_data,
        delimiter = delimiter
    )

    return result
