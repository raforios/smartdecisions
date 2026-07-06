'''
    Ingest: routes handler.
'''
from pathlib import Path
from fastapi import (
    APIRouter, Depends, File, Header, Path as PathParam, Request, UploadFile, status
)
from fastapi.responses import FileResponse
from boto3.resources.base import ServiceResource

from controllers.ingest import (
    get_dataset_status_controller,
    get_template_info_controller,
    ingest_excel_controller
)
from schemas.ingest import (
    IngestResponse,
    IngestStatusResponse,
    TemplateInfo
)
from services.db_connection import GET_DB_DEPENDENCY
from services.exceptions import InvalidInputError
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/ingest', tags = ['Ingest'])

SERVICE_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_EXTENSIONS = ('.xlsx', '.csv')


def _extract_bearer(authorization: str) -> str:
    '''
        Strips the "Bearer " prefix to forward the raw token to FILES.
    '''
    if not authorization:
        return ''
    parts = authorization.split(' ', 1)
    return parts[1] if len(parts) == 2 and parts[0].lower() == 'bearer' else authorization


@router.get(
    '/template',
    response_model = TemplateInfo,
    status_code = status.HTTP_200_OK,
    summary = 'Get sales template metadata',
    description = (
        'Returns the canonical template version, required/optional columns '
        'and the download URL.'
    )
)
async def get_template_info_endpoint(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve template metadata.
    '''
    message = f'User: {current_user}. Retrieving Excel template metadata.'
    logger.info(message)
    return await get_template_info_controller(
        base_path = SERVICE_ROOT,
        request = request,
        current_user = current_user
    )


@router.get(
    '/template/file',
    status_code = status.HTTP_200_OK,
    summary = 'Download the sales Excel template',
    description = 'Streams the canonical template_ventas_v1.xlsx file.',
    response_class = FileResponse
)
async def download_template_endpoint(
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint that streams the canonical .xlsx template generated at deploy time.
    '''
    message = f'User: {current_user}. Downloading Excel template file.'
    logger.info(message)
    template_path = SERVICE_ROOT / 'assets' / 'template_ventas_v1.xlsx'
    if not template_path.exists():
        raise InvalidInputError(detail = 'La plantilla aún no está disponible en el servidor.')
    return FileResponse(
        path = str(template_path),
        filename = 'template_ventas_v1.xlsx',
        media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@router.post(
    '/excel',
    response_model = IngestResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Upload and validate a sales Excel/CSV',
    description = (
        'Accepts a .xlsx or .csv file matching the v1 sales template, validates '
        'it against the contract and persists the dataset metadata. Valid files '
        'are also stored in S3 via the FILES microservice.'
    )
)
async def ingest_excel_endpoint(
    request: Request,
    file: UploadFile = File(...),
    authorization: str = Header(...),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to ingest a sales Excel/CSV file.
    '''
    filename = file.filename or ''
    lower = filename.lower()
    if not lower.endswith(SUPPORTED_EXTENSIONS):
        raise InvalidInputError(
            detail = f'Formato no soportado. Use uno de: {", ".join(SUPPORTED_EXTENSIONS)}.'
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise InvalidInputError(detail = 'El archivo subido está vacío.')

    message = f'Ingesting "{filename}" ({len(file_bytes)} bytes) from {current_user}.'
    logger.info(message)

    return await ingest_excel_controller(
        dynamodb_resource = dynamodb_resource,
        file_bytes = file_bytes,
        filename = filename,
        bearer_token = _extract_bearer(authorization),
        current_user = current_user,
        request = request
    )


@router.get(
    '/{dataset_id}',
    response_model = IngestStatusResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Get ingest dataset status',
    description = 'Retrieves a previously ingested dataset by its UUID.'
)
async def get_dataset_endpoint(
    request: Request,
    dataset_id: str = PathParam(..., min_length = 8, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve dataset status/metadata.
    '''
    message = f'User: {current_user}. Retrieving dataset {dataset_id}.'
    logger.info(message)
    return await get_dataset_status_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        request = request,
        current_user = current_user
    )
