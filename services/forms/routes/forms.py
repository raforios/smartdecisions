'''
    Forms: routes handler
'''
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

# Import schemas
from schemas.forms import (
    FormFilters,
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
    '''
    message = f'User: {current_user}. Received request to create form header: {form_data.form_code}'
    logger.info(message)
    return await create_form_header(db, form_data)

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
    '''
    message = f'User: {current_user}. Received request to get form header with ID: {form_id}'
    logger.info(message)
    return await get_form_header_by_id(db, form_id)

@router.get(
    '/',
    response_model = List[FormHeaderResponse],
    summary = 'Get all form headers (paginated)'
)
async def get_all_form_headers_route(
    filters: FormFilters = Depends(),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Retrieves a list of all form headers based on optional filter criteria.
        Supports pagination through 'skip' and 'limit' query parameters.
    '''
    message = f'''User: {current_user}. Received request to get all form headers
            (skip: {skip}, limit: {limit})'''
    logger.info(message)
    return await get_all_form_headers(
        db,
        filters = filters,
        skip = skip,
        limit = limit
    )

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
    '''
    message = f'User: {current_user}. Received request to update form header with ID: {form_id}'
    logger.info(message)
    return await update_form_header(db, form_id, form_data)

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
    '''
    message = f'User: {current_user}. Received request to delete form header with ID: {form_id}'
    logger.info(message)
    return await delete_form_header(db, form_id)

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
    '''
    message = f'''User: {current_user}. Received request to create question for form ID: {form_id},
            question number: {question_data.question_number}'''
    logger.info(message)
    return await create_question_detail(db, form_id, question_data)

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
    '''
    message = f'''User: {current_user}. Received request to get question detail
            with ID: {question_id}'''
    logger.info(message)
    return await get_question_detail_by_id(db, question_id)

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
    '''
    message = f'''User: {current_user}. Received request to update question detail
            with ID: {question_id}'''
    logger.info(message)
    return await update_question_detail(db, question_id, question_data)

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
    '''
    message = f'''User: {current_user}. Received request to delete question detail
            with ID: {question_id}'''
    logger.info(message)
    return await delete_question_detail(db, question_id)
