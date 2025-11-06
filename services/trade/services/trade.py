'''
    Business logic services for the Trade Microservice, including
    atomic SKU generation and transactional nested creation.
'''
import os
from typing import Any, Dict, List, Optional, Tuple, Type
from fastapi import UploadFile
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload, DeclarativeBase
from services.crud import (
    create_record,
    delete_record,
    get_record,
    update_record
)
from services.exceptions import (
    RegisterAlreadyExistsError,
    RegisterNotFoundError,
)
from services.logger_config import custom_logger as logger
from services.utils import (
    _handle_files_service,
    get_current_time_gmt,
    handle_service_errors,
    audit_event,
    sqlalchemy_object_as_dict
)
from models.trade import (
    PointOfSale,
    PointOfSaleInventory,
    Product,
    ProductAssignmentPOS,
    SKUEquivalency,
    SKUSequencer
)
from schemas.trade import (
    POSFilterSchema,
    PointOfSaleUpdateSchema,
    ProductAssignmentPOSCreateSchema,
    ProductAssignmentPOSFilterSchema,
    ProductAssignmentPOSUpdateSchema,
    ProductCreateSchema,
    PointOfSaleCreateSchema,
    ProductFilterSchema,
    ProductUpdateSchema,
    SKUEquivalencyCreateSchema,
    SKUEquivalencyUpdateSchema,
)

async def _prepare_file_to_upload(
    file: Optional[UploadFile],
    dynamic_path: str,
    auth_token: str,
    prefix: str
) -> str:
    '''
        Helper to prepare to upload file across FILES microservice
    '''
    _, file_extension = os.path.splitext(file.filename)
    current_time = get_current_time_gmt()
    timestamp_part = current_time.strftime('%Y%m%d-%H-%M-%S')
    new_file_name = f'{prefix}_{timestamp_part}{file_extension}'
    file.filename = new_file_name

    return await _handle_files_service(
        action = 'create',
        file_name = '',
        auth_token = auth_token,
        uploaded_file = file,
        dynamic_path = dynamic_path
    )

async def _create_bulk_items_from_skus(
    db: Session,
    attendance_id: int,
    company_id: int,
    items_list: List[BaseModel],
    model_class: Type[DeclarativeBase]
) -> List[DeclarativeBase]:
    '''
        Generic helper to create multiple inventory/reception items.
        Handles SKU-to-ID translation and bulk commit.
    '''
    created_items = []
    for item in items_list:
        # 1. Get product_id
        product_id = _get_product_id_by_sku(
            db, company_id, item.product_sku
        )

        # 2. Get all other fields from the item schema
        # (e.g., quantity, batch_number, expiration_date, comments)
        item_data = item.model_dump(exclude={'product_sku'})

        # 3. Create the model instance
        db_item = model_class(
            attendance_id = attendance_id,
            product_id = product_id,
            **item_data  # Desempaqueta los campos restantes
        )
        db.add(db_item)
        created_items.append(db_item)

    # Commit all items at once
    db.commit()
    for item in created_items:
        db.refresh(item)

    return created_items

def _get_segment_key(
    category_1: str,
    category_2: str,
    category_3: str,
    category_4: str
) -> str:
    '''
        Constructs the non-sequential segment key (XXX.YYY.ZZZ.WWW)
        for the SKU Sequencer table.
    '''
    # The key combines the four categories separated by dots.
    return f'{category_1}.{category_2}.{category_3}.{category_4}'

def _format_sequence_number(sequence: int) -> str:
    '''
        Formats the sequence number (SEC) to a 3-digit string (e.g., 1 -> '001').
    '''
    return f'{sequence:03d}'

def _get_product_id_by_sku(
    db: Session,
    company_id: int,
    sku: str
) -> int:
    '''
        Searches for the internal product ID (product_id) using its SKU.
    '''
    # 'Search for the product'
    product = (
        db.query(Product)
        .filter(
            Product.company_id == company_id,
            Product.sku == sku
        )
        .first()
    )

    if not product:
        error_msg = f'Product with SKU {sku} not found for company {company_id}.'
        logger.error(error_msg)
        raise RegisterNotFoundError(detail = error_msg)

    # 'Return the ID'
    return product.id

# pylint: disable=too-many-arguments, too-many-positional-arguments
def _generate_next_sku_sequence(
    db: Session,
    company_id: int,
    category_1_code: str,
    category_2_code: str,
    category_3_code: str,
    category_4_code: str
) -> str:
    '''
        Atomically gets the next sequence number (SEC) for the given category combination
        and constructs the full SKU.

        NOTE: This function MUST be called within an active transactional context 
        (e.g., inside a db.begin_nested() block in the caller).
    '''
    segment_key = _get_segment_key(
        category_1_code, category_2_code, category_3_code, category_4_code
    )
    message = f'Attempting to generate atomic SKU sequence for company {
        company_id} with segment key {segment_key}'
    logger.debug(message)

    # 1. Find or create the sequencer record for this segment and company
    # The .with_for_update() ensures an atomic lock on the row.
    sequencer = db.query(SKUSequencer).filter(
        SKUSequencer.company_id == company_id,
        SKUSequencer.segment_key == segment_key
    ).with_for_update().first()

    if sequencer:
        # 2. If found, increment the sequence number
        sequencer.last_sequence_number += 1
        db.add(sequencer)
        next_sequence = sequencer.last_sequence_number
    else:
        # 3. If not found, create a new sequencer record starting at 1
        next_sequence = 1
        new_sequencer = SKUSequencer(
            company_id = company_id,
            segment_key = segment_key,
            last_sequence_number = next_sequence
        )
        db.add(new_sequencer)

    db.flush()

    # 4. Construct the final SKU
    formatted_sec = _format_sequence_number(next_sequence)
    final_sku = f'{segment_key}.{formatted_sec}'
    message = f'Successfully generated SKU: {final_sku} for segment key: {segment_key}'
    logger.info(message)

    return final_sku

@handle_service_errors('TRADE')
@audit_event('TRADE', 'Product', 'CREATE')
async def create_product_service(
    db: Session,
    product_data: ProductCreateSchema
) -> Product:
    '''
        Creates a new product record, atomically generating its unique SKU.
    '''

    message = f'Attempting to create product {product_data.name} for company ID: {
        product_data.company_id}'
    logger.info(message)

    # 1. Check for name conflict using explicit query, matching planning service pattern
    existing_product = db.query(Product).filter(
        Product.company_id == product_data.company_id,
        Product.name == product_data.name
    ).first()

    if existing_product:
        error_msg = f'Product with name {product_data.name} already exists for this company.'
        logger.error(error_msg)
        raise RegisterAlreadyExistsError(detail = error_msg)

    # 2. Use nested transaction to encapsulate the atomic SKU sequence lock
    with db.begin_nested():
        # 3. Generate the unique SKU
        final_sku = _generate_next_sku_sequence(
            db,
            product_data.company_id,
            product_data.category_1_code,
            product_data.category_2_code,
            product_data.category_3_code,
            product_data.category_4_code
        )

        # 4. Prepare data and create the product record
        product_dict = product_data.model_dump()
        product_dict['sku'] = final_sku

        # Matching create_planning_with_details pattern: db_planning = Planning(**planning_dict)
        db_product = Product(**product_dict)
        db.add(db_product)

    # 5. Commit and refresh, matching create_planning_with_details flow
    db.commit()
    db.refresh(db_product)

    return db_product

@handle_service_errors('TRADE')
@audit_event('TRADE', 'PointOfSale', 'CREATE')
async def create_pos_with_inventory_service(
    db: Session,
    pos_data: PointOfSaleCreateSchema
) -> PointOfSale:
    '''
        Creates a new Point of Sale (POS) and its nested initial inventory records
        in a transactional block.
    '''
    message = f'Attempting to create POS with name: {pos_data.name} for company ID: {
        pos_data.company_id}'
    logger.info(message)

    # 1. Check for external_code conflict using explicit query
    if pos_data.external_code:
        existing_pos = db.query(PointOfSale).filter(
            PointOfSale.company_id == pos_data.company_id,
            PointOfSale.external_code == pos_data.external_code
        ).first()

        if existing_pos:
            error_msg = f'''Point of Sale with external code {pos_data.external_code}
                    already exists for company {pos_data.company_id}.'''
            logger.error(error_msg)
            raise RegisterAlreadyExistsError(detail = error_msg)

    # 2. Create the main PointOfSale record.
    pos_dict = pos_data.model_dump(exclude = {'initial_inventory'})
    db_pos = PointOfSale(**pos_dict)
    db.add(db_pos)
    db.flush()

    # 3. Iterate through initial inventory details and create nested records.
    if pos_data.initial_inventory:
        message = f'''Processing initial inventory for POS ID: {db_pos.id} and company
                ID: {pos_data.company_id}'''
        logger.info(message)

        for inventory_item in pos_data.initial_inventory:

            # 3a. Convert Pydantic to dictionary
            inventory_data = inventory_item.model_dump()

            # 3b. Extract the SKU and get the ID. pop() removes product_sku
            # from the dictionary so it doesn't cause an error in the model''s constructor.
            sku = inventory_data.pop('product_sku')

            # Translate SKU to product_id
            product_id = _get_product_id_by_sku(db, pos_data.company_id, sku)

            # 3c. Insert the correct product ID into the dictionary
            inventory_data['product_id'] = product_id
            inventory_data['point_of_sale_id'] = db_pos.id
            inventory_data['company_id'] = pos_data.company_id

            # 3d. Create the inventory record directly using the model constructor
            db_inventory = PointOfSaleInventory(**inventory_data)
            db.add(db_inventory)


    # 4. Commit and refresh, matching create_planning_with_details flow
    db.commit()
    db.refresh(db_pos)

    return db_pos

@handle_service_errors('TRADE')
async def get_product_by_id_service(
    db: Session,
    product_id: int
) -> Product:
    '''
        Retrieves a Product record by its unique ID.
    '''
    message = f'Attempting to retrieve product with ID: {product_id}'
    logger.info(message)

    db_product = get_record(
        db = db,
        model = Product,
        record_id = product_id
    )
    return db_product

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

    eager_load_options = [joinedload(PointOfSale.inventory)]

    db_pos = get_record(
        db = db,
        model = PointOfSale,
        record_id = pos_id,
        eager_load_options = eager_load_options
    )
    return db_pos

@handle_service_errors('TRADE')
async def get_products_list_service(
    db: Session,
    filters: ProductFilterSchema,
    skip: int,
    limit: int
) -> Tuple[List[Product], int]:
    '''
        Retrieves a paginated and filtered list of Products.
    '''
    message = f'Attempting to retrieve product list for company {filters.company_id}'
    logger.info(message)

    query = db.query(Product)

    # Mandatory filter
    conditions = [Product.company_id == filters.company_id]

    # Optional filters
    if filters.name:
        conditions.append(Product.name.ilike(f'%{filters.name}%'))
    if filters.sku:
        conditions.append(Product.sku == filters.sku)
    if filters.status:
        conditions.append(Product.status == filters.status)

    query = query.filter(and_(*conditions))

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return items, total

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

    # Mandatory filter
    conditions = [PointOfSale.company_id == filters.company_id]

    # Optional filters
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
@audit_event('TRADE', 'Product', 'UPDATE')
async def update_product_service(
    db: Session,
    product_id: int,
    product_data: ProductUpdateSchema
) -> Tuple[Product, Dict[str, Any]]:
    '''
        Updates an existing Product record.
    '''
    message = f'Attempting to update product ID: {product_id}'
    logger.info(message)

    db_product = get_record(db, Product, product_id)
    old_values = sqlalchemy_object_as_dict(db_product)

    # Use the generic crud.update_record function
    db_product = update_record(db, db_product, product_data)

    db.commit()
    db.refresh(db_product)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_product)
    }

    return db_product, auditable_data

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

    # Use the generic crud.update_record function
    db_pos = update_record(db, db_pos, pos_data)

    db.commit()
    db.refresh(db_pos)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_pos)
    }

    return db_pos, auditable_data

@handle_service_errors('TRADE')
@audit_event('TRADE', 'Product', 'DELETE')
async def delete_product_service(
    db: Session,
    product_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a product record.
    '''
    message = f'Attempting to delete product ID: {product_id}'
    logger.info(message)

    db_product = get_record(db, Product, product_id)
    old_values = sqlalchemy_object_as_dict(db_product)

    # Use the generic crud.delete_record function
    delete_record(
        db = db,
        model = db_product,
        record_id = product_id
    )

    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return product_id, auditable_data

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

    # Use the generic crud.delete_record function
    delete_record(
        db = db,
        model = db_pos,
        record_id = pos_id
    )

    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return pos_id, auditable_data

# --- SKU EQUIVALENCY SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'SKUEquivalency', 'CREATE')
async def create_sku_equivalency_service(
    db: Session,
    equivalency_data: SKUEquivalencyCreateSchema
) -> SKUEquivalency:
    '''
        Creates a new SKU Equivalency mapping.
    '''
    message = f'Attempting to create SKU equivalency for external code: {
            equivalency_data.external_product_code}'
    logger.info(message)

    # 1. Translate SKU to product_id (reusing existing helper)
    product_id = _get_product_id_by_sku(
        db, equivalency_data.company_id, equivalency_data.product_sku
    )

    # 2. Prepare data for create_record (Pydantic object)

    extra_fields = {
        'product_id': product_id
    }

    # We must exclude product_sku as it's not in the ORM model
    exclude_relations = ['product_sku']

    db_equivalency = create_record(
        db,
        SKUEquivalency,
        equivalency_data,
        extra_fields = extra_fields,
        exclude_relations = exclude_relations
    )

    db.commit()
    db.refresh(db_equivalency)
    return db_equivalency

@handle_service_errors('TRADE')
async def get_sku_equivalency_by_id_service(
    db: Session,
    equivalency_id: int
) -> SKUEquivalency:
    '''
        Retrieves a single SKU Equivalency by its ID.
    '''
    message = f'Retrieving SKU Equivalency ID: {equivalency_id}'
    logger.info(message)

    db_equivalency = get_record(db, SKUEquivalency, equivalency_id)
    return db_equivalency

@handle_service_errors('TRADE')
@audit_event('TRADE', 'SKUEquivalency', 'UPDATE')
async def update_sku_equivalency_service(
    db: Session,
    equivalency_id: int,
    update_data: SKUEquivalencyUpdateSchema
) -> Tuple[SKUEquivalency, Dict[str, Any]]:
    '''
        Updates an SKU Equivalency mapping.
    '''
    message = f'Attempting to update SKU Equivalency ID: {equivalency_id}'
    logger.info(message)

    db_equivalency = get_record(db, SKUEquivalency, equivalency_id)
    old_values = sqlalchemy_object_as_dict(db_equivalency)

    # 'Prepare data dictionary for update'
    update_dict = update_data.model_dump(exclude_unset = True)

    # 'Handle SKU translation if product_sku is included in the update'
    if 'product_sku' in update_dict and update_dict['product_sku']:
        sku = update_dict.pop('product_sku')
        # 'We need company_id for the lookup'
        company_id = db_equivalency.company_id
        update_dict['product_id'] = _get_product_id_by_sku(db, company_id, sku)

    # 'Update the record manually as update_record expects a schema'
    # 'This avoids passing a dict to update_record'
    for key, value in update_dict.items():
        setattr(db_equivalency, key, value)

    db.add(db_equivalency)
    db.commit()
    db.refresh(db_equivalency)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_equivalency)
    }

    return db_equivalency, auditable_data

@handle_service_errors('TRADE')
@audit_event('TRADE', 'SKUEquivalency', 'DELETE')
async def delete_sku_equivalency_service(
    db: Session,
    equivalency_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes an SKU Equivalency mapping.
    '''
    message = f'Attempting to delete SKU Equivalency ID: {equivalency_id}'
    logger.info(message)

    db_equivalency = get_record(db, SKUEquivalency, equivalency_id)
    old_values = sqlalchemy_object_as_dict(db_equivalency)

    delete_record(
        db = db,
        model = db_equivalency,
        record_id = equivalency_id
    )
    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return equivalency_id, auditable_data

# --- PRODUCT ASSIGNMENT POS SERVICES ---

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ProductAssignmentPOS', 'CREATE')
async def create_product_assignment_service(
    db: Session,
    assignment_data: ProductAssignmentPOSCreateSchema
) -> ProductAssignmentPOS:
    '''
        Creates a new Product to POS Assignment.
    '''
    message = (f'Attempting to assign SKU: {assignment_data.product_sku} '
               f'to POS ID: {assignment_data.point_of_sale_id}')
    logger.info(message)

    # 1. Translate SKU to product_id (reusing existing helper)
    product_id = _get_product_id_by_sku(
        db, assignment_data.company_id, assignment_data.product_sku
    )

    # 2. Verify POS exists (optional but good practice)
    _ = get_record(db, PointOfSale, assignment_data.point_of_sale_id)

    # 3. Prepare data for create_record
    extra_fields = {
        'product_id': product_id
    }

    # Exclude product_sku as it's not in the ORM model
    exclude_relations = ['product_sku']

    db_assignment = create_record(
        db,
        ProductAssignmentPOS,
        assignment_data,
        extra_fields = extra_fields,
        exclude_relations = exclude_relations
    )

    db.commit()
    db.refresh(db_assignment)
    return db_assignment

@handle_service_errors('TRADE')
async def get_product_assignment_by_id_service(
    db: Session,
    assignment_id: int
) -> ProductAssignmentPOS:
    '''
        Retrieves a single Product to POS Assignment by its ID.
    '''
    message = f'Retrieving Product Assignment POS ID: {assignment_id}'
    logger.info(message)

    db_assignment = get_record(db, ProductAssignmentPOS, assignment_id)
    return db_assignment

@handle_service_errors('TRADE')
async def get_product_assignments_list_service(
    db: Session, filters: ProductAssignmentPOSFilterSchema, skip: int, limit: int
) -> Tuple[List[ProductAssignmentPOS], int]:
    '''
        Retrieves a paginated and filtered list of Product POS Assignments.
    '''
    message = f'Attempting to retrieve Product POS Assignment list for company {filters.company_id}'
    logger.info(message)

    query = db.query(ProductAssignmentPOS)

    # Mandatory filter
    conditions = [ProductAssignmentPOS.company_id == filters.company_id]

    # Optional filters
    if filters.product_id:
        conditions.append(ProductAssignmentPOS.product_id == filters.product_id)
    if filters.point_of_sale_id:
        conditions.append(ProductAssignmentPOS.point_of_sale_id == filters.point_of_sale_id)
    if filters.status:
        conditions.append(ProductAssignmentPOS.status == filters.status)

    query = query.filter(and_(*conditions))

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    return items, total

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ProductAssignmentPOS', 'UPDATE')
async def update_product_assignment_service(
    db: Session,
    assignment_id: int,
    update_data: ProductAssignmentPOSUpdateSchema
) -> Tuple[ProductAssignmentPOS, Dict[str, Any]]:
    '''
        Updates a Product to POS Assignment (e.g., changes status).
    '''
    message = f'Attempting to update Product Assignment POS ID: {assignment_id}'
    logger.info(message)

    db_assignment = get_record(db, ProductAssignmentPOS, assignment_id)
    old_values = sqlalchemy_object_as_dict(db_assignment)

    # Use the generic crud.update_record function
    db_assignment = update_record(db, db_assignment, update_data)

    db.commit()
    db.refresh(db_assignment)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_assignment)
    }

    return db_assignment, auditable_data

@handle_service_errors('TRADE')
@audit_event('TRADE', 'ProductAssignmentPOS', 'DELETE')
async def delete_product_assignment_service(
    db: Session,
    assignment_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a Product to POS Assignment.
    '''
    message = f'Attempting to delete Product Assignment POS ID: {assignment_id}'
    logger.info(message)

    db_assignment = get_record(db, ProductAssignmentPOS, assignment_id)
    old_values = sqlalchemy_object_as_dict(db_assignment)

    delete_record(
        db = db,
        model = db_assignment,
        record_id = assignment_id
    )
    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return assignment_id, auditable_data
