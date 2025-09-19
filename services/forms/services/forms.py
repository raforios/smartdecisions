'''
    Business logic services for the Forms Microservice.
'''
from datetime import datetime
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from models.forms import (
    FormHeader,
    QuestionDetail,
    MultipleChoiceOption,
    QuestionFlow
)
from schemas.forms import (
    FormFilters,
    FormHeaderCreate,
    FormHeaderUpdate,
    QuestionDetailCreate,
    QuestionDetailUpdate
)
from services.crud import (
    create_record,
    get_record,
    update_record,
    delete_record
)
from services.exceptions import (
    RegisterAlreadyExistsError
)
from services.logger_config import custom_logger as logger
from services.utils import handle_service_errors, audit_event, sqlalchemy_object_as_dict

# --- CRUD operations for FormHeader ---
@handle_service_errors('FORMS')
@audit_event('FORMS', 'FormHeader', 'CREATE')
async def create_form_header(
    db: Session,
    form_data: FormHeaderCreate
) -> FormHeader:
    '''
        Creates a new form header along with its associated questions,
        multiple choice options, and flow rules.
    '''
    message = f'Attempting to create form header with code: {form_data.form_code}'
    logger.info(message)
    existing_form = db.query(FormHeader).filter(
        FormHeader.form_code == form_data.form_code
    ).first()
    if existing_form:
        raise RegisterAlreadyExistsError(
            detail = f'Form with this code: {form_data.form_code} already exists.'
        )
    db_form_header = create_record(
        db,
        FormHeader,
        form_data,
        extra_fields = {'creation_date': datetime.now()},
        exclude_relations = ['questions']
    )
    if db_form_header.id is None:
        raise ValueError('Failed to obtain ID for FormHeader. Cannot proceed with questions.')
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

@handle_service_errors('FORMS')
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
    form_header = get_record(db, FormHeader, form_id, eager_load_options)
    message = f'Form header {form_id} retrieved successfully.'
    logger.info(message)
    return form_header

@handle_service_errors('FORMS')
async def get_all_form_headers(
    db: Session,
    filters: FormFilters,
    skip: int = 0,
    limit: int = 100
) -> List[FormHeader]:
    '''
        Retrieves a list of all form headers with optional filters.
    '''
    message = f'Attempting to retrieve all form headers (skip: {skip}, limit: {limit}).'
    logger.info(message)
    query = db.query(FormHeader)
    if filters.company_id is not None:
        query = query.filter(FormHeader.company_id == filters.company_id)
    if filters.service_id is not None:
        query = query.filter(FormHeader.service_id == filters.service_id)
    if filters.form_code:
        query = query.filter(FormHeader.form_code == filters.form_code)
    if filters.status:
        query = query.filter(FormHeader.status == filters.status)
    if filters.name:
        query = query.filter(FormHeader.name.ilike(f"%{filters.name}%"))
    forms = query.offset(skip).limit(limit).all()
    if not forms:
        logger.warning('No form headers found with the specified criteria.')
    return forms

@handle_service_errors('FORMS')
@audit_event('FORMS', 'FormHeader', 'UPDATE')
async def update_form_header(
    db: Session,
    form_id: int,
    form_data: FormHeaderUpdate
) -> Tuple[FormHeader, Dict]:
    '''
        Updates an existing form header.
    '''
    message = f'Attempting to update form header with ID: {form_id}'
    logger.info(message)
    db_form_header = get_record(db, FormHeader, form_id)
    if form_data.form_code is not None and \
       form_data.form_code != db_form_header.form_code:
        existing_form_with_code = db.query(FormHeader).filter(
            FormHeader.form_code == form_data.form_code,
            FormHeader.id != form_id
        ).first()
        if existing_form_with_code:
            error_msg = f'''Cannot update form {form_id}: form_code
                    {form_data.form_code} already in use.'''
            logger.warning(error_msg)
            raise RegisterAlreadyExistsError(
               detail = error_msg
            )
    old_values = sqlalchemy_object_as_dict(db_form_header)

    updated_record = update_record(db, db_form_header, form_data,
                                    exclude_relations = ['questions'])
    db.commit()
    db.refresh(updated_record)
    message = f'Form header {form_id} updated successfully.'
    logger.info(message)
    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(updated_record)
    }
    return updated_record, auditable_data

@handle_service_errors('FORMS')
@audit_event('FORMS', 'FormHeader', 'DELETE')
async def delete_form_header(
    db: Session,
    form_id: int
) -> Tuple[int, Dict]:
    '''
        Deletes a form header by its ID.
    '''
    message = f'Attempting to delete form header with ID: {form_id}'
    logger.info(message)
    db_form = get_record(db, FormHeader, form_id)
    old_values = sqlalchemy_object_as_dict(db_form)
    delete_record(db, FormHeader, form_id)
    db.commit()
    message = f'Form header {form_id} deleted successfully.'
    logger.info(message)
    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }
    return form_id, auditable_data

# --- CRUD operations for QuestionDetail ---
@handle_service_errors('FORMS')
@audit_event('FORMS', 'QuestionDetail', 'CREATE')
async def create_question_detail(
    db: Session,
    form_id: int,
    question_data: QuestionDetailCreate
) -> QuestionDetail:
    '''
        Creates a new question detail for a specific form,
        including its multiple choice options and flow rules.
    '''
    message = f'''Attempting to create question for form ID: {form_id},
            question number: {question_data.question_number}'''
    logger.info(message)
    _ = get_record(db, FormHeader, form_id)
    db_question = create_record(
        db,
        QuestionDetail,
        question_data,
        extra_fields = {'form_id': form_id},
        exclude_relations = ['options', 'flow_rules']
    )
    if question_data.options:
        for opt_data in question_data.options:
            create_record(
                db,
                MultipleChoiceOption,
                opt_data,
                extra_fields = {'question_id': db_question.id}
            )
    if question_data.flow_rules:
        for flow_data in question_data.flow_rules:
            create_record(
                db,
                QuestionFlow,
                flow_data,
                extra_fields = {'form_detail_id': db_question.id}
            )
    db.commit()
    db.refresh(db_question)
    message = f'Question {db_question.id} created successfully for form {form_id}.'
    logger.info(message)

    return db_question

@handle_service_errors('FORMS')
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
    question = get_record(db, QuestionDetail, question_id, eager_load_options)
    message = f'Question detail {question_id} retrieved successfully.'
    logger.info(message)
    return question

@handle_service_errors('FORMS')
@audit_event('FORMS', 'QuestionDetail', 'UPDATE')
async def update_question_detail(
    db: Session,
    question_id: int,
    question_data: QuestionDetailUpdate
) -> Tuple[QuestionDetail, Dict]:
    '''
        Updates an existing question detail.
    '''
    message = f'Attempting to update question detail with ID: {question_id}'
    logger.info(message)
    db_question = get_record(db, QuestionDetail, question_id)
    old_values = sqlalchemy_object_as_dict(db_question)
    try:
        db_question = update_record(db, db_question, question_data)
        update_dict = question_data.model_dump(exclude_unset = True)
        if 'options' in update_dict and update_dict['options'] is not None:
            db.query(MultipleChoiceOption).filter(
                MultipleChoiceOption.question_id == question_id
            ).delete(synchronize_session = False)
            db.flush()
            for opt_data in update_dict['options']:
                create_record(
                    db,
                    MultipleChoiceOption,
                    opt_data,
                    extra_fields = {'question_id': question_id}
                )
        if 'flow_rules' in update_dict and update_dict['flow_rules'] is not None:
            db.query(QuestionFlow).filter(
                QuestionFlow.form_detail_id == question_id
            ).delete(synchronize_session = False)
            db.flush()
            for flow_data in update_dict['flow_rules']:
                create_record(
                    db,
                    QuestionFlow,
                    flow_data,
                    extra_fields = {'form_detail_id': question_id}
                )
        db.commit()
        db.refresh(db_question)
        message = f'Question detail {question_id} updated successfully.'
        logger.info(message)
        auditable_data = {
            'old_values': old_values,
            'new_values': sqlalchemy_object_as_dict(db_question)
        }
        return db_question, auditable_data
    except IntegrityError as e:
        raise RegisterAlreadyExistsError(
            detail = 'There is already a question with the same number on this form.'
        ) from e

@handle_service_errors('FORMS')
@audit_event('FORMS', 'QuestionDetail', 'DELETE')
async def delete_question_detail(
    db: Session,
    question_id: int
) -> Tuple[int, Dict]:
    '''
        Deletes a question detail by its ID.
    '''
    message = f'Attempting to delete question detail with ID: {question_id}'
    logger.info(message)
    db_question = get_record(db, QuestionDetail, question_id)
    old_values = sqlalchemy_object_as_dict(db_question)
    delete_record(db, QuestionDetail, question_id)
    db.commit()
    message = f'Question detail {question_id} deleted successfully.'
    logger.info(message)
    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }
    return question_id, auditable_data
