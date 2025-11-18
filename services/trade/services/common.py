'''
    COmmon Business Logic
'''
import os
from typing import Any, Dict, Optional, Tuple
from fastapi import UploadFile
from sqlalchemy.orm import Session
from models.common import Photo
from schemas.common import PhotoUploadData
from services.exceptions import (
    ResourceNotFoundError,
    ServiceUnavailableError
)
from services.exceptions import InvalidInputError
from services.crud import get_record, delete_record
from services.utils import (
    get_current_time_gmt,
    handle_service_errors,
    audit_event,
    _handle_files_service,
    sqlalchemy_object_as_dict
)
from services.logger_config import custom_logger as logger


@handle_service_errors('TRADE')
async def prepare_file_to_upload(
    file: Optional[UploadFile],
    dynamic_path: str,
    auth_token: str,
    prefix: str
) -> Dict[str, Any]:
    '''
        Helper to prepare to upload file across FILES microservice
    '''
    _, file_extension = os.path.splitext(file.filename)
    current_time = get_current_time_gmt()
    timestamp_part = current_time.strftime('%Y%m%d-%H-%M-%S')
    new_file_name = f'{prefix}_{timestamp_part}{file_extension}'
    file.filename = new_file_name

    file_key = f'{dynamic_path.rstrip("/")}/{new_file_name}'

    file_service_response = await _handle_files_service(
        action = 'create',
        file_name = '',
        auth_token = auth_token,
        uploaded_file = file,
        dynamic_path = dynamic_path
    )

    file_service_response['key'] = file_key

    return file_service_response

@handle_service_errors('TRADE')
@audit_event('TRADE', 'Photo', 'DELETE')
async def delete_photo_service(
    db: Session,
    photo_id: int,
    auth_token: str
) -> Tuple[int, Dict[str, Any]]:
    '''
        Delete a Photo record from the database and the S3 bucket.
    '''
    # 1. Obtener el registro de la foto
    db_photo = get_record(db, Photo, photo_id)
    old_values = sqlalchemy_object_as_dict(db_photo)

    # 2. Intentar borrar el archivo de S3
    if db_photo.file_key:
        try:
            await _handle_files_service(
                action = 'delete',
                file_name = db_photo.file_key,
                auth_token = auth_token
            )
            message = f'File {db_photo.file_key} deleted from S3.'
            logger.info(message)
        except (ServiceUnavailableError, ResourceNotFoundError) as e:
            error_msg = f'Could not delete file {db_photo.file_key} from S3: {e}'
            logger.error(error_msg, exc_info = True)

    delete_record(db, model = Photo, record_id = db_photo.id)

    db.commit()

    auditable_data = {
        'old_values': old_values,
        'new_values': None
    }

    return photo_id, auditable_data


@handle_service_errors('TRADE')
@audit_event('TRADE', 'Photo', 'CREATE')
async def add_photo_service(
    db: Session,
    auth_token: str,
    service_data: PhotoUploadData
) -> Tuple[Photo, Dict[str, Any]]:
    '''
        Upload a photo, associate it with an entity (Product or POS)
        and save the record in t_trade_photos.
    '''

    # 1. Definir una ruta en S3 (ej: trade/company_id/products/product_id)
    entity_path = 'unknown'
    if service_data.entity_type == 'PRODUCT':
        entity_path = 'products'
    elif service_data.entity_type == 'POS':
        entity_path = 'pos'
    else:
        # Validar para futuras entidades
        raise InvalidInputError(detail = f'Invalid service_data.entity_type: {
            service_data.entity_type}')

    dynamic_path = f'trade/{service_data.company_id}/{entity_path}/{service_data.entity_id}'

    if not service_data.file:
        raise InvalidInputError(detail = 'No file was provided.')

    # 2. Llamar al servicio de FILES (usando el helper existente)
    file_data = await prepare_file_to_upload(
        file = service_data.file,
        dynamic_path = dynamic_path,
        auth_token = auth_token,
        prefix = service_data.entity_type.lower()
    )

    # 3. Crear el registro en t_trade_photos
    db_photo = Photo(
        company_id = service_data.company_id,
        entity_type = service_data.entity_type.upper(),
        entity_id = service_data.entity_id,
        file_url = file_data['url'],
        file_key = file_data['key'],
        description = service_data.description
    )

    db.add(db_photo)
    db.commit()
    db.refresh(db_photo)

    auditable_data = {
        'new_values': sqlalchemy_object_as_dict(db_photo)
    }

    return db_photo, auditable_data
