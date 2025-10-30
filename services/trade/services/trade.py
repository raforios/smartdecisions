'''
    Business logic services for the Trade Microservice, including
    atomic SKU generation and transactional nested creation.
'''
from sqlalchemy.orm import Session
from services.crud import (
    create_record,
)
from services.exceptions import (
    RegisterAlreadyExistsError,
)
from services.logger_config import custom_logger as logger
from services.utils import (
    handle_service_errors,
    audit_event
)
from models.trade import Product, SKUSequencer, PointOfSale, PointOfSaleInventory
from schemas.trade import (
    ProductCreateSchema,
    PointOfSaleCreateSchema
)

def _get_segment_key(category_1: str, category_2: str, category_3: str,
                      category_4: str) -> str:
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
    message = (f'Attempting to generate atomic SKU sequence for company {company_id} '
               f'with segment key {segment_key}')
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

    db.flush() # Persist the sequence update/creation before generating the SKU

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
            error_msg = (f"Point of Sale with external code {pos_data.external_code} "
                         f"already exists for company {pos_data.company_id}.")
            logger.error(error_msg)
            raise RegisterAlreadyExistsError(detail = error_msg)

    # Matching create_planning_with_details pattern:

    # 2. Create the main PointOfSale record.
    pos_dict = pos_data.model_dump(exclude = {'initial_inventory'})
    db_pos = PointOfSale(**pos_dict)
    db.add(db_pos)
    db.flush() # Flush to get the db_pos.id

    # 3. Iterate through initial inventory details and create nested records.
    if pos_data.initial_inventory:
        for inventory_data in pos_data.initial_inventory:

            # Use create_record from crud, matching the nested record creation in planning service
            create_record(
                db,
                PointOfSaleInventory,
                inventory_data,
                extra_fields = {
                    'point_of_sale_id': db_pos.id,
                    'company_id': pos_data.company_id # Propagate company_id for the child record
                }
            )

    # 4. Commit and refresh, matching create_planning_with_details flow
    db.commit()
    db.refresh(db_pos)

    return db_pos
