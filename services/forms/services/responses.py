'''
    Business logic services for the Forms microservice.
'''
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from models.forms import QuestionDetail
from models.responses import (
    FormResponseFlow,
    Person,
    Contact,
    FormResponse,
    FormAnswer
)
from schemas.responses import (
    FormResponseFlowCreate,
    FormResponseUpdate,
    PersonCreate,
    PersonSearchFilters,
    PersonUpdate,
    StartFormSessionRequest,
    CurrentFormSession
)
from services.exceptions import (
    RegisterNotFoundError,
    InvalidInputError
)
from services.crud import (
    create_record,
    delete_record,
    get_all_records_paginated,
    get_record,
    update_record
)
from services.logger_config import custom_logger as logger
from services.utils import (
    get_current_time_gmt,
    handle_service_errors,
    audit_event,
    sqlalchemy_object_as_dict
)

async def get_question_details_for_form(
    db: Session,
    form_id: int
) -> Dict[int, QuestionDetail]:
    '''
        Helper function to fetch all question details for a given form.
    '''
    questions = db.query(QuestionDetail)\
                  .filter(QuestionDetail.form_id == form_id)\
                  .options(joinedload(QuestionDetail.options),
                           joinedload(QuestionDetail.flow_rules))\
                  .order_by(QuestionDetail.question_number)\
                  .all()
    if not questions:
        raise RegisterNotFoundError(
            detail = f'No questions found for form ID: {form_id}'
        )
    questions_map = {q.question_number: q for q in questions}
    return questions_map

async def get_next_question_number(
    current_question_number: int,
    answer_value: Optional[str],
    questions_map: Dict[int, QuestionDetail]
) -> Optional[int]:
    '''
        Determines the next question number based on flow rules or sequential order.
    '''
    current_question = questions_map.get(current_question_number)
    if not current_question:
        return None
    if current_question.flow_rules:
        for rule in current_question.flow_rules:
            if rule.answer_value == answer_value:
                return rule.next_question_number
        for rule in current_question.flow_rules:
            if rule.is_default_sequential:
                return rule.next_question_number
    sorted_question_numbers = sorted(questions_map.keys())
    try:
        current_index = sorted_question_numbers.index(current_question_number)
        if current_index + 1 < len(sorted_question_numbers):
            return sorted_question_numbers[current_index + 1]
    except ValueError:
        pass
    return None

def get_question_response_data(
    question: QuestionDetail
) -> Dict[str, Any]:
    '''
        Helper to format question data for NextQuestionResponse.
    '''
    options_data = None
    if question.response_type == 'multiple_choice' and question.options:
        options_data = [
            {'option_text': opt.option_text, 'order': opt.order}
            for opt in sorted(question.options, key = lambda o: o.order)
        ]
    return {
        'question_number': question.question_number,
        'question_content': question.content,
        'response_type': question.response_type,
        'options': options_data
    }

@handle_service_errors('FORMS')
# @audit_event('FORMS', 'Person', 'CREATE')
async def create_person_and_contact(
    db: Session,
    session_data: StartFormSessionRequest
) -> Dict[str, Any]:
    '''
        Helper to create or find Person and create Contact records.
    '''
    person_data = session_data.person_data
    contact_data = session_data.contact_data
    existing_person = db.query(Person).filter(
        (Person.identification_number == person_data.identification_number)
    ).first()
    if existing_person:
        db_person = existing_person
    else:
        try:
            db_person = create_record(db, Person, person_data)
        except IntegrityError as e:
            raise InvalidInputError(
                detail = 'Person creation failed due to data conflict.'
            ) from e
    extra_fields = {
        'person_id': db_person.id,
        'executed_route_point_id': session_data.executed_route_point_id
    }
    db_contact = create_record(db, Contact, contact_data, extra_fields = extra_fields)
    db.flush()
    result = {'person_id': db_person.id, 'contact_id': db_contact.id}

    return result

async def process_next_question_logic(
    current_session: CurrentFormSession,
    next_question_number: Optional[int],
    questions_map: Dict[int, QuestionDetail]
) -> Dict[str, Any]:
    '''
        Helper to determine next question and form completion status.
    '''
    next_question = None
    is_form_complete = False
    message_response = 'Next question available.'
    if next_question_number is not None:
        next_question = questions_map.get(next_question_number)
        if not next_question:
            is_form_complete = True
            message_response = 'Form completed (flow rule to non-existent question).'
            current_session.current_question_number = -1
        else:
            current_session.current_question_number = next_question.question_number
    else:
        is_form_complete = True
        message_response = 'Form completed. All questions answered or no next question found.'
        current_session.current_question_number = -1
    return {
        'next_question': next_question,
        'is_form_complete': is_form_complete,
        'message_response': message_response
    }

@handle_service_errors('FORMS')
@audit_event('FORMS', 'FormResponse', 'CREATE')
async def create_initial_form_response_record_logic(
    db: Session,
    inital_data: Dict
) -> FormResponse:
    '''
        Creates the initial form response record in MySQL at the start of the session.
        Returns the ID of the new record.
    '''
    db_form_response = FormResponse(
        form_id = inital_data['form_id'],
        user_id = inital_data['user_id'],
        affiliation_type = inital_data['affiliation_type'],
        contact_id = inital_data['contact_id'],
        person_id = inital_data['person_id'],
        status = inital_data['status'],
        company_id = inital_data['company_id']
    )
    db.add(db_form_response)
    db.flush()

    db.commit()

    db.refresh(db_form_response)

    return db_form_response

@handle_service_errors('FORMS')
@audit_event('FORMS', 'FormResponse', 'UPDATE')
# pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
async def update_final_form_response_logic(
    db: Session,
    current_session: CurrentFormSession,
    questions_map: Dict[int, QuestionDetail],
    company_id: Optional[int],
    affiliation_number: int,
    status: Optional[str]
) -> Tuple[FormResponse, Dict]:
    '''
        Updates the form header and persists all answers from the session cache to MySQL.
    '''

    # 1. Update the existing FormResponse header record
    db_form_response = get_record(db, FormResponse, current_session.form_response_id)
    old_values = sqlalchemy_object_as_dict(db_form_response)

    update_data = FormResponseUpdate(
        company_id = company_id,
        affiliation_number = affiliation_number,
        user_id = current_session.user_id,
        status = status,
    )

    updated_form_response = update_record(db, db_form_response, update_data)
    db.flush()

    # 2. Persist all individual answers
    question_id_map = {q.question_number: q.id for q in questions_map.values()}
    db_answers = []
    for q_num_str, temp_ans in current_session.answers.items():
        question_db_id = question_id_map.get(int(q_num_str))
        if not question_db_id:
            message = f'''Question number {q_num_str} from session
                        {current_session.session_id} not found in form
                        {current_session.form_id} definitions. Skipping this answer.'''
            logger.warning(message)
            continue
        db_answers.append(FormAnswer(
            form_response_id = updated_form_response.id,
            question_id = question_db_id,
            answer_value = temp_ans.answer_value
        ))
    db.add_all(db_answers)

    # 3. Add the logic to update the Person record
    person_record = get_record(db, Person, updated_form_response.person_id)
    if person_record:
        person_update_data = PersonUpdate(
            is_affiliated = True,
            affiliation_date = get_current_time_gmt(),
            affiliation_user_id = updated_form_response.user_id
        )
        update_record(db, person_record, person_update_data)

    db.commit()
    db.refresh(updated_form_response)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(updated_form_response)
    }

    return updated_form_response, auditable_data

def prepare_next_question_response(
    current_session: CurrentFormSession,
    next_question: Optional[QuestionDetail],
    is_form_complete: bool,
    message_response: str
) -> Dict[str, Any]:
    '''
        Helper to construct the NextQuestionResponse object.
    '''
    current_answers_for_response = {}
    for qn_key in current_session.answers:
        current_answers_for_response[qn_key] = current_session.answers[qn_key]\
                                            .model_dump(exclude_unset = True)
    response_data = {
        'session_id': current_session.session_id,
        'is_form_complete': is_form_complete,
        'message': message_response,
        'current_answers': current_answers_for_response
    }
    if next_question:
        response_data.update(get_question_response_data(next_question))
    return response_data

@handle_service_errors('FORMS')
@audit_event('FORMS', 'FormResponseFlow', 'UPDATE')
async def update_form_response_status_logic(
    db: Session,
    form_response_id: int,
    status_data: FormResponseUpdate
) -> Tuple[FormResponse, Dict]:
    '''
        Business logic to update a form response's status and record the change in the flow table.
    '''
    db_form_response = get_record(db, FormResponse, form_response_id)
    initial_status = db_form_response.status
    old_values = sqlalchemy_object_as_dict(db_form_response)

    if status_data.status == 'REJECTED' and not status_data.rejection_reason:
        raise InvalidInputError(
            detail = 'Rejection reason is required for REJECTED status.'
        )

    updated_response = update_record(db, db_form_response, status_data)

    flow_record_data = FormResponseFlowCreate(
        form_response_id = form_response_id,
        user_id = status_data.user_id,
        initial_status = initial_status,
        next_status = status_data.status,
        observations = status_data.observations
    )
    create_record(db, FormResponseFlow, flow_record_data)

    db.commit()
    db.refresh(updated_response)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(updated_response)
    }

    return updated_response, auditable_data

@handle_service_errors('FORMS')
@audit_event('FORMS', 'FormResponse', 'UPDATE')
async def update_form_response_data_logic(
    db: Session,
    form_response_id: int,
    update_data: FormResponseUpdate
) -> Tuple[FormResponse, Dict]:
    '''
        Updates an existing form response record in the database.        
    '''
    db_form_response = get_record(db, FormResponse, form_response_id)
    if not db_form_response:
        raise RegisterNotFoundError(
            detail = f"Form response with ID {form_response_id} not found."
        )
    old_values = sqlalchemy_object_as_dict(db_form_response)

    update_form_response = update_record(db, db_form_response, update_data)
    db.commit()
    db.refresh(update_form_response)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(update_form_response)
    }

    return update_form_response, auditable_data

@handle_service_errors('FORMS')
async def get_form_response_status_flow_logic(
    db: Session,
    form_response_id: int
) -> List[FormResponseFlow]:
    '''
        Retrieves the status flow for a specific form response ID.
    '''
    return db.query(FormResponseFlow).filter(
        FormResponseFlow.form_response_id == form_response_id
    ).order_by(FormResponseFlow.date_time).all()

@handle_service_errors('FORMS')
@audit_event('FORMS', 'Person', 'CREATE')
async def create_person_logic(
    db: Session,
    person_data: PersonCreate
) -> Person:
    '''
        Business logic to create a new person record.
        Checks for existing unique fields (e.g., email, identification_number)
        to prevent duplicates.
    '''
    existing_person = db.query(Person).filter(
        (Person.identification_number == person_data.identification_number)
    ).first()

    if existing_person:
        raise InvalidInputError(
            detail = 'A person with this identification number already exists.'
        )

    db_person = create_record(db, Person, person_data)
    db.commit()
    db.refresh(db_person)

    return db_person

@handle_service_errors('FORMS')
async def get_person_by_id_logic(
    db: Session,
    person_id: int
) -> Person:
    '''
        Business logic to retrieve a person record by ID.
    '''
    db_person = get_record(db, Person, person_id)
    return db_person

async def find_persons_by_filters(
    db: Session,
    filters: PersonSearchFilters
) -> List[Person]:
    '''
        Service to search for person records based on various filters.
    '''
    query = db.query(Person)
    conditions = []

    if filters.identification_number:
        conditions.append(Person.identification_number == filters.identification_number)
    if filters.first_name:
        conditions.append(Person.first_name.ilike(f'%{filters.first_name}%'))
    if filters.paternal_last_name:
        conditions.append(Person.paternal_last_name.ilike(f'%{filters.paternal_last_name}%'))
    if filters.maternal_last_name:
        conditions.append(Person.maternal_last_name.ilike(f'%{filters.maternal_last_name}%'))
    if filters.phone_number:
        conditions.append(or_(
            Person.phone_number == filters.phone_number,
            Person.phone_number_2 == filters.phone_number
        ))
    if filters.email:
        conditions.append(Person.email == filters.email)

    if conditions:
        query = query.filter(and_(*conditions))

    return query.all()

@handle_service_errors('FORMS')
async def get_all_persons_logic(
    db: Session,
    skip: int,
    limit: int
) -> List[Person]:
    '''
        Business logic to retrieve a paginated list of all person records.
    '''
    return get_all_records_paginated(db, Person, skip, limit)

@handle_service_errors('FORMS')
@audit_event('FORMS', 'Person', 'UPDATE')
async def update_person_logic(
    db: Session,
    person_id: int,
    person_data: PersonUpdate
) -> Tuple[Person, Dict]:
    '''
        Business logic to update an existing person record.
    '''
    db_person = get_record(db, Person, person_id)
    old_values = sqlalchemy_object_as_dict(db_person)

    updated_person = update_record(db, db_person, person_data)
    db.commit()
    db.refresh(updated_person)

    auditable_data = {
        'old_values': old_values,
        'new_values': sqlalchemy_object_as_dict(updated_person)
    }

    return updated_person, auditable_data

@handle_service_errors('FORMS')
@audit_event('FORMS', 'Person', 'DELETE')
async def delete_person_logic(
    db: Session,
    person_id: int
) -> Tuple[Dict[str, str], Dict]:
    '''
        Business logic to delete a person record by ID.
    '''
    db_person = get_record(db, Person, person_id)
    old_values = sqlalchemy_object_as_dict(db_person)

    try:
        delete_record(db, Person, person_id)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        error_msg = f'Deletion failed for Person ID {person_id}. Record is in use.'
        logger.error(error_msg)
        raise InvalidInputError(
            detail = 'The person record cannot be deleted because it is referenced by data.'
        ) from e

    message = f'Person with ID {person_id} has been successfully deleted.'
    logger.info(message)

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return person_id, auditable_data
