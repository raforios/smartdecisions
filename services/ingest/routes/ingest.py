'''
    Ingest: routes handler.
'''
from pathlib import Path
from fastapi import (
    APIRouter, Depends, File, Header, Path as PathParam, Query, Request,
    Response, UploadFile, status
)
from boto3.resources.base import ServiceResource

from controllers.collections import ingest_collections_controller
from controllers.ingest import (
    download_rejected_controller,
    download_template_controller,
    get_dataset_status_controller,
    get_template_info_controller,
    list_datasets_controller,
    ingest_excel_controller,
    ingest_excel_from_s3_controller
)
from controllers.stock import ingest_stock_controller
from controllers.visits import ingest_visits_controller
from schemas.ingest import (
    CollectionsResponse,
    IngestError,
    StockResponse,
    VisitsResponse,
    IngestFromS3Request,
    IngestResponse,
    DatasetListResponse,
    IngestStatusResponse,
    TemplateInfo
)
from services.db_connection import GET_DB_DEPENDENCY
from services.exceptions import InvalidInputError
from services.ingest_files import SUPPORTED_EXTENSIONS
from services.ingest_utils import HISTORY_DEFAULT_LIMIT
from services.logger_config import custom_logger as logger
from services.security import get_current_owner

router = APIRouter(prefix = '/v1/ingest', tags = ['Ingest'])

SERVICE_ROOT = Path(__file__).resolve().parent.parent


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
    current_user: str = Depends(get_current_owner)
) -> TemplateInfo:
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
    current_user: str = Depends(get_current_owner)
) -> Response:
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
    current_user: str = Depends(get_current_owner)
) -> IngestResponse:
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
    current_user: str = Depends(get_current_owner)
) -> IngestResponse:
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


@router.post(
    '/{dataset_id}/collections',
    response_model = CollectionsResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Upload the payments of a sales dataset',
    description = (
        'Accepts a .xlsx or .csv with the collections contract and marries it to '
        'an existing sales dataset by invoice number. Loading it separately is '
        'what lets a client register sales today and payments as they come in; '
        'an invoice with no payment rows is an open balance, not an error. A new '
        'load replaces the previous one for that dataset.'
    )
)
async def ingest_collections_endpoint(
    request: Request,
    dataset_id: str = PathParam(..., min_length = 8, max_length = 64),
    file: UploadFile = File(...),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> CollectionsResponse:
    '''
        Endpoint to ingest the payments of a sales dataset.
    '''
    filename = file.filename or ''
    if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
        raise InvalidInputError(detail = IngestError.UNSUPPORTED_FILE_FORMAT.value)

    file_bytes = await file.read()
    if not file_bytes:
        raise InvalidInputError(detail = IngestError.EMPTY_UPLOAD.value)

    message = (f'Ingesting collections "{filename}" ({len(file_bytes)} bytes) for '
               f'dataset {dataset_id} from {current_user}.')
    logger.info(message)

    return await ingest_collections_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        file_bytes = file_bytes,
        filename = filename,
        current_user = current_user,
        request = request
    )


@router.post(
    '/{dataset_id}/stock',
    response_model = StockResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Upload the daily stock snapshot of a sales dataset',
    description = (
        'Accepts a .xlsx or .csv with the stock contract —one row per product '
        'and day with what is in the warehouse— and marries it to the product '
        'catalogue of an existing sales dataset. It is a SNAPSHOT: a new load '
        'replaces the previous one, so what is reported is always the latest '
        'photo. `Comprometido` is read, never written: this service reports '
        'what the ERP already committed and does not hold reservations of its '
        'own.'
    )
)
async def ingest_stock_endpoint(
    request: Request,
    dataset_id: str = PathParam(..., min_length = 8, max_length = 64),
    file: UploadFile = File(...),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> StockResponse:
    '''
        Endpoint to ingest the stock snapshot of a sales dataset.
    '''
    filename = file.filename or ''
    if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
        raise InvalidInputError(detail = IngestError.UNSUPPORTED_FILE_FORMAT.value)

    file_bytes = await file.read()
    if not file_bytes:
        raise InvalidInputError(detail = IngestError.EMPTY_UPLOAD.value)

    message = (f'Ingesting stock "{filename}" ({len(file_bytes)} bytes) for '
               f'dataset {dataset_id} from {current_user}.')
    logger.info(message)

    return await ingest_stock_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        file_bytes = file_bytes,
        filename = filename,
        current_user = current_user,
        request = request
    )


@router.post(
    '/{dataset_id}/visits',
    response_model = VisitsResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Upload the visits of the sales force for a sales dataset',
    description = (
        'Accepts a .xlsx or .csv with the visits contract —one row per visit: '
        'date, seller, client, and optionally hour, coordinates and outcome— '
        'and marries it to the clients and sellers of an existing sales '
        'dataset. It is the EXECUTED side of the routes: OPTIMIZATION compares '
        'it against the plan. A new load replaces the previous one.'
    )
)
async def ingest_visits_endpoint(
    request: Request,
    dataset_id: str = PathParam(..., min_length = 8, max_length = 64),
    file: UploadFile = File(...),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> VisitsResponse:
    '''
        Endpoint to ingest the visits of a sales dataset.
    '''
    filename = file.filename or ''
    if not filename.lower().endswith(SUPPORTED_EXTENSIONS):
        raise InvalidInputError(detail = IngestError.UNSUPPORTED_FILE_FORMAT.value)

    file_bytes = await file.read()
    if not file_bytes:
        raise InvalidInputError(detail = IngestError.EMPTY_UPLOAD.value)

    message = (f'Ingesting visits "{filename}" ({len(file_bytes)} bytes) for '
               f'dataset {dataset_id} from {current_user}.')
    logger.info(message)

    return await ingest_visits_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        file_bytes = file_bytes,
        filename = filename,
        current_user = current_user,
        request = request
    )


@router.get(
    '/datasets',
    response_model = DatasetListResponse,
    summary = 'Your own uploads, most recent first',
    description = (
        'Lists the datasets uploaded by the authenticated caller. Only theirs: '
        'the owner is part of the query, not a filter applied afterwards.'
    )
)
async def list_datasets_endpoint(
    request: Request,
    limit: int = Query(
        HISTORY_DEFAULT_LIMIT, ge = 1, le = 100, description = 'Most rows to return.'
    ),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_owner)
) -> DatasetListResponse:
    ''' Endpoint listing the caller\'s own uploads. '''
    message = f'User: {current_user}. Requested their dataset history.'
    logger.info(message)

    return await list_datasets_controller(
        dynamodb_resource = dynamodb_resource,
        request = request,
        current_user = current_user,
        limit = limit
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
    current_user: str = Depends(get_current_owner)
) -> DatasetListResponse:
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
    current_user: str = Depends(get_current_owner)
) -> IngestStatusResponse:
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
