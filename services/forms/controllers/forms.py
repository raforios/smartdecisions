'''
   Forms Controller
'''
from typing import Any, Dict, List
from sqlalchemy.orm import Session
from fastapi import Request
from services.forms import (
    create_form_header,
    delete_form_header,
    get_all_form_headers,
    get_form_header_by_id,
    update_form_header,
    create_question_detail,
    delete_question_detail,
    get_question_detail_by_id,
    update_question_detail
)
from services.utils import handle_service_errors
from schemas.forms import (
    FormFilters,
    FormHeaderCreate,
    FormHeaderResponse,
    FormHeaderUpdate,
    QuestionDetailCreate,
    QuestionDetailResponse,
    QuestionDetailUpdate
)

@handle_service_errors('FORMS')
async def create_form_header_controller(
    form_data: FormHeaderCreate,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> FormHeaderResponse:
    '''
        Controller to create a new form header.
    '''
    db_form_header = await create_form_header(
        db = db,
        form_data = form_data
    )
    return FormHeaderResponse.model_validate(db_form_header, from_attributes = True)

@handle_service_errors('FORMS')
async def get_form_header_by_id_controller(
    form_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> FormHeaderResponse:
    '''
        Controller to retrieve a form header by its ID.
    '''
    db_form_header = await get_form_header_by_id(db = db, form_id = form_id)
    return FormHeaderResponse.model_validate(db_form_header, from_attributes = True)

@handle_service_errors('FORMS')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_all_form_headers_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    filters: FormFilters,
    skip: int = 0,
    limit: int = 100
) -> List[FormHeaderResponse]:
    '''
        Controller to retrieve a list of all form headers with optional filters.
    '''
    db_form_headers = await get_all_form_headers(
        db = db,
        filters = filters,
        skip = skip,
        limit = limit
    )
    return [FormHeaderResponse.model_validate(
        form,
        from_attributes = True
    ) for form in db_form_headers]

@handle_service_errors('FORMS')
async def update_form_header_controller(
    form_id: int,
    form_data: FormHeaderUpdate,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> FormHeaderResponse:
    '''
        Controller to update an existing form header.
    '''
    db_form_header = await update_form_header(
        db = db,
        form_id = form_id,
        form_data = form_data
    )
    return FormHeaderResponse.model_validate(db_form_header, from_attributes = True)

@handle_service_errors('FORMS')
async def delete_form_header_controller(
    form_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller to delete a form header by its ID.
    '''
    result_id, _ = await delete_form_header(
        db = db,
        form_id = form_id
    )
    return {
        'message': f'Form header {result_id} deleted successfully.',
        'id': result_id
    }

@handle_service_errors('FORMS')
async def create_question_detail_controller(
    form_id: int,
    question_data: QuestionDetailCreate,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> QuestionDetailResponse:
    '''
        Controller to create a new question detail.
    '''
    db_question = await create_question_detail(
        db = db,
        form_id = form_id,
        question_data = question_data
    )
    return QuestionDetailResponse.model_validate(db_question, from_attributes = True)

@handle_service_errors('FORMS')
async def get_question_detail_by_id_controller(
    question_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> QuestionDetailResponse:
    '''
        Controller to retrieve a question detail by its ID.
    '''
    db_question = await get_question_detail_by_id(db = db, question_id = question_id)
    return QuestionDetailResponse.model_validate(db_question, from_attributes = True)

@handle_service_errors('FORMS')
async def update_question_detail_controller(
    question_id: int,
    question_data: QuestionDetailUpdate,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> QuestionDetailResponse:
    '''
        Controller to update an existing question detail.
    '''
    db_question = await update_question_detail(
        db = db,
        question_id = question_id,
        question_data = question_data
    )
    return QuestionDetailResponse.model_validate(db_question, from_attributes = True)

@handle_service_errors('FORMS')
async def delete_question_detail_controller(
    question_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> Dict[str, Any]:
    '''
        Controller to delete a question detail by its ID.
    '''
    result_id = await delete_question_detail(
        db = db,
        question_id = question_id
    )
    return {
        'message': f'Question detail {result_id} deleted successfully.',
        'id': result_id
    }
