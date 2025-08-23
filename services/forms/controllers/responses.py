'''
    Responses Controller
    Handles the business logic for managing form responses, including
    temporary caching in DynamoDB and final persistence in MySQL.
'''
import mimetypes
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import httpx
from fastapi import UploadFile
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from dotenv import dotenv_values

# Import models
from models.responses import (
    Contact,
    FormResponse
)
# Import schemas
from schemas.responses import (
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
    FormResponseUpdate,
)
# Import custom exceptions
from services.exceptions import (
    RegisterNotFoundError,
    InvalidInputError,
    ServiceUnavailableError
)
from services.crud import (
    get_record,
    update_record,
    get_all_records_paginated
)
# New: DynamoDB Service
from services.dynamodb import (
    get_session_by_id,
    save_session,
    delete_session_by_id
)
# New: Utility for handling service layer errors
from services.utils import handle_service_errors
# New: Import auxiliary functions from the new service layer
from services.responses import (
    get_question_details_for_form,
    get_next_question_number,
    get_question_response_data,
    create_person_and_contact,
    process_next_question_logic,
    create_form_response_and_answers,
    prepare_next_question_response,
)
# Configuration for DynamoDB TTL (e.g., 24 hours)
# This should ideally come from configuration (e.env or config service)
DYNAMODB_SESSION_TTL_HOURS = 24

_LOCAL_ENV_PARAMS = dotenv_values('.env') if os.path.exists('.env') else {}

async def _initialize_dynamodb_session(
    session_id: str,
    form_id: int,
    first_question_number: int,
    user_id: int,
    contact_info: Dict[str, Any]
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
        person_info_id = contact_info['person_info_id']
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
    questions_map = get_question_details_for_form(db, current_session.form_id)
    if not questions_map:
        raise RegisterNotFoundError(
            detail = f'Form ID {current_session.form_id} has no questions defined.'
        )
    return current_session, questions_map

async def _handle_file_upload_logic(
    uploaded_file: UploadFile,
    auth_token: str
) -> str:
    '''
    Handles the logic for uploading a file to the FILES microservice.
    This version expects a standard file upload (multipart/form-data).

    Args:
        uploaded_file (UploadFile): The file object from the FastAPI request.
        auth_header (str): The raw 'Authorization' header string, e.g., 'Bearer abc...'.

    Returns:
        str: The S3 URL of the uploaded file.

    Raises:
        ServiceUnavailableError: If the FILES service is not available or returns an error.
    '''
    try:
        file_content_bytes = await uploaded_file.read()

        files_service_url = os.environ.get('FILES_SERVICE_URL') or \
                            _LOCAL_ENV_PARAMS.get('FILES_SERVICE_URL')

        if not files_service_url:
            raise ServiceUnavailableError(
                detail = 'FILES_SERVICE_URL environment variable is not set.'
            )
        upload_endpoint = f'{files_service_url}/v1/s3/upload'

        mime_type, _ = mimetypes.guess_type(uploaded_file.filename)
        if not mime_type:
            mime_type = 'application/octet-stream'
        async with httpx.AsyncClient() as client:
            files = {'file': (uploaded_file.filename, file_content_bytes, mime_type)}
            data = {
                'bucket_name': os.environ.get('BUCKET_NAME') or \
                        _LOCAL_ENV_PARAMS.get('BUCKET_NAME'),
                'file_path': os.environ.get('BUCKET_PATH') or \
                        _LOCAL_ENV_PARAMS.get('BUCKET_PATH')
            }
            headers = {'Authorization': f'{auth_token}'}
            response = await client.post(
                upload_endpoint,
                files = files,
                data = data,
                headers = headers
            )
            response.raise_for_status()
            s3_upload_response = response.json()
            file_url = s3_upload_response.get('url')
            if not file_url:
                raise ServiceUnavailableError(detail = 'FILES service did not return a valid URL.')
            return file_url
    except httpx.HTTPStatusError as e:
        message = f'''Failed to upload file to FILES service. Status:
                    {e.response.status_code}, Detail: {e.response.text}'''
        raise ServiceUnavailableError(detail = message) from e
    except Exception as e:
        raise ServiceUnavailableError(
            detail = f'Unexpected error during file upload to FILES service: {e}'
        ) from e

# --- Controller Functions ---
@handle_service_errors
async def start_form_session(
    db: Session,
    session_data: StartFormSessionRequest,
) -> StartFormSessionResponse:
    '''
        Initiates a new form-filling session, creates person/contact records,
        and returns the first question.
    '''
    contact_info = create_person_and_contact(db, session_data)
    questions_map = get_question_details_for_form(db, session_data.form_id)
    first_question_number = min(questions_map.keys())
    first_question = questions_map[first_question_number]
    session_id = str(uuid.uuid4())
    contact_details_for_session = {
        'contact_id': contact_info['contact_id'],
        'latitude': session_data.contact_data.latitude,
        'longitude': session_data.contact_data.longitude,
        'person_info_id': contact_info['person_id']
    }
    await _initialize_dynamodb_session(
        session_id = session_id,
        form_id = session_data.form_id,
        first_question_number = first_question_number,
        user_id = session_data.user_id,
        contact_info = contact_details_for_session
    )
    db.commit()
    return StartFormSessionResponse(
        session_id = session_id,
        form_id = session_data.form_id,
        **get_question_response_data(first_question)
    )

@handle_service_errors
async def submit_answer_and_get_next_question(
    db: Session,
    answer_data: SubmitAnswerRequest,
    auth_token: str,
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
        answer_data.answer_value = await _handle_file_upload_logic(
            uploaded_file, auth_token
        )
    temp_answer = TemporaryAnswer(
        question_id = submitted_question_detail.id,
        question_number = submitted_question_detail.question_number,
        answer_value = answer_data.answer_value,
        response_type = submitted_question_detail.response_type
    )
    current_session.answers[str(answer_data.question_number)] = temp_answer
    next_question_number = get_next_question_number(
        current_question_number = answer_data.question_number,
        answer_value = answer_data.answer_value,
        questions_map = questions_map
    )
    process_result = process_next_question_logic(
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

@handle_service_errors
async def get_question_to_modify(
    db: Session,
    request_data: GetQuestionToModifyRequest,
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

@handle_service_errors
async def update_answer_in_session(
    db: Session,
    update_data: UpdateAnswerInSessionRequest,
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
    next_question_number = get_next_question_number(
        current_question_number = update_data.question_number,
        answer_value = update_data.new_answer_value,
        questions_map = questions_map
    )
    process_result = process_next_question_logic(
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

@handle_service_errors
async def finalize_form_session(
    db: Session,
    finalize_data: FinalizeFormRequest,
) -> FinalizeFormResponse:
    '''
        Finalizes a form session, persists all answers to MySQL, and clears the cache.
    '''
    current_session, questions_map = await _common_session_load_and_validate(
        finalize_data.session_id, db)
    if not current_session.answers:
        raise InvalidInputError(detail = 'Cannot finalize an empty form session.')
    form_response_id = create_form_response_and_answers(
        db, current_session, questions_map
    )
    await delete_session_by_id(current_session.session_id)
    return FinalizeFormResponse(form_response_id = form_response_id)

@handle_service_errors
def get_form_response_by_id(
    db: Session,
    form_response_id: int,
) -> FormResponseDetailResponse:
    '''
        Retrieves a completed form response by its ID, including all associated answers,
        contact, and person details.
    '''
    eager_load_options = [
        joinedload(FormResponse.answers),
        joinedload(FormResponse.contact).joinedload(Contact.person),
        joinedload(FormResponse.person)
    ]
    db_form_response = get_record(db, FormResponse, form_response_id, eager_load_options)
    return db_form_response

@handle_service_errors
def get_all_form_responses(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> List[FormResponseSummaryResponse]:
    '''
        Retrieves a paginated list of all completed form responses.
        Does not load nested answers by default for performance (uses summary schema).
    '''
    # Using the generic get_all_records_paginated from crud service
    return get_all_records_paginated(db, FormResponse, skip, limit)

@handle_service_errors
def update_form_response_status(
    db: Session,
    form_response_id: int,
    status_data: FormResponseUpdate,
) -> FormResponseDetailResponse:
    '''
        Updates the status of an existing completed form response.
    '''
    db_form_response = get_record(db, FormResponse, form_response_id)
    try:
        updated_response = update_record(db, db_form_response, status_data)
        db.commit()
        db.refresh(updated_response)
        # Eager load for the response schema
        return get_form_response_by_id(db, updated_response.id)
    except IntegrityError as e:
        raise InvalidInputError(
            detail = '''Error updating form response: provided status is invalid
                    o conflicts with current data.'''
        ) from e
