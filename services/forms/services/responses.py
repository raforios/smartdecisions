'''
    Business logic services for the Forms microservice.
'''
from typing import Dict, Any, List, Optional
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
from services.utils import handle_service_errors

@handle_service_errors
def get_question_details_for_form(
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

def get_next_question_number(
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

def get_question_response_data(question: QuestionDetail) -> Dict[str, Any]:
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

@handle_service_errors
def create_person_and_contact(
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
    return {'person_id': db_person.id, 'contact_id': db_contact.id}

def process_next_question_logic(
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

@handle_service_errors
def create_form_response_and_answers(
    db: Session,
    current_session: CurrentFormSession,
    questions_map: Dict[int, QuestionDetail],
    company_id: Optional[int],
    affiliation_number: Optional[int]
):
    '''
        Helper to persist form response and answers to MySQL.
    '''
    question_id_map = {q.question_number: q.id for q in questions_map.values()}
    db_form_response = FormResponse(
        form_id = current_session.form_id,
        user_id = current_session.user_id,
        contact_id = current_session.contact_info_id,
        person_id = current_session.person_info_id,
        company_id = company_id,
        affiliation_number = affiliation_number
    )
    db.add(db_form_response)
    db.flush()
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
            form_response_id = db_form_response.id,
            question_id = question_db_id,
            answer_value = temp_ans.answer_value
        ))
    db.add_all(db_answers)
    db.commit()
    return db_form_response.id

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

@handle_service_errors
def update_form_response_logic(
    db: Session,
    form_response_id: int,
    status_data: FormResponseUpdate
) -> FormResponse:
    '''
        Business logic to update a form response's status and record the change in the flow table.
    '''
    db_form_response = get_record(db, FormResponse, form_response_id)
    initial_status = db_form_response.status

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

    return updated_response

@handle_service_errors
def create_person_logic(
    db: Session,
    person_data: PersonCreate
) -> Person:
    '''
        Business logic to create a new person record.
        Checks for existing unique fields (e.g., email, identification_number)
        to prevent duplicates.
    '''
    # Se realiza una comprobación de duplicados para los campos únicos
    existing_person = db.query(Person).filter(
        (Person.email == person_data.email) |
        (Person.phone_number == person_data.phone_number) |
        (Person.identification_number == person_data.identification_number)
    ).first()

    if existing_person:
        raise InvalidInputError(
            detail = '''A person with this email, phone number, or identification number
                    already exists.'''
        )

    try:
        db_person = create_record(db, Person, person_data)
        db.commit()
        db.refresh(db_person)
        return db_person
    except IntegrityError as e:
        db.rollback()
        raise InvalidInputError(
            detail = 'Failed to create person due to a data integrity issue.'
        ) from e

@handle_service_errors
def get_person_by_id_logic(db: Session, person_id: int) -> Person:
    '''
        Business logic to retrieve a person record by ID.
    '''
    db_person = get_record(db, Person, person_id)
    return db_person

@handle_service_errors
def get_all_persons_logic(db: Session, skip: int, limit: int) -> List[Person]:
    '''
        Business logic to retrieve a paginated list of all person records.
    '''
    return get_all_records_paginated(db, Person, skip, limit)

@handle_service_errors
def update_person_logic(db: Session, person_id: int, person_data: PersonUpdate) -> Person:
    '''
        Business logic to update an existing person record.
    '''
    db_person = get_record(db, Person, person_id)
    # Aquí podríamos añadir validaciones adicionales si es necesario
    updated_person = update_record(db, db_person, person_data)
    db.commit()
    db.refresh(updated_person)
    return updated_person

@handle_service_errors
def delete_person_logic(db: Session, person_id: int) -> Dict[str, str]:
    '''
        Business logic to delete a person record by ID.
    '''
    db_person = get_record(db, Person, person_id)
    delete_record(db, db_person, person_id)
    db.commit()
    return {'message': f'Person with ID {person_id} has been successfully deleted.'}
