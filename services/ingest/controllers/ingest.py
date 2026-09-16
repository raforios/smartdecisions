'''
    Ingest controllers.
'''
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.ingest import (
    OPTIONAL_COLUMNS,
    REQUIRED_COLUMNS,
    TEMPLATE_VERSION,
    CollectionsResponse,
    CollectionsSummary,
    IngestError,
    StockResponse,
    StockSummary,
    DatasetListResponse,
    DatasetSummary,
    IngestResponse,
    IngestStatusResponse,
    IngestSummary,
    TemplateInfo,
    ValidationIssue
)
from services.exceptions import ResourceNotFoundError
from services.logger_config import custom_logger as logger
from services.ingest_utils import HISTORY_DEFAULT_LIMIT
from services.collections import parse_and_validate as parse_collections
from services.stock import parse_and_validate as parse_stock
from services.ingest import (
    parse_and_validate,
    parse_and_validate_partial,
    read_file,
    serialize_dataframe
)
from services.ingest_utils import (
    attach_to_dataset,
    download_bytes,
    content_fingerprint,
    find_dataset_by_fingerprint,
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
ENV_VARS = load_and_validate_env_vars({
    'MAX_ISSUES_ON_RESPONSE': int,
    'TEMPLATE_S3_KEY': str,
})
MAX_ISSUES_ON_RESPONSE = ENV_VARS['MAX_ISSUES_ON_RESPONSE']
# The MIME type of the rejected-rows download. It stays in the code because it
# describes the format of the file, not a decision anybody would take
# differently: a CSV is served as a CSV.
CSV_CONTENT_TYPE = 'text/csv'
# The template is a static object in the default bucket, not something the
# service builds: the format is fixed and the client is the one who complies
# with it. Changing it means changing business logic, so it moves over time and
# never at runtime.
TEMPLATE_S3_KEY = ENV_VARS['TEMPLATE_S3_KEY']


def _native_numbers(stored: Dict[str, Any]) -> Dict[str, Any]:
    '''
        Turns the Decimals DynamoDB returns back into plain numbers.

        Args:
            stored (Dict[str, Any]): Attribute map as it came from the table.

        Returns:
            Dict[str, Any]: The same map, with numbers Pydantic accepts.
    '''
    return {
        key: float(value) if isinstance(value, Decimal) else value
        for key, value in stored.items()
    }


def _to_response(
    item: Dict[str, Any],
    already_stored: bool = False
) -> IngestResponse:
    '''
        Maps a persisted DynamoDB item into the public IngestResponse schema.

        Args:
            item (Dict[str, Any]): Stored dataset record.
            already_stored (bool): True when the upload matched a dataset the
                caller already had, so the client can say so instead of
                reporting a load that did not happen.

        Returns:
            IngestResponse: Public payload.
    '''
    return IngestResponse(
        already_stored = already_stored,
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
        return _to_response(existing, already_stored = True)

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
            'file_fingerprint': fingerprint,
            **result.summary.model_dump(),
            'issues': [issue.model_dump(mode = 'json') for issue in result.issues]
        }
    )

    response = _to_response(persisted)
    if is_valid:
        response.collections = await _collections_in_upload(
            dynamodb_resource = dynamodb_resource,
            dataset = persisted,
            upload = (file_bytes, filename),
            sales = result.accepted
        )
    return response


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

    # Same rule as the direct upload: identical content is the same dataset.
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
        return _to_response(existing, already_stored = True)

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
            'file_fingerprint': fingerprint,
            **result.summary.model_dump(),
            'issues': [
                issue.model_dump(mode = 'json')
                for issue in result.issues[:MAX_ISSUES_ON_RESPONSE]
            ]
        }
    )
    return _to_response(persisted)


async def _collections_in_upload(
    dynamodb_resource: ServiceResource,
    dataset: Dict[str, Any],
    upload: tuple[bytes, str],
    sales: Any
) -> Optional[CollectionsSummary]:
    '''
        Loads the payments sheet that came inside a sales upload, if any.

        The workbook the client downloads carries both sheets, so returning it
        filled answers both contracts in one upload — which is the product's
        thesis: one load feeds every module. A file without that sheet reports
        nothing at all: whoever sells cash should not have to know the contract
        exists.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset (Dict[str, Any]): The dataset just persisted.
            upload (tuple[bytes, str]): The uploaded content and its filename.
            sales (pd.DataFrame): The accepted sales rows.

        Returns:
            CollectionsSummary | None: The summary of what was loaded, or None
                when the upload carried no payments.
    '''
    file_bytes, filename = upload
    collections = parse_collections(file_bytes, filename, sales, auto = True)
    if len(collections.accepted) == 0:
        return None
    stored = await _store_collections(dynamodb_resource, dataset, collections, filename)
    return stored.summary


def _load_sales_frame(dataset: Dict[str, Any]) -> Any:
    '''
        Reads the normalized sales rows of a dataset back from S3.

        The payments have to be married against what was actually stored, not
        against the file the client happens to be holding: the stored frame is
        the one every other service reads.

        Args:
            dataset (Dict[str, Any]): The dataset item.

        Returns:
            pd.DataFrame: The normalized sales rows.

        Raises:
            ResourceNotFoundError: If the dataset has no stored file.
    '''
    file_key = dataset.get('file_s3_key')
    if not file_key:
        raise ResourceNotFoundError(detail = IngestError.DATASET_NOT_FOUND.value)
    return read_file(download_bytes(file_key), str(file_key))


async def _store_collections(
    dynamodb_resource: ServiceResource,
    dataset: Dict[str, Any],
    result: Any,
    filename: str
) -> CollectionsResponse:
    '''
        Stores an accepted collections load and attaches it to its dataset.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset (Dict[str, Any]): Dataset the payments belong to.
            result (CollectionsResult): Outcome of the collections pipeline.
            filename (str): Original filename, for the log.

        Returns:
            CollectionsResponse: What got in, what did not, and why.
    '''
    dataset_id = str(dataset['dataset_id'])
    has_rows = len(result.accepted) > 0

    collections_key: Optional[str] = None
    if has_rows:
        collections_key = upload_bytes(
            file_key = f'ingest/collections/{uuid4().hex}.csv',
            data = serialize_dataframe(result.accepted, 'collections.csv'),
            content_type = CSV_CONTENT_TYPE
        )
        attach_to_dataset(
            dynamodb_resource = dynamodb_resource,
            dataset_id = dataset_id,
            payload = {
                'collections_s3_key': collections_key,
                'collections_summary': result.summary.model_dump(),
                'collections_issues': [
                    issue.model_dump(mode = 'json')
                    for issue in result.issues[:MAX_ISSUES_ON_RESPONSE]
                ]
            }
        )

    message = (f'Collections load for dataset {dataset_id} from "{filename}": '
               f'{result.summary.valid_rows} row(s), '
               f'{len(result.issues)} issue(s).')
    logger.info(message)

    return CollectionsResponse(
        dataset_id = dataset_id,
        status = 'validated' if has_rows else 'failed',
        collections_s3_key = collections_key,
        summary = result.summary,
        issues = result.issues[:MAX_ISSUES_ON_RESPONSE]
    )


@handle_service_errors('INGEST')
async def ingest_collections_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    file_bytes: bytes,
    filename: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> CollectionsResponse:
    '''
        Loads a payments file against an existing sales dataset.

            1. Read the dataset the caller owns, and its stored sales rows.
            2. Validate the payments and marry them by invoice number.
            3. Store the accepted rows and attach them to the dataset.

        A separate call and not part of the sales upload because of when the
        data exists: an invoice at 90 days is collected three months after the
        file that registered it, and in instalments.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the payments belong to.
            file_bytes (bytes): Raw content of the uploaded file.
            filename (str): Original filename.
            current_user (str): Authenticated caller and owner of the dataset.

        Returns:
            CollectionsResponse: Summary of the load and its issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    result = parse_collections(file_bytes, filename, _load_sales_frame(dataset))
    return await _store_collections(dynamodb_resource, dataset, result, filename)


@handle_service_errors('INGEST')
async def ingest_stock_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    file_bytes: bytes,
    filename: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> StockResponse:
    '''
        Loads a stock snapshot against an existing sales dataset.

            1. Read the dataset the caller owns, and its stored sales rows.
            2. Validate the snapshot and marry it to the product catalogue.
            3. Store the accepted rows and attach them to the dataset.

        Its own endpoint because of cadence: the sales file is loaded once and
        the stock changes every day. A new load REPLACES the previous snapshot
        —the dataset keeps one `stock_s3_key`— so what is reported is always
        the latest photo and not an accumulation nobody can tell apart.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the snapshot belongs to.
            file_bytes (bytes): Raw content of the uploaded file.
            filename (str): Original filename.
            current_user (str): Authenticated caller and owner of the dataset.

        Returns:
            StockResponse: Summary of the load and its issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    result = parse_stock(file_bytes, filename, _load_sales_frame(dataset))
    has_rows = len(result.accepted) > 0

    stock_key: Optional[str] = None
    if has_rows:
        stock_key = upload_bytes(
            file_key = f'ingest/stock/{uuid4().hex}.csv',
            data = serialize_dataframe(result.accepted, 'stock.csv'),
            content_type = CSV_CONTENT_TYPE
        )
        attach_to_dataset(
            dynamodb_resource = dynamodb_resource,
            dataset_id = dataset_id,
            payload = {
                'stock_s3_key': stock_key,
                'stock_summary': result.summary.model_dump(),
                'stock_issues': [
                    issue.model_dump(mode = 'json')
                    for issue in result.issues[:MAX_ISSUES_ON_RESPONSE]
                ]
            }
        )

    message = (f'Stock load for dataset {dataset_id} from "{filename}": '
               f'{result.summary.valid_rows} row(s), {len(result.issues)} issue(s).')
    logger.info(message)

    return StockResponse(
        dataset_id = dataset_id,
        status = 'validated' if has_rows else 'failed',
        stock_s3_key = stock_key,
        summary = result.summary,
        issues = result.issues[:MAX_ISSUES_ON_RESPONSE]
    )


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
    stored_collections = item.get('collections_summary')
    stored_stock = item.get('stock_summary')
    return IngestStatusResponse(
        dataset_id = item['dataset_id'],
        status = item['status'],
        owner_email = item['owner_email'],
        file_s3_key = item.get('file_s3_key') or '',
        collections = (
            CollectionsSummary(**_native_numbers(stored_collections))
            if stored_collections else None
        ),
        stock = (
            StockSummary(**_native_numbers(stored_stock))
            if stored_stock else None
        ),
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
