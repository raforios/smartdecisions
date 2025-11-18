'''
    Business Logic for Products and SKUs.
'''
from typing import Any, Dict, List, Tuple, Type
from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.orm import Session, DeclarativeBase, joinedload
from services.crud import (
    create_record,
    delete_record,
    get_record,
    update_record
)
from services.exceptions import (
    RegisterAlreadyExistsError,
    RegisterNotFoundError
)
from services.logger_config import custom_logger as logger
from services.utils import (
    handle_service_errors,
    audit_event,
    sqlalchemy_object_as_dict
)
from models.products import (
    Product,
    ProductAssignmentPOS,
    SKUEquivalency,
    SKUSequencer
)
from schemas.products import (
    ProductAssignmentPOSCreateSchema,
    ProductAssignmentPOSFilterSchema,
    ProductAssignmentPOSUpdateSchema,
    ProductCreateSchema,
    ProductFilterSchema,
    ProductUpdateSchema,
    SKUEquivalencyCreateSchema,
    SKUEquivalencyUpdateSchema
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
    return f'{category_1}.{category_2}.{category_3}.{category_4}'

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
        Creates a new product record, atomically generating its unique SKU.
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

    with db.begin_nested():
        final_sku = _generate_next_sku_sequence(
            db,
            product_data.company_id,
            product_data.category_1_code,
            product_data.category_2_code,
            product_data.category_3_code,
            product_data.category_4_code
        )

        product_dict = product_data.model_dump()
        product_dict['sku'] = final_sku

        db_product = Product(**product_dict)
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
        Updates an existing Product record.
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
        Deletes a product record.
    '''
    message = f'Attempting to delete product ID: {product_id}'
    logger.info(message)

    db_product = get_record(db, Product, product_id)
    old_values = sqlalchemy_object_as_dict(db_product)

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
        raise RegisterNotFoundError(detail = f'SKU Equivalency with ID {equivalency_id} not found.')

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
        Injects 'product_sku' into each record to satisfy the Response Schema
        without modifying the SQLAlchemy Model.
    '''
    message = 'Attempting to retrieve SKU Equivalencies list.'
    logger.info(message)

    # Use joinedload to fetch the related Product efficiently
    query = db.query(SKUEquivalency).options(
        joinedload(SKUEquivalency.product)
    )

    total = query.count()
    items = query.offset(skip).limit(limit).all()

    # Manually inject 'product_sku' into the instances so Pydantic can read it
    for item in items:
        if item.product:
            # We assign the attribute dynamically to the instance
            setattr(item, 'product_sku', item.product.sku)

    return items, total

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

    # 1. Traducir SKU a ID (Esto soluciona el problema de consistencia)
    product_id = get_product_id_by_sku(
        db = db,
        company_id = assignment_data.company_id,
        sku = assignment_data.product_sku
    )

    # 2. Verificar si ya existe
    exists = db.query(ProductAssignmentPOS).filter(
        ProductAssignmentPOS.company_id == assignment_data.company_id,
        ProductAssignmentPOS.product_id == product_id,
        ProductAssignmentPOS.point_of_sale_id == assignment_data.point_of_sale_id
    ).first()

    if exists:
        raise RegisterAlreadyExistsError(
            detail = f'Product {assignment_data.product_sku} is already assigned to this POS.'
        )

    # 3. Crear
    db_assign = ProductAssignmentPOS(
        company_id = assignment_data.company_id,
        product_id = product_id, # Usamos el ID traducido
        point_of_sale_id = assignment_data.point_of_sale_id,
        status = 'ACTIVE'
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
