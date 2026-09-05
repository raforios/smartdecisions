'''
    Ingest controllers.
'''
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.ingest import (
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    TEMPLATE_VERSION,
    DatasetListResponse,
    DatasetSummary,
    IngestResponse,
    IngestStatusResponse,
    IngestSummary,
    TemplateInfo,
    ValidationIssue
)
from services.exceptions import ResourceNotFoundError
from services.ingest import (
    parse_and_validate,
    parse_and_validate_partial,
    serialize_dataframe
)
from services.ingest_utils import (
    download_bytes,
    get_owned_dataset,
    list_datasets_for_owner,
    persist_dataset,
    upload_bytes,
    upload_excel
)
from services.environment import load_and_validate_env_vars
from services.utils import handle_service_errors

# Only a slice of the issues travels in the JSON response / DynamoDB item
# (400 KB limit); the full set lives in the rejected CSV in S3.
ENV_VARS = load_and_validate_env_vars({}, optional_env_vars = {
    'MAX_ISSUES_ON_RESPONSE': int,
    'CSV_CONTENT_TYPE': str,
    'TEMPLATE_S3_KEY': str,
})
MAX_ISSUES_ON_RESPONSE = ENV_VARS['MAX_ISSUES_ON_RESPONSE'] or 100
CSV_CONTENT_TYPE = ENV_VARS['CSV_CONTENT_TYPE'] or 'text/csv'
# The template is a static object in the default bucket, not something the
# service builds: the format is fixed and the client is the one who complies
# with it. Changing it means changing business logic, so it moves over time and
# never at runtime.
TEMPLATE_S3_KEY = ENV_VARS['TEMPLATE_S3_KEY'] or 'ingest/templates/template_ventas_v1.xlsx'


def _to_response(item: Dict[str, Any]) -> IngestResponse:
    '''
        Maps a persisted DynamoDB item into the public IngestResponse schema.
    '''
    return IngestResponse(
        dataset_id = item['dataset_id'],
        status = item['status'],
        file_s3_key = item.get('file_s3_key') or '',
        summary = IngestSummary(
            total_rows = item.get('total_rows', 0),
            valid_rows = item.get('valid_rows', 0),
            error_rows = item.get('error_rows', 0),
            unique_points_of_sale = item.get('unique_points_of_sale', 0),
            unique_products = item.get('unique_products', 0),
            date_range_start = item.get('date_range_start'),
            date_range_end = item.get('date_range_end')
        ),
        issues = [ValidationIssue(**issue) for issue in item.get('issues', [])],
        created_at = item['created_at']
    )


# pylint: disable=too-many-arguments, too-many-positional-arguments
@handle_service_errors('INGEST')
async def ingest_excel_controller(
    dynamodb_resource: ServiceResource,
    file_bytes: bytes,
    filename: str,
    bearer_token: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> IngestResponse:
    '''
        Controller orchestrating the full ingest flow:
            1. Parse + validate the uploaded file.
            2. If valid: upload to S3 via FILES; otherwise skip the upload.
            3. Persist the dataset metadata in DynamoDB.
            4. Return the public response.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            file_bytes (bytes): Raw content of the uploaded file.
            filename (str): Original filename.
            bearer_token (str): JWT used to call FILES on behalf of the user.
            current_user (str): Authenticated user email (owner of the dataset).

        Returns:
            IngestResponse: Public payload with the summary and per-row issues.
    '''
    result = parse_and_validate(file_bytes, filename)
    is_valid = not result.issues

    file_s3_key: Optional[str] = None
    if is_valid:
        # Store the NORMALIZED dataframe (canonical columns, ids filled) so every
        # downstream service reads a clean, uniform dataset without re-mapping.
        file_s3_key = upload_excel(
            file_bytes = serialize_dataframe(result.accepted, filename),
            filename = filename,
            bearer_token = bearer_token
        )

    persisted = persist_dataset(
        dynamodb_resource = dynamodb_resource,
        payload = {
            'owner_email': current_user,
            'status': 'validated' if is_valid else 'failed',
            'file_s3_key': file_s3_key,
            'template_version': TEMPLATE_VERSION,
            **result.summary.model_dump(),
            'issues': [issue.model_dump(mode = 'json') for issue in result.issues]
        }
    )
    return _to_response(persisted)


@handle_service_errors('INGEST')
async def ingest_excel_from_s3_controller(
    dynamodb_resource: ServiceResource,
    file_key: str,
    file_name: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> IngestResponse:
    '''
        Synchronously processes a file already uploaded to S3 (via a pre-signed
        URL) and returns the outcome in the same response — mirroring the TRADE
        bulk pattern (upload to S3, read from S3, process, return). No async job
        and no polling: if it fails, it fails visibly.

            1. Download the raw file from S3 with boto3 (no API Gateway limit).
            2. Validate + normalize with partial acceptance: valid rows are kept,
               invalid rows go to a separate 'rejected' CSV with a reason.
            3. Store the normalized rows (CSV) and the rejected rows in S3.
            4. Persist the dataset metadata and return the public response.

        Processing a CSV of ~120k rows takes ~2 s, well under the API Gateway
        29 s timeout; the multi-minute part is the S3 upload, which already
        happened before this call.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            file_key (str): S3 key of the raw uploaded file.
            file_name (str): Original filename (drives format detection).
            current_user (str): Authenticated user email (dataset owner).

        Returns:
            IngestResponse: Public payload with the summary and per-row issues.
    '''
    file_bytes = download_bytes(file_key)

    result = parse_and_validate_partial(file_bytes, file_name)
    has_valid_rows = len(result.accepted) > 0

    # Accepted rows -> normalized CSV (feeds analytics/forecast/routes).
    normalized_key: Optional[str] = None
    if has_valid_rows:
        normalized_key = upload_bytes(
            file_key = f'ingest/normalized/{uuid4().hex}.csv',
            data = serialize_dataframe(result.accepted, 'normalized.csv'),
            content_type = CSV_CONTENT_TYPE
        )
    # Rejected rows -> separate CSV the client can fix and re-upload.
    rejected_key: Optional[str] = None
    if len(result.rejected) > 0:
        rejected_key = upload_bytes(
            file_key = f'ingest/rejected/{uuid4().hex}.csv',
            data = serialize_dataframe(result.rejected, 'rejected.csv'),
            content_type = CSV_CONTENT_TYPE
        )

    persisted = persist_dataset(
        dynamodb_resource = dynamodb_resource,
        payload = {
            'owner_email': current_user,
            'status': 'validated' if has_valid_rows else 'failed',
            'file_s3_key': normalized_key,
            'rejected_s3_key': rejected_key,
            'template_version': TEMPLATE_VERSION,
            **result.summary.model_dump(),
            'issues': [
                issue.model_dump(mode = 'json')
                for issue in result.issues[:MAX_ISSUES_ON_RESPONSE]
            ]
        }
    )
    return _to_response(persisted)


@handle_service_errors('INGEST', with_log = False)
async def download_rejected_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> bytes:
    '''
        Returns the CSV of rows that could not be loaded, each carrying the
        reason in Spanish, so the client can fix them and re-upload.

        Raises:
            ResourceNotFoundError: If the dataset has no rejected-rows file.
    '''
    item = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    rejected_key = item.get('rejected_s3_key')
    if not rejected_key:
        raise ResourceNotFoundError(
            detail = 'Este dataset no tiene filas rechazadas para descargar.'
        )
    return download_bytes(rejected_key)


@handle_service_errors('INGEST')
async def list_datasets_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str,
    limit: int = 20
) -> DatasetListResponse:
    '''
        Returns the caller's own uploads, most recent first.

        Args:
            dynamodb_resource (ServiceResource): DynamoDB resource.
            request (Request): Incoming request, used by the audit decorator.
            current_user (str): Authenticated caller and owner of the rows.
            limit (int): Most rows to return.

        Returns:
            DatasetListResponse: The caller's uploads.
    '''
    items = list_datasets_for_owner(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        limit = limit
    )
    return DatasetListResponse(
        owner_email = current_user,
        count = len(items),
        datasets = [
            DatasetSummary(
                dataset_id = item['dataset_id'],
                status = item['status'],
                total_rows = int(item.get('total_rows', 0)),
                valid_rows = int(item.get('valid_rows', 0)),
                error_rows = int(item.get('error_rows', 0)),
                unique_points_of_sale = int(item.get('unique_points_of_sale', 0)),
                unique_products = int(item.get('unique_products', 0)),
                date_range_start = item.get('date_range_start'),
                date_range_end = item.get('date_range_end'),
                created_at = item['created_at']
            )
            for item in items
        ]
    )


@handle_service_errors('INGEST')
async def get_dataset_status_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str
) -> IngestStatusResponse:
    '''
        Controller to retrieve the status of a previously ingested dataset.
    '''
    item = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    return IngestStatusResponse(
        dataset_id = item['dataset_id'],
        status = item['status'],
        owner_email = item['owner_email'],
        file_s3_key = item.get('file_s3_key') or '',
        summary = IngestSummary(
            total_rows = item.get('total_rows', 0),
            valid_rows = item.get('valid_rows', 0),
            error_rows = item.get('error_rows', 0),
            unique_points_of_sale = item.get('unique_points_of_sale', 0),
            unique_products = item.get('unique_products', 0),
            date_range_start = item.get('date_range_start'),
            date_range_end = item.get('date_range_end')
        ),
        issues = [ValidationIssue(**issue) for issue in item.get('issues', [])],
        created_at = item['created_at']
    )


@handle_service_errors('INGEST', with_log = False)
async def download_template_controller(
    base_path: Path, # pylint: disable=unused-argument
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> bytes:
    '''
        Reads the canonical template from the default bucket so the route can
        return it. Decorated with `with_log = False`: the event is still shipped
        to EVENTS, but the binary file body is not logged.

        Returns:
            bytes: Raw .xlsx content of the stored template.
    '''
    return download_bytes(TEMPLATE_S3_KEY)


@handle_service_errors('INGEST')
async def get_template_info_controller(
    base_path: Path, # pylint: disable=unused-argument
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> TemplateInfo:
    '''
        Controller returning the metadata of the canonical Excel template,
        served from the default bucket.

        Returns:
            TemplateInfo: Version + required/optional columns + relative URL.
    '''
    return TemplateInfo(
        template_version = TEMPLATE_VERSION,
        download_url = '/v1/ingest/template/file',
        required_columns = list(REQUIRED_COLUMNS),
        optional_columns = list(OPTIONAL_COLUMNS)
    )
