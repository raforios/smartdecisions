'''
    Common: routes handler
'''
from typing import Any, Dict
from fastapi import (
    APIRouter,
    Depends,
    Request,
    status,
    Header
)
from sqlalchemy.orm import Session
from schemas.common import PhotoResponseSchema, PhotoUploadForm
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.common import add_photo_controller, delete_photo_controller

router = APIRouter(prefix = '/v1/common', tags = ['Common'])

@router.delete(
    '/photos/{photo_id}',
    response_model = Dict[str, Any],
    status_code = status.HTTP_200_OK,
    summary = 'Delete a Photo'
)
async def delete_photo_endpoint(
    photo_id: int,
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user),
    auth_token: str = Header(..., alias = 'Authorization')
):
    '''
        Delete a photo from S3 and the database.
    '''
    message = f'User: {current_user}. Request to delete Photo ID: {photo_id}.'
    logger.info(message)
    return await delete_photo_controller(
        photo_id = photo_id,
        db = db,
        request = request,
        current_user = current_user,
        auth_token = auth_token
    )

@router.post(
    '/photos/upload',
    response_model = PhotoResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Upload a photo for any entity'
)
async def upload_photo_endpoint(
    request: Request,
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user),
    auth_token: str = Header(..., alias = 'Authorization'),
    form_data: PhotoUploadForm = Depends(PhotoUploadForm)
):
    '''
        Upload an image file and associate it with a generic entity.
    '''
    message = f'User: {current_user}. Request to upload photo for {
        form_data.entity_type} ID: {form_data.entity_id}.'
    logger.info(message)

    return await add_photo_controller(
        db = db,
        request = request,
        current_user = current_user,
        auth_token = auth_token,
        form_data = form_data
    )
