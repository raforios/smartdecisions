'''
    Forms: routes handler
'''
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

# Import schemas
from schemas.forms import (
    FormHeaderCreate,
    FormHeaderResponse,
    FormHeaderUpdate,
    QuestionDetailCreate,
    QuestionDetailResponse,
    QuestionDetailUpdate
)
from controllers.forms import (
    create_form_header,
    get_form_header_by_id,
    get_all_form_headers,
    update_form_header,
    delete_form_header,
    create_question_detail,
    get_question_detail_by_id,
    update_question_detail,
    delete_question_detail
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/forms', tags = ['Forms'])

# --- Endpoints for FormHeader ---

@router.post(
    '/',
    response_model = FormHeaderResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new form header with its questions'
)
async def create_new_form_header_route(
    form_data: FormHeaderCreate,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
    Creates a new form header, including its questions, multiple choice options,
    and flow rules.

    Args:
        form_data (FormHeaderCreate): The form header data with nested questions.
        db (Session): The database session.

    Returns:
        FormHeaderResponse: The created form header with all its details.
    '''
    message = f'User: {current_user}. Received request to create form header: {form_data.form_code}'
    logger.info(message)
    db_form_header = await create_form_header(db, form_data)
    message = f'Form header {db_form_header.id} created successfully via API.'
    logger.info(message)
    return db_form_header

@router.get(
    '/{form_id}',
    response_model = FormHeaderResponse,
    summary = 'Get a form header by ID with all its questions'
)
async def get_form_header_by_id_route(
    form_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
    Retrieves a single form header by its ID, including all associated questions,
    multiple choice options, and flow rules.

    Args:
        form_id (int): The ID of the form header to retrieve.
        db (Session): The database session.

    Returns:
        FormHeaderResponse: The requested form header.
    '''
    message = f'User: {current_user}. Received request to get form header with ID: {form_id}'
    logger.info(message)
    form_header = await get_form_header_by_id(db, form_id)
    message = f'Form header {form_id} retrieved successfully via API.'
    logger.info(message)
    return form_header

@router.get(
    '/',
    response_model = List[FormHeaderResponse],
    summary = 'Get all form headers (paginated)'
)
async def get_all_form_headers_route(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
    Retrieves a list of all form headers.
    Supports pagination through 'skip' and 'limit' query parameters.

    Args:
        skip (int): The number of items to skip (for pagination).
        limit (int): The maximum number of items to return (for pagination).
        db (Session): The database session.

    Returns:
        List[FormHeaderResponse]: A list of form headers.
    '''
    message = f'''User: {current_user}. Received request to get all form headers
            (skip: {skip}, limit: {limit})'''
    logger.info(message)
    form_headers = await get_all_form_headers(db, skip=skip, limit=limit)
    message = f'{len(form_headers)} form headers retrieved successfully via API.'
    logger.info(message)
    return form_headers

@router.put(
    '/{form_id}',
    response_model = FormHeaderResponse,
    summary = 'Update a form header by ID'
)
async def update_existing_form_header_route(
    form_id: int,
    form_data: FormHeaderUpdate,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
    Updates an existing form header by its ID.
    Note: This endpoint updates only the header's direct attributes.
    Questions, options, and flow rules should be updated via their specific endpoints.

    Args:
        form_id (int): The ID of the form header to update.
        form_data (FormHeaderUpdate): The updated data for the form header.
        db (Session): The database session.

    Returns:
        FormHeaderResponse: The updated form header.
    '''
    message = f'User: {current_user}. Received request to update form header with ID: {form_id}'
    logger.info(message)
    updated_form_header = await update_form_header(db, form_id, form_data)
    message = f'Form header {form_id} updated successfully via API.'
    logger.info(message)
    return updated_form_header

@router.delete(
    '/{form_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a form header by ID'
)
async def delete_existing_form_header_route(
    form_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
    Deletes a form header by its ID.
    This action will also delete all associated questions, options, flow rules,
    and form responses due to cascade settings in the database models.

    Args:
        form_id (int): The ID of the form header to delete.
        db (Session): The database session.

    Returns:
        Dict[str, str]: A success message.
    '''
    message = f'User: {current_user}. Received request to delete form header with ID: {form_id}'
    logger.info(message)
    response = await delete_form_header(db, form_id)
    message = f'Form header {form_id} deleted successfully via API.'
    logger.info(message)
    return response

# --- Endpoints for QuestionDetail ---

@router.post(
    '/{form_id}/questions/',
    response_model = QuestionDetailResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new question for a specific form header'
)
async def create_new_question_detail_route(
    form_id: int,
    question_data: QuestionDetailCreate,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
    Creates a new question detail for a specified form header,
    including its multiple choice options and flow rules.

    Args:
        form_id (int): The ID of the form header to associate the question with.
        question_data (QuestionDetailCreate): The question detail data.
        db (Session): The database session.

    Returns:
        QuestionDetailResponse: The created question detail.
    '''
    message = f'''User: {current_user}. Received request to create question for form ID: {form_id},
            question number: {question_data.question_number}'''
    logger.info(message)
    db_question = await create_question_detail(db, form_id, question_data)
    message = f'Question {db_question.id} created successfully for form {form_id} via API.'
    logger.info(message)
    return db_question

@router.get(
    '/questions/{question_id}',
    response_model = QuestionDetailResponse,
    summary = 'Get a question detail by ID'
)
async def get_question_detail_by_id_route(
    question_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
    Retrieves a single question detail by its ID, including associated
    multiple choice options and flow rules.

    Args:
        question_id (int): The ID of the question detail to retrieve.
        db (Session): The database session.

    Returns:
        QuestionDetailResponse: The requested question detail.
    '''
    message = f'''User: {current_user}. Received request to get question detail
            with ID: {question_id}'''
    logger.info(message)
    question_detail = await get_question_detail_by_id(db, question_id)
    message = f'Question detail {question_id} retrieved successfully via API.'
    logger.info(message)
    return question_detail

@router.put(
    '/questions/{question_id}',
    response_model = QuestionDetailResponse,
    summary = 'Update a question detail by ID'
)
async def update_existing_question_detail_route(
    question_id: int,
    question_data: QuestionDetailUpdate,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
    Updates an existing question detail by its ID.
    This endpoint supports updating question attributes, and replacing
    (deleting old and adding new) associated options and flow rules.

    Args:
        question_id (int): The ID of the question detail to update.
        question_data (QuestionDetailUpdate): The updated data for the question detail.
        db (Session): The database session.

    Returns:
        QuestionDetailResponse: The updated question detail.
    '''
    message = f'''User: {current_user}. Received request to update question detail
            with ID: {question_id}'''
    logger.info(message)
    updated_question_detail = await update_question_detail(db, question_id, question_data)
    message = f'Question detail {question_id} updated successfully via API.'
    logger.info(message)
    return updated_question_detail

@router.delete(
    '/questions/{question_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a question detail by ID'
)
async def delete_existing_question_detail_route(
    question_id: int,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
    Deletes a question detail by its ID.
    This action will also delete all associated multiple choice options and
    flow rules due to cascade settings in the database models.

    Args:
        question_id (int): The ID of the question detail to delete.
        db (Session): The database session.

    Returns:
        Dict[str, str]: A success message.
    '''
    message = f'''User: {current_user}. Received request to delete question detail
            with ID: {question_id}'''
    logger.info(message)
    response = await delete_question_detail(db, question_id)
    message = f'Question detail {question_id} deleted successfully via API.'
    logger.info(message)
    return response
