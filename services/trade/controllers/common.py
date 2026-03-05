'''
    Common Controllers
'''
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from fastapi import Request
from schemas.common import (
    PhotoListResponseSchema,
    PhotoResponseSchema,
    PhotoUploadData,
    PhotoUploadForm
)
from services.utils import handle_service_errors
from services.common import (
    delete_photo_service,
    add_photo_service,
    get_photos_by_entity_service,
    get_photos_list_service
)

@handle_service_errors('TRADE')
async def delete_photo_controller(
    photo_id: int,
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    auth_token: str
) -> Dict[str, Any]:
    '''
        Controller for deleting a photo.
    '''
    deleted_id = await delete_photo_service(
        db = db,
        photo_id = photo_id,
        auth_token = auth_token
    )

    return {
        'message': f'Photo with ID {deleted_id} deleted successfully.',
        'id': deleted_id
    }

@handle_service_errors('TRADE')
async def add_photo_controller(
    db: Session,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    auth_token: str,
    form_data: PhotoUploadForm
) -> PhotoResponseSchema:
    '''
        Generic controller for uploading a photo and associating it
        with any entity.
    '''

    service_data = PhotoUploadData(
        company_id = form_data.company_id,
        entity_type = form_data.entity_type,
        entity_id = form_data.entity_id,
        description = form_data.description,
        file = form_data.file
    )

    db_photo = await add_photo_service(
        db = db,
        auth_token = auth_token,
        service_data = service_data
    )

    return PhotoResponseSchema.model_validate(db_photo, from_attributes = True)

@handle_service_errors('TRADE')
async def get_photos_list_controller(
    db: Session,
    skip: int,
    limit: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> PhotoListResponseSchema:
    '''
        Controller to retrieve all photos.
    '''
    items, total = await get_photos_list_service(db=db, skip = skip, limit = limit)

    serialized_items = [
        PhotoResponseSchema.model_validate(item, from_attributes = True)
        for item in items
    ]
    return PhotoListResponseSchema(items = serialized_items, total = total)

@handle_service_errors('TRADE')
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def get_photos_by_entity_controller(
    entity_type: str,
    db: Session,
    skip: int,
    limit: int,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    entity_id: Optional[int] = None
) -> PhotoListResponseSchema:
    '''
        Controller to retrieve photos by specific entity.
    '''
    items, total = await get_photos_by_entity_service(
        db = db,
        entity_type = entity_type,
        entity_id = entity_id,
        skip = skip,
        limit = limit
    )

    serialized_items = [
        PhotoResponseSchema.model_validate(item, from_attributes = True)
        for item in items
    ]
    return PhotoListResponseSchema(items = serialized_items, total = total)
