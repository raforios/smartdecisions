'''
    Forms: routes handler
'''
from typing import List
from fastapi import (
    APIRouter,
    Depends,
    status,
    Path,
    Query,
    Request
)
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
    create_form_header_controller,
    get_all_form_headers_controller,
    get_form_header_by_id_controller,
    update_form_header_controller,
    delete_form_header_controller,
    create_question_detail_controller,
    get_question_detail_by_id_controller,
    update_question_detail_controller,
    delete_question_detail_controller
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
    summary = 'Create a new form header with its questions',
    description = '''Creates a new form header, including its questions, multiple choice options,
        and flow rules.'''
)
async def create_new_form_header_route(
    form_data: FormHeaderCreate,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new form header.
    '''
    message = f'User: {current_user}. Received request to create form header: {form_data.form_code}'
    logger.info(message)
    return await create_form_header_controller(
        db = db,
        form_data = form_data,
        request = request,
        current_user = current_user
    )

@router.get(
    '/{form_id}',
    response_model = FormHeaderResponse,
    summary = 'Get a form header by ID with all its questions',
    description = '''Retrieves a single form header by its ID, including all associated questions,
        multiple choice options, and flow rules.'''
)
async def get_form_header_by_id_route(
    request: Request,
    form_id: int = Path(..., gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to get a form header by ID.
    '''
    message = f'User: {current_user}. Received request to get form header with ID: {form_id}'
    logger.info(message)
    return await get_form_header_by_id_controller(
        db = db,
        form_id = form_id,
        request = request,
        current_user = current_user
    )

@router.get(
    '/',
    response_model = List[FormHeaderResponse],
    summary = 'Get all form headers (paginated)',
    description = '''Retrieves a list of all form headers based on optional filter criteria.
        Supports pagination through 'skip' and 'limit' query parameters.'''
)
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_all_form_headers_route(
    request: Request,
    filters: FormFilters = Depends(),
    skip: int = Query(0, ge = 0),
    limit: int = Query(100, ge = 1, le = 100),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to get all form headers.
    '''
    message = f'''User: {current_user}. Received request to get all form headers
            (skip: {skip}, limit: {limit})'''
    logger.info(message)
    return await get_all_form_headers_controller(
        db = db,
        filters = filters,
        skip = skip,
        limit = limit,
        request = request,
        current_user = current_user
    )

@router.put(
    '/{form_id}',
    response_model = FormHeaderResponse,
    summary = 'Update a form header by ID',
    description = '''Updates an existing form header by its ID.
        Note: This endpoint updates only the header\'s direct attributes.
        Questions, options, and flow rules should be updated via their specific endpoints.'''
)
async def update_existing_form_header_route(
    request: Request,
    form_id: int = Path(..., gt = 0),
    form_data: FormHeaderUpdate = ...,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update an existing form header.
    '''
    message = f'User: {current_user}. Received request to update form header with ID: {form_id}'
    logger.info(message)
    return await update_form_header_controller(
        db = db,
        form_id = form_id,
        form_data = form_data,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/{form_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a form header by ID',
    description = '''Deletes a form header by its ID.
        This action will also delete all associated questions, options, flow rules,
        and form responses due to cascade settings in the database models.'''
)
async def delete_existing_form_header_route(
    request: Request,
    form_id: int = Path(..., gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a form header.
    '''
    message = f'User: {current_user}. Received request to delete form header with ID: {form_id}'
    logger.info(message)
    return await delete_form_header_controller(
        db = db,
        form_id = form_id,
        request = request,
        current_user = current_user
    )

# --- Endpoints for QuestionDetail ---

@router.post(
    '/{form_id}/questions/',
    response_model = QuestionDetailResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a new question for a specific form header',
    description = '''Creates a new question detail for a specified form header,
        including its multiple choice options and flow rules.'''
)
async def create_new_question_detail_route(
    request: Request,
    form_id: int = Path(..., gt = 0),
    question_data: QuestionDetailCreate = ...,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to create a new question detail.
    '''
    message = f'''User: {current_user}. Received request to create question for form ID: {form_id},
            question number: {question_data.question_number}'''
    logger.info(message)
    return await create_question_detail_controller(
        db = db,
        form_id = form_id,
        question_data = question_data,
        request = request,
        current_user = current_user
    )

@router.get(
    '/questions/{question_id}',
    response_model = QuestionDetailResponse,
    summary = 'Get a question detail by ID',
    description = '''Retrieves a single question detail by its ID, including associated
        multiple choice options and flow rules.'''
)
async def get_question_detail_by_id_route(
    request: Request,
    question_id: int = Path(..., gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to get a question detail by ID.
    '''
    message = f'''User: {current_user}. Received request to get question detail
            with ID: {question_id}'''
    logger.info(message)
    return await get_question_detail_by_id_controller(
        db = db,
        question_id = question_id,
        request = request,
        current_user = current_user
    )

@router.put(
    '/questions/{question_id}',
    response_model = QuestionDetailResponse,
    summary = 'Update a question detail by ID',
    description = '''Updates an existing question detail by its ID.
        This endpoint supports updating question attributes, and replacing
        (deleting old and adding new) associated options and flow rules.'''
)
async def update_existing_question_detail_route(
    request: Request,
    question_id: int = Path(..., gt = 0),
    question_data: QuestionDetailUpdate = ...,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to update a question detail.
    '''
    message = f'''User: {current_user}. Received request to update question detail
            with ID: {question_id}'''
    logger.info(message)
    return await update_question_detail_controller(
        db = db,
        question_id = question_id,
        question_data = question_data,
        request = request,
        current_user = current_user
    )

@router.delete(
    '/questions/{question_id}',
    status_code = status.HTTP_200_OK,
    summary = 'Delete a question detail by ID',
    description = '''Deletes a question detail by its ID.
        This action will also delete all associated multiple choice options and
        flow rules due to cascade settings in the database models.'''
)
async def delete_existing_question_detail_route(
    request: Request,
    question_id: int = Path(..., gt = 0),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to delete a question detail.
    '''
    message = f'''User: {current_user}. Received request to delete question detail
            with ID: {question_id}'''
    logger.info(message)
    return await delete_question_detail_controller(
        db = db,
        question_id = question_id,
        request = request,
        current_user = current_user
    )
