'''
   Forms Controller
'''
from datetime import datetime
from typing import List, Dict
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

# Import models
from models.forms import (
    FormHeader,
    QuestionDetail,
    MultipleChoiceOption,
    QuestionFlow
)
# Import schemas
from schemas.forms import (
    FormHeaderCreate,
    FormHeaderUpdate,
    QuestionDetailCreate,
    QuestionDetailUpdate
)
# Import custom exceptions
from services.exceptions import (
    RegisterNotFoundError,
    RegisterAlreadyExistsError,
)
from services.logger_config import custom_logger as logger
from services.crud import (
    create_record,
    get_record,
    update_record,
    delete_record
)

# --- CRUD operations for FormHeader ---
async def create_form_header(
    db: Session, form_data: FormHeaderCreate
) -> FormHeader:
    '''
        Creates a new form header along with its associated questions,
        multiple choice options, and flow rules.
    '''
    message = f'Attempting to create form header with code: {form_data.form_code}'
    logger.info(message)
    try:
        # Specific validation for unique form_code
        existing_form = db.query(FormHeader).filter(
            FormHeader.form_code == form_data.form_code
        ).first()
        if existing_form:
            message = f'Form with code {form_data.form_code} already exists.'
            logger.warning(message)
            raise RegisterAlreadyExistsError(
                detail = f'Form with this code: {form_data.form_code} already exists.'
            )

        # Call create_record, explicitly excluding 'questions' as it's a relation
        db_form_header = create_record(
            db,
            FormHeader,
            form_data,
            extra_fields = {'creation_date': datetime.now()},
            exclude_relations = ['questions']
        )

        # --- DEBUGGING STEP: LOG THE ID ---
        message = f'FormHeader created (or flushed). ID: {db_form_header.id}'
        logger.info(message)
        if db_form_header.id is None:
            # This case should ideally be caught by create_record raising an exception,
            # but if for some reason it's None, we raise early.
            logger.error('''FormHeader ID is None immediately after creation/flush.
                         This is unexpected.''')
            raise ValueError('Failed to obtain ID for FormHeader. Cannot proceed with questions.')
        # --- END DEBUGGING STEP ---

        for q_data in form_data.questions:

            db_question = create_record(
                db,
                QuestionDetail,
                q_data,
                extra_fields = {'form_id': db_form_header.id},
                exclude_relations = ['options', 'flow_rules']
            )

            if q_data.options:
                for opt_data in q_data.options:
                    create_record(
                        db,
                        MultipleChoiceOption,
                        opt_data,
                        extra_fields = {'question_id': db_question.id}
                    )

            if q_data.flow_rules:
                for flow_data in q_data.flow_rules:
                    create_record(
                        db,
                        QuestionFlow,
                        flow_data,
                        extra_fields = {'form_detail_id': db_question.id},
                        exclude_relations = ['current_question_number']
                    )
        db.commit()
        db.refresh(db_form_header)
        message = f'Form header {db_form_header.id} created successfully.'
        logger.info(message)
        return db_form_header
    except IntegrityError as e:
        db.rollback()
        error_msg = f'Database integrity error when creating form: {e}'
        logger.error(error_msg, exc_info = True)
        raise RegisterAlreadyExistsError(
            detail = 'Error creating form: The code or question/number combination already exists.'
        ) from e
    except RegisterAlreadyExistsError as e:
        db.rollback()
        raise e
    except ValueError as e:
        db.rollback()
        error_msg = f'Critical error: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error creating form header: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

async def get_form_header_by_id(
    db: Session,
    form_id: int
) -> FormHeader:
    '''
        Retrieves a form header by its ID, including all its nested questions,
        options, and flow rules.
    '''
    message = f'Attempting to retrieve form header with ID: {form_id}'
    logger.info(message)
    eager_load_options = [
        joinedload(FormHeader.questions).joinedload(QuestionDetail.options),
        joinedload(FormHeader.questions).joinedload(QuestionDetail.flow_rules)
    ]
    try:
        form_header = get_record(db, FormHeader, form_id, eager_load_options)
        message = f'Form header {form_id} retrieved successfully.'
        logger.info(message)
        return form_header
    except RegisterNotFoundError as e:
        message = f'Form with ID {form_id} not found.'
        logger.warning(message)
        raise RegisterNotFoundError(detail = message) from e
    except Exception as e:
        error_msg = f'Unexpected error retrieving form header {form_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

async def get_all_form_headers(
    db: Session,
    skip: int = 0,
    limit: int = 100
) -> List[FormHeader]:
    '''
        Retrieves a list of all form headers, with optional pagination.
        Does not load nested questions by default for performance.
    '''
    message = f'Attempting to retrieve all form headers (skip: {skip}, limit: {limit}).'
    logger.info(message)
    return db.query(FormHeader).offset(skip).limit(limit).all()

async def update_form_header(
    db: Session, form_id: int, form_data: FormHeaderUpdate
) -> FormHeader:
    '''
        Updates an existing form header.
        Note: This method is for updating the header attributes only.
        Questions, options, and flow rules should be managed via separate
        dedicated endpoints (e.g., for question CRUD).
    '''
    message = f'Attempting to update form header with ID: {form_id}'
    logger.info(message)
    db_form_header = get_record(db, FormHeader, form_id)

    # Specific validation for unique form_code if it's being updated
    if form_data.form_code is not None and form_data.form_code != db_form_header.form_code:
        existing_form_with_code = db.query(FormHeader).filter(
            FormHeader.form_code == form_data.form_code,
            FormHeader.id != form_id
        ).first()
        if existing_form_with_code:
            message = f'''Cannot update form {form_id}: form_code {form_data.form_code}
                    already in use.'''
            logger.warning(message)
            raise RegisterAlreadyExistsError(
               detail = message
            )
    try:
        # Call update_record, excluding 'questions' as it's not updated via this endpoint
        db_form_header = update_record(db, db_form_header, form_data,
                        exclude_relations = ['questions'])
        db.commit()
        db.refresh(db_form_header)
        message = f'Form header {form_id} updated successfully.'
        logger.info(message)
        return db_form_header
    except IntegrityError as e: # Captura errores de unicidad
        db.rollback()
        error_msg = f'Database integrity error when updating form {form_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise RegisterAlreadyExistsError(
            detail = 'Error updating form: code already exists or there is a data conflict.'
        ) from e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error updating form header {form_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

async def delete_form_header(
    db: Session, form_id: int
) -> Dict[str, str]:
    '''
        Deletes a form header by its ID.
        Due to cascade settings in the model, associated questions, options,
        flow rules, and form responses will also be deleted.
    '''
    message = f'Attempting to delete form header with ID: {form_id}'
    logger.info(message)
    try:
        delete_record(db, FormHeader, form_id)
        db.commit()
        message = f'Form header {form_id} deleted successfully.'
        logger.info(message)
        return {'message': 'Form header deleted successfully.'}
    except RegisterNotFoundError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error deleting form header {form_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

# --- CRUD operations for QuestionDetail ---
async def create_question_detail(
    db: Session, form_id: int, question_data: QuestionDetailCreate
) -> QuestionDetail:
    '''
        Creates a new question detail for a specific form,
        including its multiple choice options and flow rules.
    '''
    message = f'''Attempting to create question for form ID: {form_id},
            question number: {question_data.question_number}'''
    logger.info(message)
    _ = get_record(db, FormHeader, form_id)

    try:
        # Call create_record, explicitly excluding 'options' and 'flow_rules'
        db_question = create_record(
            db,
            QuestionDetail,
            question_data,
            extra_fields={'form_id': form_id},
            exclude_relations=['options', 'flow_rules']
        )

        if question_data.options:
            for opt_data in question_data.options:
                create_record(
                    db,
                    MultipleChoiceOption,
                    opt_data,
                    extra_fields={'question_id': db_question.id}
                )

        if question_data.flow_rules:
            for flow_data in question_data.flow_rules:
                create_record(
                    db,
                    QuestionFlow,
                    flow_data,
                    extra_fields={'form_detail_id': db_question.id}
                )

        db.commit()
        db.refresh(db_question)
        message = f'Question {db_question.id} created successfully for form {form_id}.'
        logger.info(message)
        return db_question
    except IntegrityError as e:
        db.rollback()
        error_msg = f'Database integrity error creating question for form {form_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise RegisterAlreadyExistsError(
            detail = 'A question with this number already exists for this form.'
        ) from e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error creating question detail for form {form_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

async def get_question_detail_by_id(
    db: Session,
    question_id: int
) -> QuestionDetail:
    '''
        Retrieves a question detail by its ID, including its nested options and flow rules.
    '''
    message = f'Attempting to retrieve question detail with ID: {question_id}'
    logger.info(message)
    eager_load_options = [
        joinedload(QuestionDetail.options),
        joinedload(QuestionDetail.flow_rules)
    ]
    try:
        question = get_record(db, QuestionDetail, question_id, eager_load_options)
        message = f'Question detail {question_id} retrieved successfully.'
        logger.info(message)
        return question
    except RegisterNotFoundError as e: # Corrected W0707
        message = f'Question detail with ID {question_id} not found.'
        logger.warning(message)
        raise RegisterNotFoundError(detail = message) from e
    except Exception as e:
        error_msg = f'Unexpected error retrieving question detail {question_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

async def update_question_detail(
    db: Session,
    question_id: int,
    question_data: QuestionDetailUpdate
) -> QuestionDetail:
    '''
        Updates an existing question detail.
        This method supports updating question attributes, and replacing
        (deleting old and adding new) associated options and flow rules.
    '''
    message = f'Attempting to update question detail with ID: {question_id}'
    logger.info(message)
    db_question = get_record(db, QuestionDetail, question_id)

    try:
        # Update core question attributes using generic update
        db_question = update_record(db, db_question, question_data)

        update_data = question_data.model_dump(exclude_unset = True)

        # Handle options update (replace existing with new ones)
        if 'options' in update_data and update_data['options'] is not None:
            # Delete existing options
            db.query(MultipleChoiceOption).filter(
                MultipleChoiceOption.question_id == question_id
            ).delete(synchronize_session = False)
            db.flush() # Flush to ensure deletions are processed

            # Add new options
            for opt_data in update_data['options']:
                create_record(
                    db,
                    MultipleChoiceOption,
                    opt_data,
                    extra_fields={'question_id': question_id}
                )

        if 'flow_rules' in update_data and update_data['flow_rules'] is not None:
            # Delete existing flow rules
            db.query(QuestionFlow).filter(
                QuestionFlow.form_detail_id == question_id
            ).delete(synchronize_session=False)
            db.flush() # Flush to ensure deletions are processed

            # Add new flow rules
            for flow_data in update_data['flow_rules']:
                create_record(
                    db,
                    QuestionFlow,
                    flow_data,
                    extra_fields={'form_detail_id': question_id}
                )

        db.commit()
        db.refresh(db_question) # Refresh to load all relationships
        message = f'Question detail {question_id} updated successfully.'
        logger.info(message)
        return db_question
    except IntegrityError as e: # Captura errores de unicidad
        db.rollback()
        error_msg = f'Database integrity error when updating question {question_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise RegisterAlreadyExistsError(
            detail = 'There is already a question with the same number on this form.'
        ) from e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error updating question details {question_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

async def delete_question_detail(
    db: Session,
    question_id: int
) -> Dict[str, str]:
    '''
        Deletes a question detail by its ID.
        Due to cascade settings in the model, associated options and flow rules
        will also be deleted.
    '''
    message = f'Attempting to delete question detail with ID: {question_id}'
    logger.info(message)
    try:
        delete_record(db, QuestionDetail, question_id)
        db.commit()
        message = f'Question detail {question_id} deleted successfully.'
        logger.info(message)
        return {'message': 'Question detail deleted successfully.'}
    except RegisterNotFoundError as e: # Corrected W0707
        db.rollback()
        raise RegisterNotFoundError(
            detail = f'Question detail with ID {question_id} not found for deletion.'
        ) from e
