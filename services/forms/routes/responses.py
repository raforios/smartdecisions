'''
    Responses: routes handler
'''
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

# Import schemas for form responses
from schemas.responses import (
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
    start_form_session,
    submit_answer_and_get_next_question,
    get_question_to_modify,
    update_answer_in_session,
    finalize_form_session,
    get_form_response_by_id,
    get_all_form_responses,
    update_form_response_status
)

from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user # To get current_user_id from JWT

router = APIRouter(prefix = '/v1/form-responses', tags = ['Form Responses'])

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

        Args:
            session_data (StartFormSessionRequest): Contains the `form_id`,
                                                    `user_id` (the client's numeric ID),
                                                    and personal and contact info.
            db (Session): The database session dependency.
            current_user (str): The email of the authenticated user from the JWT token.
                                Used for logging and audit purposes only.

        Returns:
            StartFormSessionResponse: Details of the started session and the first
                                    question to be displayed to the client.
    '''
    message = f'''Authenticated user '{current_user}' requests to start a new
            form session for form ID: {session_data.form_id},
            on behalf of client ID: {session_data.user_id}.'''
    logger.info(message)
    return await start_form_session(db, session_data)

@router.post(
    '/submit-answer',
    response_model = NextQuestionResponse,
    summary = 'Submits an answer and gets the next question in the session'
)
async def submit_answer_route(
    answer_data: SubmitAnswerRequest,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Submits an answer for the current question in a temporary form session.
        The session is identified by `session_id`, and the state is updated
        temporarily in DynamoDB. This endpoint is accessible only to authenticated
        users.

        Args:
            answer_data (SubmitAnswerRequest): Contains the `session_id`,
                                            `question_number`, and the `answer_value`.
            db (Session): The database session dependency.
            current_user (str): The email of the authenticated user from the JWT token.
                                Used for logging and audit purposes only.

        Returns:
            NextQuestionResponse: Details of the next question in the flow or indicates
                                that the form is complete.
    '''
    message = f'''Authenticated user '{current_user}' submits an answer
            for session: {answer_data.session_id}, question: {answer_data.question_number}.'''
    logger.info(message)
    return await submit_answer_and_get_next_question(db, answer_data)

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

        Args:
            request_data (GetQuestionToModifyRequest): Contains the `session_id` and
                                                    `question_number` of the question to retrieve.
            db (Session): The database session dependency.
            current_user (str): The email of the authenticated user from the JWT token.
                                Used for logging and audit purposes only.

        Returns:
            GetQuestionToModifyResponse: Details of the requested question and its
                                        current answer within the session.
    '''
    message = f'''Authenticated user '{current_user}' requests to modify
            question {request_data.question_number} in session: {request_data.session_id}.'''
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

        Args:
            update_data (UpdateAnswerInSessionRequest): Contains the `session_id`,
                                    `question_number`, and the `new_answer_value`.
            db (Session): The database session dependency.
            current_user (str): The email of the authenticated user from the JWT token.
                                Used for logging and audit purposes only.

        Returns:
            NextQuestionResponse: Details of the next question (after re-evaluation)
                                or indicates that the form is complete.
    '''
    message = f'''Authenticated user '{current_user}' updates an answer
            for question {update_data.question_number} in session: {update_data.session_id}.'''
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

        Args:
            finalize_data (FinalizeFormRequest): Contains the `session_id` to finalize.
            db (Session): The database session dependency.
            current_user (str): The email of the authenticated user from the JWT token.
                                Used for logging and audit purposes only.

        Returns:
            FinalizeFormResponse: Confirmation of finalization with the new
                                permanent `form_response_id`.
    '''
    message = f'''Authenticated user '{current_user}' requests to
            finalize form session: {finalize_data.session_id}.'''
    logger.info(message)
    return await finalize_form_session(db, finalize_data)

# --- Endpoints for Completed Form Responses (MySQL backed) ---

@router.get(
    '/{form_response_id}',
    response_model = FormResponseDetailResponse,
    summary = 'Get a completed form response by ID with all answers and contact info'
)
async def get_form_response_by_id_route(
    form_response_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Retrieves a single completed form response by its ID from the permanent
        database. This endpoint includes all associated answers, contact, and
        person details.

        Args:
            form_response_id (int): The ID of the completed form response.
            db (Session): The database session dependency.
            current_user (str): The email of the authenticated user from the JWT token.
                                Used for logging and to enforce access control.

        Returns:
            FormResponseDetailResponse: The detailed completed form response.
    '''
    message = f'''Authenticated user '{current_user}' requests to get
            form response by ID: {form_response_id}.'''
    logger.info(message)
    return await get_form_response_by_id(db, form_response_id)

@router.get(
    '/',
    response_model = List[FormResponseSummaryResponse],
    summary = 'Get all completed form responses (paginated)'
)
async def get_all_form_responses_route(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Retrieves a paginated list of all completed form responses. This endpoint
        returns a summary view for performance, avoiding the load of nested answers.
        Access is restricted to authenticated users.

        Args:
            skip (int): The number of items to skip for pagination.
            limit (int): The maximum number of items to return.
            db (Session): The database session dependency.
            current_user (str): The email of the authenticated user from the JWT token.
                                Used for logging and to enforce access control.

        Returns:
            List[FormResponseSummaryResponse]: A list of summarized form responses.
    '''
    message = f'''Authenticated user '{current_user}' requests to get all form
            responses (skip: {skip}, limit: {limit}).'''
    logger.info(message)
    return await get_all_form_responses(db, skip = skip, limit = limit)

@router.put(
    '/{form_response_id}/status',
    response_model = FormResponseDetailResponse,
    summary = 'Update the status of a completed form response'
)
async def update_form_response_status_route(
    form_response_id: int,
    status_data: FormResponseUpdate,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Updates the administrative status of a previously completed form response
        (e.g., from 'PENDING' to 'REVIEWED'). This action is performed by
        an authenticated user.

        Args:
            form_response_id (int): The ID of the form response to update.
            status_data (FormResponseUpdate): The new status to apply.
            db (Session): The database session dependency.
            current_user (str): The email of the authenticated user from the JWT token.
                                Used for logging and to enforce access control.

        Returns:
            FormResponseDetailResponse: The updated form response with its new status.
    '''
    message = f'''Authenticated user {current_user} requests to update status
            for form response {form_response_id} to {status_data.status.value}.'''
    logger.info(message)
    return await update_form_response_status(db, form_response_id, status_data)
