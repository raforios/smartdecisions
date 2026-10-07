'''
    Ingest controllers.
'''
from dataclasses import replace
from pathlib import Path

from boto3.resources.base import ServiceResource
from fastapi import Request

from controllers.common import (
    MAX_ISSUES_ON_RESPONSE,
    template_key,
    native_numbers,
    store_frame,
    summary_of,
    to_ingest_response
)
from schemas.clients import ClientSource
from schemas.ingest import (
    OPTIONAL_COLUMNS,
    SALES_TEMPLATE,
    REQUIRED_COLUMNS,
    TEMPLATE_VERSION,
    CollectionsSummary,
    StockSummary,
    VisitsSummary,
    DatasetListResponse,
    DatasetSummary,
    IngestError,
    IngestResponse,
    IngestStatusResponse,
    TemplateInfo,
    ValidationIssue
)
from services.exceptions import ResourceNotFoundError
from services.logger_config import custom_logger as logger
from services.ingest_utils import HISTORY_DEFAULT_LIMIT
from services.clients import CLIENT_FRAME_COLUMNS, sync_master
from services.ingest import parse_and_validate
from services.ingest import parse_frame as parse_sales_frame
from services.ingest_files import serialize_dataframe
from services.ingest_utils import (
    content_fingerprint,
    download_template_bytes,
    find_dataset_by_fingerprint,
    get_owned_dataset,
    list_datasets_for_owner,
    persist_dataset,
    read_stored_frame
)
from services.utils import audit_event, delete_stored_file, handle_service_errors

# The companion sheets of a sales upload, in the order they are read. Each
# one is a pipeline over its own sheet and the spec that says how to store it.

# pylint: disable=too-many-arguments, too-many-positional-arguments
@handle_service_errors('INGEST')
@audit_event('INGEST', 'Dataset', 'UPLOAD')
async def ingest_excel_controller(
    dynamodb_resource: ServiceResource,
    file_bytes: bytes,
    filename: str,
    current_user: str,
    auth_token: str,
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
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            current_user (str): Authenticated user email (owner of the dataset).

        Returns:
            IngestResponse: Public payload with the summary and per-row issues.
    '''
    # The same file uploaded twice is the same dataset, not a second one: it
    # used to mint a new identifier, a new copy in S3 and a new history row
    # every time, with nothing telling the user they already had it.
    fingerprint = content_fingerprint(file_bytes)
    existing = find_dataset_by_fingerprint(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        fingerprint = fingerprint
    )
    if existing is not None:
        message = (f'Dataset {existing["dataset_id"]} already holds this exact '
                   f'file for {current_user}; returning it.')
        logger.info(message)
        return to_ingest_response(existing, already_stored = True)

    result = parse_and_validate(file_bytes, filename)
    is_valid = not result.issues

    file_s3_key: str | None = None
    if is_valid:
        # The client master learns from the file and then completes it. A
        # company that uploaded coordinates once should not have to upload them
        # again to keep Routes alive, and an export that drops a column must
        # not blank what is already known about the client.
        result = replace(result, accepted = sync_master(
            dynamodb_resource = dynamodb_resource,
            owner_email = current_user,
            frame = result.accepted,
            columns = CLIENT_FRAME_COLUMNS,
            source = ClientSource.FILE
        ))
        # Store the NORMALIZED dataframe (canonical columns, ids filled) so every
        # downstream service reads a clean, uniform dataset without re-mapping.
        file_s3_key = store_frame(result.accepted, 'normalized', auth_token)

    persisted = persist_dataset(
        dynamodb_resource = dynamodb_resource,
        payload = {
            'owner_email': current_user,
            'status': 'validated' if is_valid else 'failed',
            'file_s3_key': file_s3_key,
            'template_version': TEMPLATE_VERSION,
            'file_fingerprint': fingerprint,
            **result.summary.model_dump(),
            'issues': [issue.model_dump(mode = 'json') for issue in result.issues]
        }
    )

    return to_ingest_response(persisted)


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Dataset', 'UPLOAD_S3')
async def ingest_excel_from_s3_controller(
    dynamodb_resource: ServiceResource,
    file_key: str,
    file_name: str,
    current_user: str,
    auth_token: str,
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
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            IngestResponse: Public payload with the summary and per-row issues.
    '''
    # FILES owns the bucket: the object comes back as rows, not as bytes.
    raw = read_stored_frame(file_key, auth_token)

    # Same rule as the direct upload: identical content is the same dataset.
    # Fingerprinted over the canonical rows and not the raw bytes, so the same
    # data sent as .xlsx or as .csv is recognised as the one dataset it is.
    fingerprint = content_fingerprint(serialize_dataframe(raw, 'raw.csv'))
    existing = find_dataset_by_fingerprint(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        fingerprint = fingerprint
    )
    if existing is not None:
        message = (f'Dataset {existing["dataset_id"]} already holds this exact '
                   f'file for {current_user}; returning it.')
        logger.info(message)
        return to_ingest_response(existing, already_stored = True)

    result = parse_sales_frame(raw, file_name)
    has_valid_rows = len(result.accepted) > 0
    if has_valid_rows:
        result = replace(result, accepted = sync_master(
            dynamodb_resource = dynamodb_resource,
            owner_email = current_user,
            frame = result.accepted,
            columns = CLIENT_FRAME_COLUMNS,
            source = ClientSource.FILE
        ))

    # Accepted rows feed analytics, forecast and routes; the rejected ones go
    # to their own CSV so the client can fix just those and re-upload.
    normalized_key = store_frame(result.accepted, 'normalized', auth_token)
    rejected_key = store_frame(result.rejected, 'rejected', auth_token)

    persisted = persist_dataset(
        dynamodb_resource = dynamodb_resource,
        payload = {
            'owner_email': current_user,
            'status': 'validated' if has_valid_rows else 'failed',
            'file_s3_key': normalized_key,
            'rejected_s3_key': rejected_key,
            'template_version': TEMPLATE_VERSION,
            'file_fingerprint': fingerprint,
            **result.summary.model_dump(),
            'issues': [
                issue.model_dump(mode = 'json')
                for issue in result.issues[:MAX_ISSUES_ON_RESPONSE]
            ]
        }
    )

    # The staged upload is temporary: its rows now live in the normalized
    # dataset, so the raw copy is deleted instead of piling up in the bucket.
    delete_stored_file(file_key, auth_token)
    return to_ingest_response(persisted)


@handle_service_errors('INGEST', with_log = False)
async def download_rejected_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    auth_token: str
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
        raise ResourceNotFoundError(detail = IngestError.NO_REJECTED_ROWS.value)
    return serialize_dataframe(
        read_stored_frame(str(rejected_key), auth_token), 'rejected.csv'
    )


@handle_service_errors('INGEST')
async def list_datasets_controller(
    dynamodb_resource: ServiceResource,
    request: Request, # pylint: disable=unused-argument
    current_user: str, # pylint: disable=unused-argument
    limit: int = HISTORY_DEFAULT_LIMIT
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
    current_user: str # pylint: disable=unused-argument
) -> IngestStatusResponse:
    '''
        Controller to retrieve the status of a previously ingested dataset.
    '''
    item = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    stored_collections = item.get('collections_summary')
    stored_stock = item.get('stock_summary')
    stored_visits = item.get('visits_summary')
    return IngestStatusResponse(
        dataset_id = item['dataset_id'],
        status = item['status'],
        owner_email = item['owner_email'],
        file_s3_key = item.get('file_s3_key') or '',
        collections = (
            CollectionsSummary(**native_numbers(stored_collections))
            if stored_collections else None
        ),
        stock = (
            StockSummary(**native_numbers(stored_stock))
            if stored_stock else None
        ),
        visits = (
            VisitsSummary(**native_numbers(stored_visits))
            if stored_visits else None
        ),
        summary = summary_of(item),
        issues = [ValidationIssue(**issue) for issue in item.get('issues', [])],
        created_at = item['created_at']
    )


@handle_service_errors('INGEST', with_log = False)
async def download_template_controller(
    contract: str,
    request: Request, # pylint: disable=unused-argument
    current_user: str # pylint: disable=unused-argument
) -> bytes:
    '''
        Reads one contract's template from the default bucket so the route can
        return it. Decorated with `with_log = False`: the event is still shipped
        to EVENTS, but the binary file body is not logged.

        This is the one object read straight from the bucket and not through
        FILES, and the rule in `CLAUDE.md` §9 names the case: it is a STATIC
        file the client downloads, identical for everyone, and putting a parse
        and a second hop in front of it would only make it slower.

        Args:
            contract (str): Which template — ventas, cobros, stock or visitas.

        Returns:
            bytes: Raw .xlsx content of the stored template.
    '''
    return download_template_bytes(template_key(contract))


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
        download_url = f'/v1/ingest/template/file/{SALES_TEMPLATE}',
        required_columns = list(REQUIRED_COLUMNS),
        optional_columns = list(OPTIONAL_COLUMNS)
    )
