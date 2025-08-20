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
from json.decoder import JSONDecodeError
import httpx
from fastapi import UploadFile
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from dotenv import dotenv_values

# Import models
from models.forms import FormHeader, QuestionDetail # Needed to fetch form structure
from models.responses import Person, Contact, FormResponse, FormAnswer
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
    ServiceUnavailableError # For DynamoDB issues
)
from services.logger_config import custom_logger as logger
from services.crud import (
    create_record,
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

# Configuration for DynamoDB TTL (e.g., 24 hours)
# This should ideally come from configuration (e.env or config service)
DYNAMODB_SESSION_TTL_HOURS = 24

_LOCAL_ENV_PARAMS = dotenv_values('.env') if os.path.exists('.env') else {}

async def _get_question_details_for_form(
    db: Session,
    form_id: int
) -> Dict[int, QuestionDetail]:
    '''
        Helper function to fetch all question details for a given form,
        eagerly loading options and flow rules, and returning them in a
        dictionary keyed by question_number for easy lookup.
    '''
    message = f'Fetching all question details for form_id: {form_id}'
    logger.debug(message)
    # Ensure form exists first
    _ = get_record(db, FormHeader, form_id)

    questions = db.query(QuestionDetail)\
                  .filter(QuestionDetail.form_id == form_id)\
                  .options(joinedload(QuestionDetail.options),
                           joinedload(QuestionDetail.flow_rules))\
                  .order_by(QuestionDetail.question_number)\
                  .all()
    if not questions:
        raise RegisterNotFoundError(
            detail=f'No questions found for form ID: {form_id}'
        )

    # Map questions by their number for quick access
    questions_map = {q.question_number: q for q in questions}
    message = f'Successfully fetched {len(questions_map)} questions for form_id: {form_id}'
    logger.debug(message)
    return questions_map

async def _get_next_question_number(
    current_question_number: int,
    answer_value: Optional[str],
    questions_map: Dict[int, QuestionDetail]
) -> Optional[int]:
    '''
        Determines the next question number based on flow rules or sequential order.
        Returns None if no next question is found (end of form).
    '''
    message = f'''Determining next question for current_question_number:
        {current_question_number}, answer: {answer_value}'''
    logger.debug(message)

    current_question = questions_map.get(current_question_number)
    if not current_question:
        message = f'Current question {current_question_number} not found in map.'
        logger.warning(message)
        return None

    # Check for specific flow rules based on the answer
    if current_question.flow_rules:
        for rule in current_question.flow_rules:
            if rule.answer_value == answer_value:
                message = f'''Flow rule matched: answer '{answer_value}' leads to question
                        {rule.next_question_number}'''
                logger.debug(message)
                return rule.next_question_number
        # If no specific rule matches, check for a default sequential rule
        for rule in current_question.flow_rules:
            if rule.is_default_sequential:
                message = f'''Default sequential flow rule matched (no specific answer match)
                        leads to question {rule.next_question_number}'''
                logger.debug(message)
                return rule.next_question_number

    # If no flow rules, or no matching flow rule, default to next sequential question
    sorted_question_numbers = sorted(questions_map.keys())
    try:
        current_index = sorted_question_numbers.index(current_question_number)
        if current_index + 1 < len(sorted_question_numbers):
            next_seq_question_number = sorted_question_numbers[current_index + 1]
            message = f'''No flow rule matched, defaulting to next sequential question:
                    {next_seq_question_number}'''
            logger.debug(message)
            return next_seq_question_number
    except ValueError:
        # This should ideally not happen if current_question_number is valid
        error_msg = f'''Current question number {current_question_number}
                not found in sorted list.'''
        logger.error(error_msg, exc_info = True)

    logger.debug('No next question found. End of form.')
    return None # End of form

async def _get_question_response_data(question: QuestionDetail) -> Dict[str, Any]:
    '''
        Helper to format question data for NextQuestionResponse.
    '''
    options_data = None
    if question.response_type == 'multiple_choice' and question.options:
        options_data = [
            {'option_text': opt.option_text, 'order': opt.order}
            for opt in sorted(question.options, key=lambda o: o.order)
        ]
    return {
        'question_number': question.question_number,
        'question_content': question.content,
        'response_type': question.response_type,
        'options': options_data
    }

async def _create_person_and_contact(
    db: Session,
    session_data: StartFormSessionRequest
) -> Dict[str, Any]:
    '''
        Helper to create or find Person and create Contact records.
    '''
    person_data = session_data.person_data
    contact_data = session_data.contact_data

    # Check for existing person by unique identifiers
    existing_person = db.query(Person).filter(
        (Person.email == person_data.email) |
        (Person.phone_number == person_data.phone_number) |
        (Person.identification_number == person_data.identification_number)
    ).first()

    if existing_person:
        message = f'Existing person found with ID: {existing_person.id}'
        logger.info(message)
        db_person = existing_person
    else:
        try:
            # New person, create the record
            db_person = create_record(db, Person, person_data)
            message = f'New person created with ID: {db_person.id}'
            logger.info(message)
        except IntegrityError as e:
            db.rollback()
            error_msg = f'Integrity error creating person: {e}'
            logger.error(error_msg, exc_info = True)
            raise InvalidInputError(
                detail='Person creation failed due to data conflict.'
            ) from e

    # Create a new Contact record regardless of whether person is new or existing
    extra_fields = {
        'person_id': db_person.id,
        'executed_route_point_id': session_data.executed_route_point_id
    }
    db_contact = create_record(db, Contact, contact_data, extra_fields = extra_fields)
    message = f'New contact created with ID: {db_contact.id} for person ID: {db_person.id}'
    logger.info(message)

    db.flush() # Ensure Contact record is available before commit
    return {'person_id': db_person.id, 'contact_id': db_contact.id}

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

async def _process_next_question_logic(
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
            error_msg = f'''Flow rule points to non-existent question {next_question_number}
            in form {current_session.form_id}. Treating as end of form.'''
            logger.error(error_msg, exc_info = True)
            is_form_complete = True
            message_response = 'Form completed (flow rule to non-existent question).'
            current_session.current_question_number = -1
        else:
            current_session.current_question_number = next_question.question_number
    else:
        is_form_complete = True
        message_response = '''Form completed. All questions answered or no
                    next question found.'''
        current_session.current_question_number = -1

    return {
        'next_question': next_question,
        'is_form_complete': is_form_complete,
        'message_response': message_response
    }

async def _create_form_response_and_answers(
    db: Session,
    current_session: CurrentFormSession,
    questions_map: Dict[int, QuestionDetail]
):
    '''
        Helper to persist form response and answers to MySQL.
    '''
    question_id_map = {q.question_number: q.id for q in questions_map.values()}

    db_form_response = FormResponse(
        form_id = current_session.form_id,
        user_id = current_session.user_id,
        contact_id = current_session.contact_info_id,
        person_id = current_session.person_info_id
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

    questions_map = await _get_question_details_for_form(db, current_session.form_id)
    if not questions_map:
        raise RegisterNotFoundError(
            detail = f'Form ID {current_session.form_id} has no questions defined.'
        )
    return current_session, questions_map

async def _prepare_next_question_response(
    current_session: CurrentFormSession,
    next_question: Optional[QuestionDetail],
    is_form_complete: bool,
    message_response: str
) -> NextQuestionResponse:
    '''
        Helper to construct the NextQuestionResponse object.
    '''
    current_answers_for_response = {}
    for qn_key in current_session.answers: # Iterate keys to avoid .items() E1101
        current_answers_for_response[qn_key] = current_session.answers[qn_key] \
                                                .model_dump(exclude_unset = True)

    response_data = {
        'session_id': current_session.session_id,
        'is_form_complete': is_form_complete,
        'message': message_response,
        'current_answers': current_answers_for_response
    }

    if next_question:
        response_data.update(await _get_question_response_data(next_question))
    return NextQuestionResponse(**response_data)

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
            message = 'FILES_SERVICE_URL environment variable is not set.'
            raise ServiceUnavailableError(detail = message)

        upload_endpoint = f'{files_service_url}/v1/s3/upload'

        mime_type, _ = mimetypes.guess_type(uploaded_file.filename)
        if not mime_type:
            mime_type = 'application/octet-stream' # Fallback por si no se detecta

        async with httpx.AsyncClient() as client:
            try:
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
                    message = 'FILES service did not return a valid URL.'
                    raise ServiceUnavailableError(detail = message)

                message = f'File uploaded successfully. URL received: {file_url}'
                logger.info(message)
                return file_url

            except httpx.HTTPStatusError as e:
                message = f'''Failed to upload file to FILES service. Status:
                            {e.response.status_code}, Detail: {e.response.text}'''
                logger.error(message, exc_info = True)
                raise ServiceUnavailableError(detail = message) from e
            except Exception as e:
                message = f'''Unexpected error during file upload to FILES service:
                            {e}'''
                logger.error(message, exc_info = True)
                raise ServiceUnavailableError(detail = message) from e

    except JSONDecodeError as e:
        message = 'answer_value has an invalid JSON format.'
        raise InvalidInputError(detail = message) from e
    except Exception as e:
        message = f'Unexpected error in file upload logic: {e}'
        logger.error(message, exc_info = True)
        raise e

# --- Controller Functions ---

async def start_form_session(
    db: Session,
    session_data: StartFormSessionRequest,
) -> StartFormSessionResponse:
    '''
        Initiates a new form-filling session, creates person/contact records,
        and returns the first question.
    '''
    try:
        # 1. Create Person and Contact records
        contact_info = await _create_person_and_contact(db, session_data)

        # 2. Get form details (questions, options, flow rules)
        questions_map = await _get_question_details_for_form(db, session_data.form_id)
        first_question_number = min(questions_map.keys())
        first_question = questions_map[first_question_number]
        session_id = str(uuid.uuid4())

        # 3. Initialize temporary session in DynamoDB
        contact_details_for_session = {
            'contact_id': contact_info['contact_id'],
            'latitude': session_data.contact_data.latitude,
            'longitude': session_data.contact_data.longitude,
            'person_info_id': contact_info['person_id']
        }

        _ = await _initialize_dynamodb_session(
            session_id = session_id,
            form_id = session_data.form_id,
            first_question_number = first_question_number,
            user_id = session_data.user_id,
            contact_info = contact_details_for_session
        )
        db.commit() # Commit MySQL changes

        message = f'''User {session_data.user_id,} started session {session_id}
                for form {session_data.form_id}. First question: {first_question_number}'''
        logger.info(message)

        return StartFormSessionResponse(
            session_id = session_id,
            form_id = session_data.form_id,
            **await _get_question_response_data(first_question)
        )

    except (RegisterNotFoundError, IntegrityError) as e:
        db.rollback()
        error_msg = f'''Error starting form session:
            {e.detail if hasattr(e, 'detail') else str(e)}'''
        logger.error(error_msg, exc_info = True)
        raise e
    except ServiceUnavailableError as e:
        db.rollback() # Rollback MySQL changes if DynamoDB fails
        error_msg = f'''DynamoDB error starting session: {e}'''
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'''Unexpected error starting form session: {e}'''
        logger.error(error_msg, exc_info = True)
        raise e


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
    try:
        current_session, questions_map = await _common_session_load_and_validate(
            answer_data.session_id, db)

        # Ensure the submitted question is the expected current question or a valid prior one
        if current_session.current_question_number != answer_data.question_number:
            message = f'''User submitted answer for question
                    {answer_data.question_number} but current session question is
                    {current_session.current_question_number}. Allowing for now,
                    but consider stricter check.'''
            logger.warning(message)

        submitted_question_detail = questions_map.get(answer_data.question_number)
        if not submitted_question_detail:
            raise RegisterNotFoundError(
                detail = f'''Question number {answer_data.question_number} not found
                        in form {current_session.form_id}.'''
            )

     # Si el tipo de pregunta es "file upload", maneja la lógica de subida de archivo.
        if submitted_question_detail.response_type == 'FILE_UPLOAD':
            if not uploaded_file:
                raise InvalidInputError(detail = 'File upload question requires a file.')

            # Llama a la función auxiliar con el objeto UploadFile
            answer_data.answer_value = await _handle_file_upload_logic(
                uploaded_file, auth_token
            )

        # Store the submitted answer in the session cache
        temp_answer = TemporaryAnswer(
            question_id = submitted_question_detail.id,
            question_number = submitted_question_detail.question_number,
            answer_value = answer_data.answer_value,
            response_type = submitted_question_detail.response_type
        )
        current_session.answers[str(answer_data.question_number)] = temp_answer

        # Determine the next question number and process form completion
        next_question_number = await _get_next_question_number(
            current_question_number = answer_data.question_number,
            answer_value = answer_data.answer_value,
            questions_map = questions_map
        )

        process_result = await _process_next_question_logic(
            current_session, next_question_number, questions_map
        )
        next_question = process_result['next_question']
        is_form_complete = process_result['is_form_complete']
        message_response = process_result['message_response']

        # Update session in DynamoDB
        current_session.ttl = int(
            (datetime.now() + timedelta(hours = DYNAMODB_SESSION_TTL_HOURS)).timestamp()
        )
        await save_session(current_session.model_dump())

        message = f'''Session {current_session.session_id}:
            Next question determined. Form complete: {is_form_complete}'''
        logger.info(message)
        return await _prepare_next_question_response(
            current_session, next_question, is_form_complete, message_response
        )

    except (RegisterNotFoundError, InvalidInputError) as e:
        message = f'''Error submitting answer:
            {e.detail if hasattr(e, 'detail') else str(e)}'''
        logger.error(message, exc_info = True)
        raise e
    except ServiceUnavailableError as e:
        message = f'''DynamoDB error submitting answer: {e}'''
        logger.error(message, exc_info = True)
        raise e
    except Exception as e:
        message = f'Unexpected error submitting answer and getting next question: {e}'
        logger.error(message, exc_info = True)
        raise e

async def get_question_to_modify(
    db: Session,
    request_data: GetQuestionToModifyRequest,
) -> GetQuestionToModifyResponse:
    '''
        Retrieves a specific question and its current answer from a session for modification.
    '''
    try:
        current_session, questions_map = await _common_session_load_and_validate(
            request_data.session_id, db)

        target_question = questions_map.get(request_data.question_number)
        if not target_question:
            raise RegisterNotFoundError(
                detail=(
                    f'Question number {request_data.question_number} not found '
                    f'in form {current_session.form_id}.'
                )
            )

        # Retrieve current answer from session cache
        # Replaced .get() with explicit check for E1101
        current_answer_obj = None
        if str(request_data.question_number) in current_session.answers:
            current_answer_obj = current_session.answers[str(request_data.question_number)]

        current_answer_value = current_answer_obj.answer_value \
                               if current_answer_obj else None

        response_data = {
            'session_id': current_session.session_id,
            'question_number': target_question.question_number,
            'question_content': target_question.content,
            'response_type': target_question.response_type,
            'current_answer': current_answer_value,
            'options': None, # Default to None
            'message': 'Question retrieved for modification.'
        }

        if target_question.response_type == 'multiple_choice' \
           and target_question.options:
            response_data['options'] = [
                {'option_text': opt.option_text, 'order': opt.order}
                for opt in sorted(target_question.options, key=lambda o: o.order)
            ]

        message = f'''User retrieved question {request_data.question_number}
                from session {request_data.session_id} for modification.'''
        logger.info(message)
        return GetQuestionToModifyResponse(**response_data)

    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'''Error retrieving question for modification:
        {e.detail if hasattr(e, 'detail') else str(e)}'''
        logger.error(error_msg, exc_info = True)
        raise e
    except ServiceUnavailableError as e:
        error_msg = f'DynamoDB error retrieving question for modification: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error retrieving question for modification: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

async def update_answer_in_session(
    db: Session,
    update_data: UpdateAnswerInSessionRequest,
) -> NextQuestionResponse: # Using NextQuestionResponse as it provides session status
    '''
        Updates the answer for a specific question within a form session in DynamoDB.
        This also re-evaluates the flow from that point.
    '''
    try:
        current_session, questions_map = await _common_session_load_and_validate(
            update_data.session_id, db)

        target_question_detail = questions_map.get(update_data.question_number)
        if not target_question_detail:
            raise RegisterNotFoundError(
                detail = f'''Question number {update_data.question_number} not found
                    in form {current_session.form_id}.'''
            )

        # Update the answer in the session cache
        temp_answer = TemporaryAnswer(
            question_id = target_question_detail.id,
            question_number = target_question_detail.question_number,
            answer_value = update_data.new_answer_value,
            response_type = target_question_detail.response_type
        )
        current_session.answers[str(update_data.question_number)] = temp_answer

        # Determine the next question number and process form completion
        next_question_number = await _get_next_question_number(
            current_question_number = update_data.question_number,
            answer_value = update_data.new_answer_value,
            questions_map = questions_map
        )

        process_result = await _process_next_question_logic(
            current_session, next_question_number, questions_map
        )
        next_question = process_result['next_question']
        is_form_complete = process_result['is_form_complete']
        message_response = process_result['message_response']


        # Update session in DynamoDB
        current_session.ttl = int(
            (datetime.now() + timedelta(hours = DYNAMODB_SESSION_TTL_HOURS)).timestamp()
        )
        await save_session(current_session.model_dump())

        message = f'''User updated question {update_data.question_number}
                in session {update_data.session_id}. Form complete: {is_form_complete}'''
        logger.info(message)
        return await _prepare_next_question_response(
            current_session, next_question, is_form_complete, message_response
        )

    except (RegisterNotFoundError, InvalidInputError) as e:
        error_msg = f'''Error updating answer in session:
        {e.detail if hasattr(e, 'detail') else str(e)}'''
        logger.error(error_msg, exc_info = True)
        raise e
    except ServiceUnavailableError as e:
        error_msg = f'DynamoDB error updating answer in session: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        error_msg = f'Unexpected error updating answer in session: {e}'
        logger.error(error_msg, exc_info = True)
        raise e


async def finalize_form_session(
    db: Session,
    finalize_data: FinalizeFormRequest,
) -> FinalizeFormResponse:
    '''
        Finalizes a form session, persists all answers to MySQL, and clears the cache.
    '''
    try:
        current_session, questions_map = await _common_session_load_and_validate(
            finalize_data.session_id, db)

        if not current_session.answers:
            raise InvalidInputError(detail='Cannot finalize an empty form session.')

        # Create FormResponse and FormAnswer records in MySQL
        form_response_id = await _create_form_response_and_answers(
            db, current_session, questions_map
        )

        # Delete session from DynamoDB (cleanup)
        await delete_session_by_id(current_session.session_id)

        message = f'''User finalized session {current_session.session_id}.
                Permanent FormResponse ID: {form_response_id}'''
        logger.info(message)
        return FinalizeFormResponse(form_response_id=form_response_id)

    except (RegisterNotFoundError, InvalidInputError, IntegrityError) as e:
        db.rollback() # Rollback MySQL changes
        error_msg = f'''Error finalizing form session:
            {e.detail if hasattr(e, 'detail') else str(e)}'''
        logger.error(error_msg, exc_info = True)
        raise e
    except ServiceUnavailableError as e:
        db.rollback() # Rollback MySQL changes if DynamoDB cleanup fails
        error_msg = f'DynamoDB error during finalization: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error finalizing form session: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

# --- CRUD Operations for Completed Form Responses ---

async def get_form_response_by_id(
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
    try:
        db_form_response = get_record(db, FormResponse, form_response_id, eager_load_options)
        message = f'''Form response {form_response_id} retrieved successfully.'''
        logger.info(message)
        return db_form_response
    except RegisterNotFoundError as exc:
        message = f'Form response with ID {form_response_id} not found.'
        logger.warning(message)
        raise RegisterNotFoundError(
            detail = f'Form response with ID {form_response_id} not found.'
        ) from exc
    except Exception as e:
        error_msg = f'Unexpected error retrieving form response {form_response_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e

async def get_all_form_responses(
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

async def update_form_response_status(
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
        return await get_form_response_by_id(db, updated_response.id)
    except RegisterNotFoundError:
        db.rollback()
        raise
    except IntegrityError as e:
        db.rollback()
        error_msg = f'''Database integrity error when updating form response
                {form_response_id}: {e}'''
        logger.error(error_msg, exc_info = True)
        raise InvalidInputError(
            detail = '''Error updating form response: provided status is invalid
                    o conflicts with current data.'''
        ) from e
    except Exception as e:
        db.rollback()
        error_msg = f'Unexpected error updating form response {form_response_id}: {e}'
        logger.error(error_msg, exc_info = True)
        raise e
