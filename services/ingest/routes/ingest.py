'''
    Ingest: routes handler.
'''
from pathlib import Path
from fastapi import (
    APIRouter, Depends, File, Header, Path as PathParam, Request, Response,
    UploadFile, status
)
from boto3.resources.base import ServiceResource

from controllers.ingest import (
    download_rejected_controller,
    download_template_controller,
    get_dataset_status_controller,
    get_template_info_controller,
    ingest_excel_controller,
    ingest_excel_from_s3_controller
)
from schemas.ingest import (
    IngestError,
    IngestFromS3Request,
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
    description = 'Returns the canonical template_ventas_v1.xlsx stored in S3.',
    response_class = Response
)
async def download_template_endpoint(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint that streams the canonical .xlsx template.
    '''
    message = f'User: {current_user}. Downloading Excel template file.'
    logger.info(message)
    content = await download_template_controller(
        base_path = SERVICE_ROOT,
        request = request,
        current_user = current_user
    )
    return Response(
        content = content,
        media_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers = {
            'Content-Disposition': 'attachment; filename="template_ventas_v1.xlsx"'
        }
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
        raise InvalidInputError(detail = IngestError.UNSUPPORTED_FILE_FORMAT.value)

    file_bytes = await file.read()
    if not file_bytes:
        raise InvalidInputError(detail = IngestError.EMPTY_UPLOAD.value)

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


@router.post(
    '/excel-from-s3',
    response_model = IngestResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Ingest a large sales file already uploaded to S3',
    description = (
        'Validates and normalizes a file previously uploaded to S3 via a '
        'pre-signed URL, addressed by its object key, and returns the outcome '
        'synchronously. Used for files that exceed the API Gateway payload '
        '(~10 MB), so the binary never transits API Gateway. Invalid rows are '
        'accepted partially and offered via GET /v1/ingest/{dataset_id}/rejected.'
    )
)
async def ingest_excel_from_s3_endpoint(
    request: Request,
    payload: IngestFromS3Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to ingest a sales file already staged in S3 by key.
    '''
    lower = payload.file_name.lower()
    if not lower.endswith(SUPPORTED_EXTENSIONS):
        raise InvalidInputError(detail = IngestError.UNSUPPORTED_FILE_FORMAT.value)
    message = f'Ingesting from S3 key "{payload.file_key}" for {current_user}.'
    logger.info(message)
    return await ingest_excel_from_s3_controller(
        dynamodb_resource = dynamodb_resource,
        file_key = payload.file_key,
        file_name = payload.file_name,
        current_user = current_user,
        request = request
    )


@router.get(
    '/{dataset_id}/rejected',
    summary = 'Download the rows that could not be loaded',
    description = (
        'Streams a CSV with the rejected rows and a "motivo" column explaining '
        'why each failed, so the client can fix and re-upload them.'
    )
)
async def download_rejected_endpoint(
    request: Request,
    dataset_id: str = PathParam(..., min_length = 8, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint that streams the rejected-rows CSV for a dataset.
    '''
    content = await download_rejected_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        request = request,
        current_user = current_user
    )
    return Response(
        content = content,
        media_type = 'text/csv',
        headers = {'Content-Disposition': 'attachment; filename="filas_no_cargadas.csv"'}
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
