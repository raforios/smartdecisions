'''
    Responses Controller
    Handles the business logic for managing form responses, including
    temporary caching in DynamoDB and final persistence in MySQL.
'''
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import Request, UploadFile
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

# Import models
from models.responses import (
    Contact,
    FormResponse,
    Person
)
# Import FormHeader to get company_id
from models.forms import FormHeader

# Import schemas
from schemas.responses import (
    FormResponseFilters,
    FormResponseStatusFlow,
    PersonCreate,
    PersonListResponse,
    PersonResponse,
    PersonSearchFilters,
    PersonUpdate,
    StartFormSessionRequest,
    StartFormSessionResponse,
    SubmitAnswerRequest,
    NextQuestionResponse,
    TemporaryAnswer,
    CurrentFormSession,
    GetQuestionToModifyRequest,
    GetQuestionToModifyResponse,
    UpdateAnswerInSessionRequest,
    FinalizeFormRequest,
    FinalizeFormResponse,
    FormResponseDetailResponse,
    FormResponseSummaryResponse,
    FormResponseUpdate
)
# Import custom exceptions
from services.exceptions import (
    RegisterNotFoundError,
    InvalidInputError,
    ServiceUnavailableError
)
from services.crud import (
    get_record,
    get_all_records_paginated
)
# DynamoDB Service
from services.dynamodb import (
    get_session_by_id,
    save_session,
    delete_session_by_id
)
# Utility for handling service layer errors
from services.utils import _handle_files_service, get_current_time_gmt, handle_service_errors
# Import auxiliary functions from the new service layer
from services.responses import (
    create_person_logic,
    delete_person_logic,
    find_form_responses_by_filters,
    find_persons_by_filters,
    get_all_persons_logic,
    get_form_response_status_flow_logic,
    get_person_by_id_logic,
    get_question_details_for_form,
    get_next_question_number,
    get_question_response_data,
    create_person_and_contact,
    process_next_question_logic,
    prepare_next_question_response,
    update_form_response_data_logic,
    update_form_response_status_logic,
    update_person_logic,
    create_initial_form_response_record_logic,
    update_final_form_response_logic
)
# Configuration for DynamoDB TTL (e.g., 24 hours)
# This should ideally come from configuration (e.env or config service)
DYNAMODB_SESSION_TTL_HOURS = 24

# pylint: disable=too-many-arguments, too-many-positional-arguments
async def _initialize_dynamodb_session(
    session_id: str,
    form_id: int,
    first_question_number: int,
    user_id: int,
    contact_info: Dict[str, Any],
    form_response_id: int,
    service_id: int
) -> CurrentFormSession:
    '''
        Helper to initialize and save a new session in DynamoDB.
    '''
    ttl_timestamp = int(
        (datetime.now() + timedelta(hours = DYNAMODB_SESSION_TTL_HOURS)).timestamp()
    )
    initial_session_state = CurrentFormSession(
        session_id = session_id,
        form_id = form_id,
        current_question_number = first_question_number,
        answers = {},
        start_time = datetime.now(),
        ttl = ttl_timestamp,
        user_id = user_id,
        contact_info_id = contact_info['contact_id'],
        contact_temp_latitude = contact_info.get('latitude'),
        contact_temp_longitude = contact_info.get('longitude'),
        person_info_id = contact_info['person_id'],
        form_response_id = form_response_id,
        service_id = service_id
    )
    await save_session(initial_session_state.model_dump())
    return initial_session_state

async def _common_session_load_and_validate(
    session_id: str,
    db: Session
):
    '''
        Helper to load session from DynamoDB and perform common validations.
    '''
    session_state_dict = await get_session_by_id(session_id)
    if not session_state_dict:
        raise RegisterNotFoundError(
            detail = f'Session {session_id} not found or expired.'
        )
    current_session = CurrentFormSession(**session_state_dict)
    questions_map = await get_question_details_for_form(db, current_session.form_id)
    if not questions_map:
        raise RegisterNotFoundError(
            detail = f'Form ID {current_session.form_id} has no questions defined.'
        )
    return current_session, questions_map

@handle_service_errors('FORMS')
async def _handle_file_upload_logic(
    uploaded_file: UploadFile,
    auth_token: str,
    dynamic_path: str,
    person_id: int
) -> str:
    '''
        Handles the logic for uploading a file to the FILES microservice.
        This version uses the standardized _perform_request function.
    '''
    _, file_extension = os.path.splitext(uploaded_file.filename)
    current_time = get_current_time_gmt()
    timestamp_part = current_time.strftime('%Y%m%d-%H-%M-%S')
    new_file_name = f'{person_id}_{timestamp_part}{file_extension}'
    uploaded_file.filename = new_file_name

    response = await _handle_files_service(
        action = 'create',
        file_name = '',
        auth_token = auth_token,
        uploaded_file = uploaded_file,
        dynamic_path = dynamic_path
    )

    file_url = response.get('url')

    if not file_url:
        raise ServiceUnavailableError(detail = 'FILES service did not return a valid URL.')

    return file_url


# --- Controller Functions ---
@handle_service_errors('FORMS')
async def start_form_session(
    db: Session,
    session_data: StartFormSessionRequest,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> StartFormSessionResponse:
    '''
        Initiates a new form-filling session, creates person/contact records,
        and returns the first question.
    '''
    # 1. Create or find the Person and the Contact
    contact_info = await create_person_and_contact(db, session_data)

    # 2. Get the company_id from the FormHeader
    form_header = db.query(FormHeader).filter(FormHeader.id == session_data.form_id).first()
    if not form_header:
        raise RegisterNotFoundError(
            detail = f'FormHeader with ID {session_data.form_id} not found.'
        )
    company_id = form_header.company_id

    initial_data = {
        'form_id': session_data.form_id,
        'user_id': session_data.user_id,
        'affiliation_type': session_data.affiliation_type,
        'contact_id': contact_info['contact_id'],
        'person_id': contact_info['person_id'],
        'status': session_data.status, 
        'company_id': company_id,
        'service_id': session_data.service_id
    }

    # 3. Create the form header record in MySQL with the status from the frontend
    db_form_response = await create_initial_form_response_record_logic(
        db,
        initial_data
    )
    form_response_id = db_form_response.id

    # 4. Get form information
    questions_map = await get_question_details_for_form(db, session_data.form_id)
    first_question_number = min(questions_map.keys())
    first_question = questions_map[first_question_number]

    # 5. Initialize and save the session in DynamoDB with the new header ID
    session_id = str(uuid.uuid4())
    contact_details_for_session = {
        'contact_id': contact_info['contact_id'],
        'latitude': session_data.contact_data.latitude,
        'longitude': session_data.contact_data.longitude,
        'person_id': contact_info['person_id']
    }

    await _initialize_dynamodb_session(
        session_id = session_id,
        form_id = session_data.form_id,
        first_question_number = first_question_number,
        user_id = session_data.user_id,
        contact_info = contact_details_for_session,
        form_response_id = form_response_id,
        service_id = session_data.service_id
    )

    db.commit()

    return StartFormSessionResponse(
        session_id = session_id,
        form_id = session_data.form_id,
        form_response_id = form_response_id,
        affiliation_type = session_data.affiliation_type,
        status = session_data.status,
        **get_question_response_data(first_question)
    )

# pylint: disable=too-many-arguments, too-many-positional-arguments, too-many-locals
async def submit_answer_and_get_next_question(
    db: Session,
    answer_data: SubmitAnswerRequest,
    auth_token: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    uploaded_file: Optional[UploadFile] = None
) -> NextQuestionResponse:
    '''
        Submits an answer for the current question, updates the session cache,
        and determines the next question based on flow rules.
    '''
    current_session, questions_map = await _common_session_load_and_validate(
        answer_data.session_id, db)
    submitted_question_detail = questions_map.get(answer_data.question_number)
    if not submitted_question_detail:
        raise RegisterNotFoundError(
            detail = f'''Question number {answer_data.question_number} not found
                    in form {current_session.form_id}.'''
        )
    if submitted_question_detail.response_type == 'FILE_UPLOAD':
        if not uploaded_file:
            raise InvalidInputError(detail = 'File upload question requires a file.')

        form_header = db.query(FormHeader).filter(
            FormHeader.id == current_session.form_id
        ).first()

        if not form_header:
            raise RegisterNotFoundError(
                detail = f'FormHeader with ID {current_session.form_id} not found.'
            )

        company_id = form_header.company_id
        person_id = current_session.person_info_id
        service_id = current_session.service_id

        dynamic_path = f'{company_id}/{service_id}/{person_id}'

        answer_data.answer_value = await _handle_file_upload_logic(
            uploaded_file,
            auth_token,
            dynamic_path,
            person_id
        )

    temp_answer = TemporaryAnswer(
        question_id = submitted_question_detail.id,
        question_number = submitted_question_detail.question_number,
        answer_value = answer_data.answer_value,
        response_type = submitted_question_detail.response_type
    )
    current_session.answers[str(answer_data.question_number)] = temp_answer
    next_question_number = await get_next_question_number(
        current_question_number = answer_data.question_number,
        answer_value = answer_data.answer_value,
        questions_map = questions_map
    )
    process_result = await process_next_question_logic(
        current_session, next_question_number, questions_map
    )
    next_question = process_result['next_question']
    is_form_complete = process_result['is_form_complete']
    message_response = process_result['message_response']
    current_session.ttl = int(
        (datetime.now() + timedelta(hours = DYNAMODB_SESSION_TTL_HOURS)).timestamp()
    )
    await save_session(current_session.model_dump())
    return NextQuestionResponse(
        **prepare_next_question_response(
            current_session, next_question, is_form_complete, message_response)
    )

@handle_service_errors('FORMS')
async def get_question_to_modify(
    db: Session,
    request_data: GetQuestionToModifyRequest,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> GetQuestionToModifyResponse:
    '''
        Retrieves a specific question and its current answer from a session for modification.
    '''
    current_session, questions_map = await _common_session_load_and_validate(
        request_data.session_id, db)
    target_question = questions_map.get(request_data.question_number)
    if not target_question:
        raise RegisterNotFoundError(
            detail = f'''Question number {request_data.question_number} not found in
                    form {current_session.form_id}.'''
        )
    current_answer_obj = current_session.answers.get(str(request_data.question_number))
    current_answer_value = current_answer_obj.answer_value if current_answer_obj else None
    response_data = {
        'session_id': current_session.session_id,
        'question_number': target_question.question_number,
        'question_content': target_question.content,
        'response_type': target_question.response_type,
        'current_answer': current_answer_value,
        'options': None,
        'message': 'Question retrieved for modification.'
    }
    if target_question.response_type == 'multiple_choice' and target_question.options:
        response_data['options'] = [
            {'option_text': opt.option_text, 'order': opt.order}
            for opt in sorted(target_question.options, key=lambda o: o.order)
        ]
    return GetQuestionToModifyResponse(**response_data)

@handle_service_errors('FORMS')
async def update_answer_in_session(
    db: Session,
    update_data: UpdateAnswerInSessionRequest,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> NextQuestionResponse:
    '''
        Updates the answer for a specific question within a form session in DynamoDB.
        This also re-evaluates the flow from that point.
    '''
    current_session, questions_map = await _common_session_load_and_validate(
        update_data.session_id, db)
    target_question_detail = questions_map.get(update_data.question_number)
    if not target_question_detail:
        raise RegisterNotFoundError(
            detail = f'''Question number {update_data.question_number} not found
                in form {current_session.form_id}.'''
        )
    temp_answer = TemporaryAnswer(
        question_id = target_question_detail.id,
        question_number = target_question_detail.question_number,
        answer_value = update_data.new_answer_value,
        response_type = target_question_detail.response_type
    )
    current_session.answers[str(update_data.question_number)] = temp_answer
    next_question_number = await get_next_question_number(
        current_question_number = update_data.question_number,
        answer_value = update_data.new_answer_value,
        questions_map = questions_map
    )
    process_result = await process_next_question_logic(
        current_session, next_question_number, questions_map
    )
    next_question = process_result['next_question']
    is_form_complete = process_result['is_form_complete']
    message_response = process_result['message_response']
    current_session.ttl = int(
        (datetime.now() + timedelta(hours = DYNAMODB_SESSION_TTL_HOURS)).timestamp()
    )
    await save_session(current_session.model_dump())
    return NextQuestionResponse(
        **prepare_next_question_response(
            current_session, next_question, is_form_complete, message_response)
    )

@handle_service_errors('FORMS')
async def finalize_form_session(
    db: Session,
    finalize_data: FinalizeFormRequest,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> FinalizeFormResponse:
    '''
        Finalizes a form session, persists all answers to MySQL, and clears the cache.
    '''
    current_session, questions_map = await _common_session_load_and_validate(
        finalize_data.session_id, db)
    if not current_session.answers:
        raise InvalidInputError(detail = 'Cannot finalize an empty form session.')

    # Get the company_id from the FormHeader
    form_header = db.query(FormHeader).filter(FormHeader.id == current_session.form_id).first()
    if not form_header:
        raise RegisterNotFoundError(
            detail = f'FormHeader with ID {current_session.form_id} not found.'
        )
    company_id = form_header.company_id

    # Get the latest affiliation_number for this company and form
    latest_affiliation = db.query(func.max(FormResponse.affiliation_number)).filter(
        FormResponse.form_id == current_session.form_id,
        FormResponse.company_id == company_id
    ).scalar()

    # Calculate the new affiliation number. If none exists, it's 1.
    new_affiliation_number = (latest_affiliation or 0) + 1
    status = finalize_data.status

    db_form_response = get_record(db, FormResponse, current_session.form_response_id)
    if not db_form_response:
        raise RegisterNotFoundError(
            detail = f"Form response with ID {current_session.form_response_id} not found."
        )

    # MODIFIED: The logic to create the final records has been moved to a new service function.
    updated_form_response = await update_final_form_response_logic(
        db,
        current_session,
        questions_map,
        company_id,
        new_affiliation_number,
        status
    )

    await delete_session_by_id(current_session.session_id)
    return FinalizeFormResponse(
        form_response_id = updated_form_response.id,
        affiliation_number = updated_form_response.affiliation_number
    )

@handle_service_errors('FORMS')
async def get_form_response_by_id(
    db: Session,
    form_response_id: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> FormResponseDetailResponse:
    '''
        Retrieves a completed form response by its ID, including all associated answers,
        contact, and person details.
    '''
    eager_load_options = [
        joinedload(FormResponse.answers),
        joinedload(FormResponse.contact).joinedload(Contact.person),
        joinedload(FormResponse.person),
        joinedload(FormResponse.status_flow)
    ]
    db_form_response = get_record(db, FormResponse, form_response_id, eager_load_options)
    return FormResponseDetailResponse.model_validate(db_form_response, from_attributes = True)

@handle_service_errors('FORMS')
async def get_all_form_responses(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    skip: int = 0,
    limit: int = 100,
    filters: FormResponseFilters = None
) -> List[FormResponseSummaryResponse]:
    '''
        Retrieves a paginated list of all completed form responses, with optional filtering.
    '''
    if not filters:
        responses, _ = get_all_records_paginated(db, FormResponse, skip, limit)
        return [FormResponseSummaryResponse.model_validate(r) for r in responses]

    # Usar el nuevo servicio de filtrado
    responses, _ = await find_form_responses_by_filters(
        db, filters, skip, limit
    )

    return [FormResponseSummaryResponse.model_validate(r) for r in responses]

async def update_form_response_status(
    db: Session,
    form_response_id: int,
    status_data: FormResponseUpdate,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> FormResponseDetailResponse:
    '''
        Updates the status of an existing completed form response.
    '''
    updated_response = await update_form_response_status_logic(
        db,
        form_response_id,
        status_data
    )

    # Eager load for the response schema
    return await get_form_response_by_id(
        db = db,
        form_response_id = updated_response.id,
        request = request,
        current_user = current_user
    )

@handle_service_errors('FORMS')
async def update_form_response_data(
    db: Session,
    form_response_id: int,
    form_response_data: FormResponseUpdate,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> FormResponse:
    '''
        Controller function to update a form response record.
    '''
    updated_response = await update_form_response_data_logic(
        db,
        form_response_id,
        form_response_data
    )
    return updated_response

@handle_service_errors('FORMS')
async def get_form_response_status_flow_controller(
    db: Session,
    form_response_id: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> List[FormResponseStatusFlow]:
    '''
        Retrieves the status flow history for a given form response.
    '''
    return await get_form_response_status_flow_logic(db, form_response_id)

@handle_service_errors('FORMS')
async def create_person(
    db: Session,
    person_data: PersonCreate,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PersonResponse:
    '''
        Creates a new person record in the database.
    '''
    db_person = await create_person_logic(db, person_data)
    return PersonResponse.model_validate(db_person, from_attributes = True)

@handle_service_errors('FORMS')
async def get_person_by_id(
    db: Session,
    person_id: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PersonResponse:
    '''
        Retrieves a person record by its ID.
    '''
    return await get_person_by_id_logic(db, person_id)

@handle_service_errors('PERSONS')
async def search_persons(
    db: Session,
    filters: PersonSearchFilters,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
) -> List[PersonResponse]:
    '''
        Controller to process the search request and fetch matching person records.
    '''
    persons = await find_persons_by_filters(db, filters)
    return [PersonResponse.model_validate(person) for person in persons]

@handle_service_errors('FORMS')
async def get_all_persons(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    skip: int = 0,
    limit: int = 100
) -> PersonListResponse:
    '''
        Retrieves a paginated list of all person records.
    '''
    persons = await get_all_persons_logic(db, skip, limit)
    total_count = db.query(Person).count()
    return PersonListResponse(items = persons, total = total_count)

@handle_service_errors('FORMS')
async def update_person(
    db: Session,
    person_id: int,
    person_data: PersonUpdate,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
) -> PersonResponse:
    '''
        Updates an existing person record by ID.
    '''
    updated_person = await update_person_logic(db, person_id, person_data)
    return PersonResponse.model_validate(updated_person, from_attributes = True)

@handle_service_errors('FORMS')
async def delete_person(
    db: Session,
    person_id: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
) -> Dict[str, str]:
    '''
        Deletes a person record by ID.
    '''
    result = await delete_person_logic(db, person_id)

    return {
        'message': f'Person with ID: {person_id} deleted successfully.',
        'id': result
    }
