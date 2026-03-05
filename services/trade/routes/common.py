'''
    Common: routes handler
'''
from typing import Any, Dict
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Request,
    status,
    Header
)
from sqlalchemy.orm import Session
from schemas.common import (
    PhotoListResponseSchema,
    PhotoResponseSchema,
    PhotoUploadForm
)
from services.db_connection import GET_DB_DEPENDENCY
from services.security import get_current_user
from services.logger_config import custom_logger as logger
from controllers.common import (
    add_photo_controller,
    delete_photo_controller,
    get_photos_by_entity_controller,
    get_photos_list_controller
)

router = APIRouter(prefix = '/v1/common', tags = ['Common'])

# pylint: disable=duplicate-code
@router.get(
    '/photos',
    response_model = PhotoListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List all photos'
)
async def get_all_photos_endpoint(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Retrieve a general paginated list of all uploaded photos.
    '''
    message = f'User: {current_user}. Request to list all photos.'
    logger.info(message)

    return await get_photos_list_controller(
        db = db,
        skip = skip,
        limit = limit,
        request = request,
        current_user = current_user
    )
# pylint: disable=duplicate-code, too-many-arguments, too-many-positional-arguments
@router.get(
    '/photos/entity',
    response_model = PhotoListResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'List photos by entity'
)
async def get_photos_by_entity_endpoint(
    request: Request,
    entity_type: str = Query(..., description = 'Type of the entity (e.g., PRODUCT, POS, etc.)'),
    entity_id: int = Query(None, description = 'Unique ID of the entity'),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1),
    db: Session = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Retrieve a paginated list of photos filtered by a specific entity type and ID.
    '''
    message = f'User: {current_user}. Request to list photos for {entity_type} ID: {entity_id}.'
    logger.info(message)

    return await get_photos_by_entity_controller(
        entity_type = entity_type,
        entity_id = entity_id,
        db = db,
        skip = skip,
        limit = limit,
        request = request,
        current_user=current_user
    )

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
