'''
    Responses: routes handler
'''
from typing import List, Optional
from fastapi import APIRouter, Depends, Form, Header, UploadFile, status
from sqlalchemy.orm import Session

# Import schemas for form responses
from schemas.responses import (
    FormResponseStatusFlow,
    PersonCreate,
    PersonListResponse,
    PersonResponse,
    PersonUpdate,
    StartFormSessionRequest,
    StartFormSessionResponse,
    SubmitAnswerRequest,
    NextQuestionResponse,
    GetQuestionToModifyRequest,
    GetQuestionToModifyResponse,
    UpdateAnswerInSessionRequest,
    FinalizeFormRequest,
    FinalizeFormResponse,
    FormResponseDetailResponse,
    FormResponseSummaryResponse,
    FormResponseUpdate
)

# Import controllers for form responses
from controllers.responses import (
    create_person,
    delete_person,
    get_all_persons,
    get_form_response_status_flow_controller,
    get_person_by_id,
    start_form_session,
    submit_answer_and_get_next_question,
    get_question_to_modify,
    update_answer_in_session,
    finalize_form_session,
    get_form_response_by_id,
    get_all_form_responses,
    update_form_response_data,
    update_form_response_status,
    update_person
)

from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/form-responses', tags = ['Form Responses'])
persons_router = APIRouter(prefix = '/v1/persons', tags = ['Persons'])

# --- Endpoints for Form Session Management (DynamoDB backed) ---

@router.post(
    '/start-session',
    response_model = StartFormSessionResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Starts a new form-filling session and returns the first question'
)
async def start_form_session_route(
    session_data: StartFormSessionRequest,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Initiates a new form-filling session for a given form. This endpoint
        handles the session creation for a specific client (identified by `user_id`
        in the request body) and is called by an authenticated user
        (identified by `current_user` in the JWT token).
    '''
    message = f'''User: {current_user
            }. Requests to start a new form session for form ID: {session_data.form_id
            }, on behalf of client ID: {session_data.user_id}.'''
    logger.info(message)
    return await start_form_session(db, session_data)

def _get_submit_answer_request(
    session_id: str = Form(..., description = 'ID of the temporary form filling session.'),
    question_id: int = Form(..., description = 'ID of the question being answered.'),
    question_number: int = Form(..., description = 'Number of the question being answered.'),
    answer_value: Optional[str] = Form(None, description = 'The user\'s answer to the question.'),
    uploaded_file: Optional[UploadFile] = None
) -> SubmitAnswerRequest:
    '''
        Private helper function that handles multipart/form-data and consolidates
        the fields into a single SubmitAnswerRequest object.
    '''
    return SubmitAnswerRequest(
        session_id=session_id,
        question_id=question_id,
        question_number=question_number,
        answer_value=answer_value,
        uploaded_file=uploaded_file
    )

@router.post(
    '/submit-answer',
    response_model = NextQuestionResponse,
    summary = 'Submits an answer and gets the next question in the session'
)
async def submit_answer_route(
    answer_data: SubmitAnswerRequest = Depends(_get_submit_answer_request),
    uploaded_file: Optional[UploadFile] = None,
    db: Session = Depends(GET_DB_DEPENDENCY),
    auth_token: str = Header(..., alias = 'Authorization'),
    current_user: str = Depends(get_current_user)
):
    '''
        Submits an answer for the current question in a temporary form session.
        The session is identified by `session_id`, and the state is updated
        temporarily in DynamoDB. This endpoint is accessible only to authenticated
        users.
    '''
    message = f'''User: {current_user
            }. Submits an answer for session: {answer_data.session_id
            }, question: {answer_data.question_number}.'''
    logger.info(message)
    return await submit_answer_and_get_next_question(db, answer_data, auth_token, uploaded_file)

@router.post(
    '/get-question-to-modify',
    response_model = GetQuestionToModifyResponse,
    summary = 'Retrieves a specific question and its current answer from a session for modification'
)
async def get_question_to_modify_route(
    request_data: GetQuestionToModifyRequest,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Retrieves a previously answered question and its value from a temporary
        form session. This is useful for allowing users to review or modify a
        specific answer before finalizing the form.
    '''
    message = f'''User: {current_user}. Requests to modify question {
        request_data.question_number} in session: {request_data.session_id}.'''
    logger.info(message)
    return await get_question_to_modify(db, request_data)

@router.put(
    '/update-answer-in-session',
    response_model = NextQuestionResponse,
    summary = 'Updates an answer for a specific question within a form session'
)
async def update_answer_in_session_route(
    update_data: UpdateAnswerInSessionRequest,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Updates a specific answer in an ongoing form session. The form flow is
        re-evaluated from the updated question's point to determine the next
        question to be presented.
    '''
    message = f'''User: {current_user}. Updates an answer for question {
        update_data.question_number} in session: {update_data.session_id}.'''
    logger.info(message)
    return await update_answer_in_session(db, update_data)

@router.post(
    '/finalize-session',
    response_model = FinalizeFormResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Finalizes a form session and persists all answers to MySQL'
)
async def finalize_form_session_route(
    finalize_data: FinalizeFormRequest,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Concludes a form-filling session. All temporary answers from DynamoDB
        are moved to the permanent MySQL database, and the temporary session
        is cleared.
    '''
    message = f'''User: {current_user
            }. Requests to finalize form session: {finalize_data.session_id}.'''
    logger.info(message)
    return await finalize_form_session(db, finalize_data)

# --- Endpoints for Completed Form Responses (MySQL backed) ---

@router.get(
    '/{form_response_id}',
    response_model = FormResponseDetailResponse,
    summary = 'Get a completed form response by ID with all answers and contact info'
)
def get_form_response_by_id_route(
    form_response_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Retrieves a single completed form response by its ID from the permanent
        database. This endpoint includes all associated answers, contact, and
        person details.
    '''
    message = f'''User: {current_user
            }. Requests to get form response by ID: {form_response_id}.'''
    logger.info(message)
    return get_form_response_by_id(db, form_response_id)

@router.get(
    '/',
    response_model = List[FormResponseSummaryResponse],
    summary = 'Get all completed form responses (paginated)'
)
def get_all_form_responses_route(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Retrieves a paginated list of all completed form responses. This endpoint
        returns a summary view for performance, avoiding the load of nested answers.
        Access is restricted to authenticated users.
    '''
    message = f'''User: {current_user
            }. Requests to get all form responses (skip: {skip}, limit: {limit}).'''
    logger.info(message)
    return get_all_form_responses(db, skip = skip, limit = limit)

@router.put(
    '/{form_response_id}/status',
    response_model = FormResponseDetailResponse,
    status_code = status.HTTP_200_OK,
    summary = '''Updates the status of a completed form response and records the change
    in the status flow'''
)
def update_form_response_status_route(
    form_response_id: int,
    status_data: FormResponseUpdate,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Updates the administrative status of a previously completed form response
        (e.g., from 'COMPLETED' to 'REVIEWED'). This action is performed by an
        authenticated user and logs the status change in the `form_response_flow` table.
    '''
    message = f'''User: {current_user
            }. Requests to update status for form response {form_response_id
            } to {status_data.status}.'''
    logger.info(message)
    return update_form_response_status(db, form_response_id, status_data)

@persons_router.post(
    '/',
    response_model = PersonResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new person record'
)
def create_person_route(
    person_data: PersonCreate,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Creates a new record in the `t_persons` table.
    '''
    message = f'''User: {current_user
            }. Requests to create a new person record.'''
    logger.info(message)
    return create_person(db, person_data)

@persons_router.get(
    '/{person_id}',
    response_model = PersonResponse,
    summary = 'Get a person by ID'
)
def get_person_by_id_route(
    person_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Retrieves a person record from the `t_persons` table by its ID.
    '''
    message = f'''User: {current_user
            }. Requests to get person with ID: {person_id}.'''
    logger.info(message)
    return get_person_by_id(db, person_id)

@persons_router.get(
    '/',
    response_model = PersonListResponse,
    summary = 'Get all person records (paginated)'
)
def get_all_persons_route(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Retrieves a paginated list of all person records from the `t_persons` table.
    '''
    message = f'''User: {current_user
            }. Requests to get all persons (skip: {skip}, limit: {limit}).'''
    logger.info(message)
    return get_all_persons(db, skip, limit)


@persons_router.put(
    '/{person_id}',
    response_model = PersonResponse,
    summary = 'Update a person record by ID'
)
def update_person_route(
    person_id: int,
    person_data: PersonUpdate,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Updates an existing person record in the `t_persons` table by its ID.
    '''
    message = f'''User: {current_user
            }. Requests to update person with ID: {person_id}.'''
    logger.info(message)
    return update_person(db, person_id, person_data)


@persons_router.delete(
    '/{person_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a person record by ID'
)
def delete_person_route(
    person_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Deletes a person record from the `t_persons` table by its ID.
    '''
    message = f'''User: {current_user
            }. Requests to delete person with ID: {person_id}.'''
    logger.info(message)
    return delete_person(db, person_id)

@router.put(
    '/{form_response_id}',
    response_model = FormResponseDetailResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Updates a completed form response with new data'
)
def update_form_response_route(
    form_response_id: int,
    form_response_data: FormResponseUpdate,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Updates a previously completed form response with new data.
        This endpoint is intended for administrative updates (e.g., modifying
        affiliation details or other fields after the initial submission).
    '''
    message = f'''User: {current_user
            }. Requests to update form response {form_response_id}.'''
    logger.info(message)
    return update_form_response_data(db, form_response_id, form_response_data)

@router.get(
    '/{form_response_id}/status-flow',
    response_model = List[FormResponseStatusFlow],
    summary = 'Get the status flow history for a completed form response'
)
def get_form_response_status_flow_route(
    form_response_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Retrieves the chronological history of status changes for a specific
        form response, including the old and new statuses and the timestamp.
    '''
    message = f'''User: {current_user
            }. Requests status flow for form response {form_response_id}.'''
    logger.info(message)
    return get_form_response_status_flow_controller(db, form_response_id)
