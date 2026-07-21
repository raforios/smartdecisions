'''
    ETL (participant batch load): routes handler.
'''
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from boto3.resources.base import ServiceResource

from controllers.etl import load_participants_controller
from schemas.enums import ParticipantRole, RoleEnum
from schemas.etl import EtlLoadResponseSchema, ResponsibleSchema
from services.db_connection import GET_DB_DEPENDENCY
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger
from services.security import require_roles

router = APIRouter(prefix = '/v1/mining-summit/etl', tags = ['ETL'])

_ALLOWED_SUFFIX = '.xlsx'


@router.post(
    '/participants',
    response_model = EtlLoadResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Batch-load participants from an institution Excel file',
    description = (
        'Uploads an institution registration Excel and accredits its '
        'participants. The institution is a parameter, so every row belongs to '
        'it. Validates mandatory fields, enforces the institution cupo (only the '
        'first rows that fit are accredited), assigns each participant a stable '
        'eje/mesa seat and the given role, and returns the accreditation summary '
        'including the not-accredited report. Restricted to ADMIN.'
    )
)
# FastAPI multipart endpoints legitimately take several Form fields plus the
# file and dependency injections; grouping them would obscure the OpenAPI form.
# pylint: disable=too-many-arguments, too-many-positional-arguments
async def load_participants_endpoint(
    institution_id: str = Form(..., min_length = 1, max_length = 120),
    responsible_name: str = Form(..., min_length = 1, max_length = 120),
    responsible_phone: str = Form(..., min_length = 1, max_length = 30),
    file: UploadFile = File(...),
    role: Optional[ParticipantRole] = Form(
        None, description = 'Default role for rows with a blank "Rol" cell. The '
                            'per-row column wins; omit to default blanks to SIN_ROL.'
    ),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    _: str = Depends(require_roles(RoleEnum.ADMIN.value))
):
    '''
        Endpoint to batch-load participants from an institution Excel file.
    '''
    if not (file.filename or '').lower().endswith(_ALLOWED_SUFFIX):
        raise InvalidInputError(detail = 'Only .xlsx files are accepted.')

    file_bytes = await file.read()
    message = (
        f'ETL upload for institution={institution_id} role={role.value if role else None} '
        f'file={file.filename} size={len(file_bytes)}B'
    )
    logger.info(message)
    return load_participants_controller(
        dynamodb_resource = dynamodb_resource,
        file_bytes = file_bytes,
        institution_id = institution_id,
        responsible = ResponsibleSchema(name = responsible_name, phone = responsible_phone),
        role = role.value if role else None
    )
