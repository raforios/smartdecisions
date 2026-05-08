'''
    Business Logic for Products and SKUs.
'''
from typing import Any, Dict, List, Tuple, Type
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session, DeclarativeBase, joinedload
from sqlalchemy.exc import SQLAlchemyError
from services.crud import (
    create_record,
    delete_record,
    get_record,
    update_record
)
from services.exceptions import (
    RegisterAlreadyExistsError,
    RegisterNotFoundError,
    InvalidInputError
)
from services.logger_config import custom_logger as logger
from services.utils import (
    generic_bulk_processor,
    handle_service_errors,
    audit_event,
    perform_bulk_upload,
    sqlalchemy_object_as_dict
)
from models.impulses import (
    ImpulseInventoryStart,
    ImpulseInventoryEnd,
    ImpulseSaleDetail,
    TradePromotionDetail
)
from models.replenishments import (
    ReplenishmentInventory,
    ReplenishmentReception,
    ComplementaryBandeoDetail
)
from models.products import (
    Product,
    ProductCategory,
    ProductAssignmentPOS,
    SKUEquivalency,
    SKUSequencer
)
from models.pos import PointOfSale
from schemas.products import (
    ProductAssignmentPOSBulkItemSchema,
    ProductAssignmentPOSCreateSchema,
    ProductAssignmentPOSFilterSchema,
    ProductAssignmentPOSUpdateSchema,
    ProductBulkCreateSchema,
    ProductCreateSchema,
    ProductFilterSchema,
    ProductUpdateSchema,
    SKUEquivalencyCreateSchema,
    SKUEquivalencyUpdateSchema,
    SKUEquivalencyBulkItemSchema,
    ProductCategoryCreateSchema
)

async def create_bulk_items_from_skus(
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
        product_id = get_product_id_by_sku(
            db, company_id, item.product_sku
        )

        item_data = item.model_dump(exclude={'product_sku'})

        db_item = model_class(
            attendance_id = attendance_id,
            product_id = product_id,
            **item_data
        )
        db.add(db_item)
        created_items.append(db_item)

    db.commit()
    for item in created_items:
        db.refresh(item)

    return created_items

def _get_segment_key_from_list(categories: List[ProductCategoryCreateSchema]) -> str:
    '''
        Constructs the non-sequential segment key for the SKU from a list of categories.
        Sorts categories by their numeric category_id and takes the first 4, padding
        if necessary, to ensure a consistent SKU structure as per requirements.
    '''
    # Sort by numeric category_id to keep a deterministic order for the SKU segment.
    sorted_cats = sorted(categories, key=lambda c: c.category_id)

    # Per requirements doc, SKU is composed of up to 4 categories.
    sku_cats = sorted_cats[:4]
    codes = [c.category_code for c in sku_cats]

    # Pad with '000' if fewer than 4 categories are provided for the SKU.
    while len(codes) < 4:
        codes.append('000')

    return '.'.join(codes)

def _format_sequence_number(sequence: int) -> str:
    '''
        Formats the sequence number (SEC) to a 3-digit string (e.g., 1 -> '001').
    '''
    return f'{sequence:03d}'

def get_product_id_by_sku(
    db: Session,
    company_id: int,
    sku: str
) -> int:
    '''
        Searches for the internal product ID (product_id) using its SKU.
    '''
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

    return product.id

def _generate_next_sku_sequence(
    db: Session,
    company_id: int,
    segment_key: str
) -> str:
    '''
        Atomically gets the next sequence number (SEC) for a given segment key
        and constructs the full SKU.

        NOTE: This function MUST be called within an active transactional context.
    '''
    message = f'Attempting to generate atomic SKU sequence for company {
        company_id} with segment key {segment_key}'
    logger.debug(message)

    sequencer = db.query(SKUSequencer).filter(
        SKUSequencer.company_id == company_id,
        SKUSequencer.segment_key == segment_key
    ).with_for_update().first()

    if sequencer:
        sequencer.last_sequence_number += 1
        db.add(sequencer)
        next_sequence = sequencer.last_sequence_number
    else:
        next_sequence = 1
        new_sequencer = SKUSequencer(
            company_id = company_id,
            segment_key = segment_key,
            last_sequence_number = next_sequence
        )
        db.add(new_sequencer)

    db.flush()

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
        Creates a new product, its associated categories, and atomically generates its unique SKU.
    '''
    message = f'Attempting to create product {product_data.name} for company ID: {
        product_data.company_id}'
    logger.info(message)

    existing_product = db.query(Product).filter(
        Product.company_id == product_data.company_id,
        Product.name == product_data.name
    ).first()

    if existing_product:
        error_msg = f'Product with name {product_data.name} already exists for this company.'
        logger.error(error_msg)
        raise RegisterAlreadyExistsError(detail = error_msg)

    product_info = product_data.model_dump(exclude={'categories'})
    category_info = product_data.categories

    with db.begin_nested():
        segment_key = _get_segment_key_from_list(category_info)
        final_sku = _generate_next_sku_sequence(
            db,
            product_data.company_id,
            segment_key
        )

        product_dict = product_info
        product_dict['sku'] = final_sku

        db_product = Product(**product_dict)

        for cat_data in category_info:
            db_product.categories.append(ProductCategory(**cat_data.model_dump()))

        db.add(db_product)

    db.commit()
    db.refresh(db_product)

    return db_product

@handle_service_errors('TRADE')
async def get_product_by_id_service(
    db: Session,
    product_id: int
) -> Product:
    '''
        Retrieves a Product record by its unique ID, including its categories.
    '''
    message = f'Attempting to retrieve product with ID: {product_id}'
    logger.info(message)

    db_product = db.query(Product).options(
        joinedload(Product.categories)
    ).filter(Product.id == product_id).first()

    if not db_product:
        raise RegisterNotFoundError(f'Product with ID {product_id} not found.')

    return db_product

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

    query = db.query(Product).options(joinedload(Product.categories))

    conditions = [Product.company_id == filters.company_id]

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
@audit_event('TRADE', 'Product', 'UPDATE')
async def update_product_service(
    db: Session,
    product_id: int,
    product_data: ProductUpdateSchema
) -> Tuple[Product, Dict[str, Any]]:
    '''
        Updates an existing Product record. Categories are not updated here.
    '''
    message = f'Attempting to update product ID: {product_id}'
    logger.info(message)

    db_product = get_record(db, Product, product_id)
    old_values = sqlalchemy_object_as_dict(db_product)

    db_product = update_record(db, db_product, product_data)

    db.commit()
    db.refresh(db_product)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(db_product)
    }

    return db_product, auditable_data

@handle_service_errors('TRADE')
@audit_event('TRADE', 'Product', 'DELETE')
async def delete_product_service(
    db: Session,
    product_id: int
) -> Tuple[int, Dict[str, Any]]:
    '''
        Deletes a product record and its associated categories via cascading.
    '''
    message = f'Attempting to delete product ID: {product_id}'
    logger.info(message)

    db_product = get_record(db, Product, product_id)
    old_values = sqlalchemy_object_as_dict(db_product)

    # 1. Cleanup Dependencies
    db.query(ProductAssignmentPOS).filter(ProductAssignmentPOS.product_id == product_id).delete()

    # We also need to cleanup Impulse tables that might reference this product
    db.query(ImpulseInventoryStart).filter(ImpulseInventoryStart.product_id == product_id).delete()
    db.query(ImpulseInventoryEnd).filter(ImpulseInventoryEnd.product_id == product_id).delete()
    db.query(ImpulseSaleDetail).filter(ImpulseSaleDetail.product_id == product_id).delete()
    db.query(TradePromotionDetail).filter(TradePromotionDetail.product_id == product_id).delete()

    # Replenishment tables
    db.query(ReplenishmentInventory).filter(
        ReplenishmentInventory.product_id == product_id
    ).delete()
    db.query(ReplenishmentReception).filter(
        ReplenishmentReception.product_id == product_id
    ).delete()
    db.query(ComplementaryBandeoDetail).filter(
        ComplementaryBandeoDetail.product_id == product_id
    ).delete()

    db.flush()

    # 2. Delete Product
    delete_record(
        db = db,
        model = Product,
        record_id = product_id
    )

    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return product_id, auditable_data

# --- PRODUCT BULK HELPERS ---

async def _insert_product_bulk_data(
    db: Session,
    processed_data: List[ProductBulkCreateSchema],
    file_name: str, # pylint: disable=unused-argument
    auth_token: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Handles the transactional insertion of Product records from bulk uploads,
        adapting the flat schema to the relational model.
    '''
    products_created = 0
    if not processed_data:
        return {'message': 'No valid product data to insert.', 'created_records': 0}

    for item in processed_data:
        try:
            if db.query(Product).filter(
                Product.company_id == item.company_id, Product.name == item.name
            ).first():
                error_msg = f'Product "{item.name}" already exists. Skipping.'
                logger.warning(error_msg)
                continue

            # Dynamically build category list from flat schema
            category_info = [
                ProductCategoryCreateSchema(
                    category_id = getattr(item, f'category_{i}_id'),
                    category_code = getattr(item, f'category_{i}_code')
                )
                for i in range(1, 5)
                if getattr(item, f'category_{i}_id') and getattr(item, f'category_{i}_code')
            ]

            if not category_info:
                error_msg = f'Skipping product {item.name} as it has no categories.'
                logger.warning(error_msg)
                continue

            with db.begin_nested():
                # Prepare product data, excluding category fields
                product_dict = item.model_dump(exclude={
                    f'category_{i}_id' for i in range(1, 5)
                } | {
                    f'category_{i}_code' for i in range(1, 5)
                })

                # Generate SKU
                segment_key = _get_segment_key_from_list(category_info)
                product_dict['sku'] = _generate_next_sku_sequence(db, item.company_id, segment_key)

                # Create Product and associate categories
                db_product = Product(**product_dict)
                db_product.categories = [ProductCategory(**c.model_dump()) for c in category_info]

                db.add(db_product)
                db.flush()
                products_created += 1

        except (SQLAlchemyError, InvalidInputError) as e:
            error_msg = f'Unexpected error for product {item.name}: {e}'
            logger.error(error_msg, exc_info=True)
            continue

    return {
        'message': 'Product bulk insertion completed.',
        'created_records': products_created
    }

@handle_service_errors('TRADE')
async def bulk_create_products_service(
    db: Session,
    file_name: str,
    delimiter: str,
    auth_token: str,
) -> Dict[str, Any]:
    '''
        Service wrapper function to handle the bulk upload of Products.
    '''
    result = await perform_bulk_upload(
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        bulk_schema = ProductBulkCreateSchema,
        processor_func = generic_bulk_processor,
        inserter_func = _insert_product_bulk_data,
        delimiter = delimiter
    )

    return result

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

    existing_equiv = db.query(SKUEquivalency).filter(
        SKUEquivalency.company_id == equivalency_data.company_id,
        SKUEquivalency.external_system_name == equivalency_data.external_system_name,
        SKUEquivalency.external_product_code == equivalency_data.external_product_code
    ).first()

    if existing_equiv:
        error_msg = f'Equivalency for system {equivalency_data.external_system_name
                } and code {equivalency_data.external_product_code} already exists.'
        logger.error(error_msg, exc_info = True)
        raise RegisterAlreadyExistsError(detail = error_msg)

    product_id = get_product_id_by_sku(
        db, equivalency_data.company_id, equivalency_data.product_sku
    )

    extra_fields = {
        'product_id': product_id
    }

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

    db_equivalency = db.query(SKUEquivalency).options(
        joinedload(SKUEquivalency.product)
    ).filter(SKUEquivalency.id == equivalency_id).first()

    if not db_equivalency:
        raise RegisterNotFoundError(
            detail = f'SKU Equivalency with ID {equivalency_id} not found.'
        )

    if db_equivalency.product:
        setattr(db_equivalency, 'product_sku', db_equivalency.product.sku)

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

    db_equivalency = db.query(SKUEquivalency).options(
        joinedload(SKUEquivalency.product)
    ).filter(SKUEquivalency.id == equivalency_id).first()

    if not db_equivalency:
        raise RegisterNotFoundError(
            detail = f'SKU Equivalency with ID {equivalency_id} not found.'
        )

    old_values = sqlalchemy_object_as_dict(db_equivalency)

    update_dict = update_data.model_dump(exclude_unset = True)

    if 'product_sku' in update_dict and update_dict['product_sku']:
        sku = update_dict.pop('product_sku')
        company_id = db_equivalency.company_id
        update_dict['product_id'] = get_product_id_by_sku(db, company_id, sku)

    for key, value in update_dict.items():
        setattr(db_equivalency, key, value)

    db.add(db_equivalency)
    db.commit()
    db.refresh(db_equivalency)

    if db_equivalency.product:
        setattr(db_equivalency, 'product_sku', db_equivalency.product.sku)

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
        model = SKUEquivalency,
        record_id = equivalency_id
    )
    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return equivalency_id, auditable_data

@handle_service_errors('TRADE')
async def get_sku_equivalencies_list_service(
    db: Session,
    skip: int,
    limit: int
) -> Tuple[List[SKUEquivalency], int]:
    '''
        Retrieves a paginated list of SKU Equivalencies.
    '''
    message = 'Attempting to retrieve SKU Equivalencies list.'
    logger.info(message)

    query = db.query(SKUEquivalency).options(
        joinedload(SKUEquivalency.product)
    )

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    for item in items:
        if item.product:
            setattr(item, 'product_sku', item.product.sku)

    return items, total

# --- SKU EQUIVALENCY BULK HELPERS ---
async def _insert_sku_equivalency_bulk_data(
    db: Session,
    processed_data: List[SKUEquivalencyCreateSchema],
    file_name: str, # pylint: disable=unused-argument
    auth_token: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Handles the transactional insertion of SKU Equivalency records.
    '''
    records_created = 0

    if not processed_data:
        return {'message': 'No valid equivalency data to insert.', 'created_records': 0}

    for item in processed_data:
        try:
            if db.query(SKUEquivalency).filter(
                SKUEquivalency.company_id == item.company_id,
                SKUEquivalency.external_system_name == item.external_system_name,
                SKUEquivalency.external_product_code == item.external_product_code
            ).first():
                error_msg = (f"Equivalency for system '{item.external_system_name}' "
                             f"and code '{item.external_product_code}' already exists. Skipping.")
                logger.warning(error_msg)
                continue

            with db.begin_nested():
                product_id = get_product_id_by_sku(
                    db, item.company_id, item.product_sku
                )

                equiv_dict = item.model_dump(exclude={'product_sku'})
                equiv_dict['product_id'] = product_id

                db_equiv = SKUEquivalency(**equiv_dict)
                db.add(db_equiv)
                db.flush()
                records_created += 1

        except RegisterNotFoundError:
            error_msg = (f"Skipping record in bulk upload: Internal SKU '{item.product_sku}' "
                         f"not found for company {item.company_id}.")
            logger.warning(error_msg)
            continue
        except (SQLAlchemyError, InvalidInputError) as e:
            error_msg = (f"Unexpected error during SKU Equivalency bulk insertion "
                         f"for code {item.external_product_code}: {e}")
            logger.error(error_msg, exc_info=True)
            continue

    return {
        'message': 'SKU Equivalency insertion completed.',
        'created_records': records_created
    }

@handle_service_errors('TRADE')
async def bulk_create_sku_equivalencies_service(
    db: Session,
    file_name: str,
    delimiter: str,
    auth_token: str,
) -> Dict[str, Any]:
    '''
        Service wrapper function to handle the bulk upload of SKU equivalencies.
    '''
    message = 'Starting SKU Equivalencies bulk upload process.'
    logger.info(message)

    result = await perform_bulk_upload(
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        bulk_schema = SKUEquivalencyBulkItemSchema,
        processor_func = generic_bulk_processor,
        inserter_func = _insert_sku_equivalency_bulk_data,
        delimiter = delimiter
    )

    return result

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
    message = f'Assigning SKU {assignment_data.product_sku} to POS {
        assignment_data.point_of_sale_id}'
    logger.info(message)

    # 1. Validate POS Existence
    pos = db.query(PointOfSale).filter(
        PointOfSale.id == assignment_data.point_of_sale_id,
        PointOfSale.company_id == assignment_data.company_id
    ).first()

    if not pos:
        error_msg = f'POS with ID {assignment_data.point_of_sale_id} not found for this company.'
        logger.error(error_msg)
        raise RegisterNotFoundError(detail = error_msg)

    # 2. Resolve Product ID
    product_id = get_product_id_by_sku(
        db = db,
        company_id = assignment_data.company_id,
        sku = assignment_data.product_sku
    )

    # 3. Check for duplicates
    exists = db.query(ProductAssignmentPOS).filter(
        ProductAssignmentPOS.company_id == assignment_data.company_id,
        ProductAssignmentPOS.product_id == product_id,
        ProductAssignmentPOS.point_of_sale_id == assignment_data.point_of_sale_id
    ).first()

    if exists:
        raise RegisterAlreadyExistsError(
            detail = f'Product {assignment_data.product_sku} is already assigned to this POS.'
        )

    db_assign = ProductAssignmentPOS(
        company_id = assignment_data.company_id,
        product_id = product_id,
        point_of_sale_id = assignment_data.point_of_sale_id,
        near_expiration_days = assignment_data.near_expiration_days,
        minimum_stock = assignment_data.minimum_stock,
        status = assignment_data.status or 'ACTIVE'
    )

    db.add(db_assign)
    db.commit()
    db.refresh(db_assign)

    return db_assign

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

    conditions = [ProductAssignmentPOS.company_id == filters.company_id]

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
        model = ProductAssignmentPOS,
        record_id = assignment_id
    )
    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return assignment_id, auditable_data

async def _insert_assignment_bulk_data(
    db: Session,
    processed_data: List[ProductAssignmentPOSBulkItemSchema],
    file_name: str, # pylint: disable=unused-argument
    auth_token: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Handles the transactional insertion of Product Assignments.
        Resolves POS IDs from external codes if necessary.
    '''
    records_created = 0
    if not processed_data:
        return {'message': 'No valid data.', 'created_records': 0}

    for item in processed_data:
        try:
            # 1. Resolve Product ID
            product_id = get_product_id_by_sku(db, item.company_id, item.product_sku)

            # 2. Resolve POS ID
            pos_id = item.point_of_sale_id
            if not pos_id and item.pos_external_code:
                pos = db.query(PointOfSale).filter(
                    PointOfSale.company_id == item.company_id,
                    PointOfSale.external_code == item.pos_external_code
                ).first()
                if pos:
                    pos_id = pos.id

            if not pos_id:
                error_msg = f'Skipping assignment: POS not found for row {item}'
                logger.warning(error_msg)
                continue

            # 3. Check for duplicates
            exists = db.query(ProductAssignmentPOS).filter(
                ProductAssignmentPOS.company_id == item.company_id,
                ProductAssignmentPOS.product_id == product_id,
                ProductAssignmentPOS.point_of_sale_id == pos_id
            ).first()

            if exists:
                continue

            # 4. Create
            db_assign = ProductAssignmentPOS(
                company_id = item.company_id,
                product_id = product_id,
                point_of_sale_id = pos_id,
                near_expiration_days = item.near_expiration_days,
                minimum_stock = item.minimum_stock,
                status = item.status
            )
            db.add(db_assign)
            records_created += 1

            # Flush every 100 records to manage memory
            if records_created % 100 == 0:
                db.flush()

        except RegisterAlreadyExistsError as e:
            error_msg = f'Product creation failed (Integrity): {e.detail}'
            logger.warning(error_msg)
            continue
        except (SQLAlchemyError, InvalidInputError) as e:
            error_msg = f'Unexpected error during Product bulk insertion for {item.pos_external_code
                        }: {e}'
            logger.error(error_msg, exc_info = True)
            continue

    return {
        'message': 'Product Assignment bulk upload completed.',
        'created_records': records_created
    }

@handle_service_errors('TRADE')
async def bulk_create_product_assignments_service(
    db: Session,
    file_name: str,
    delimiter: str,
    auth_token: str,
) -> Dict[str, Any]:
    '''
        Service wrapper for bulk assignments.
    '''
    return await perform_bulk_upload(
        db = db,
        file_name = file_name,
        auth_token = auth_token,
        bulk_schema = ProductAssignmentPOSBulkItemSchema,
        processor_func = generic_bulk_processor,
        inserter_func = _insert_assignment_bulk_data,
        delimiter = delimiter
    )

def validate_product_assigned_to_pos(
    db: Session,
    company_id: int,
    pos_id: int,
    product_id: int
) -> None:
    '''
        Validates if a product is actively assigned to a POS.
        Raises InvalidInputError if not assigned.
    '''
    assignment = db.query(ProductAssignmentPOS).filter(
        ProductAssignmentPOS.company_id == company_id,
        ProductAssignmentPOS.point_of_sale_id == pos_id,
        ProductAssignmentPOS.product_id == product_id,
        ProductAssignmentPOS.status == 'ACTIVE'
    ).first()

    if not assignment:
        raise InvalidInputError(
            detail = f'Product ID {product_id} is not assigned to POS ID {pos_id}.'
        )
