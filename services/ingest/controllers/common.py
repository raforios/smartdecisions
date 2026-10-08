'''
    What the ingest controllers share: the environment they read, the helpers
    that turn stored items back into DTOs, and the one way a companion load
    —payments, stock, visits— is stored and attached to its dataset.

    The three companions are the same operation over a different sheet: store
    the accepted rows as CSV, hang the key, the summary and the issues off the
    dataset item, answer with the summary. Stating it once here keeps the three
    from drifting apart, which is exactly what happened when the S3 upload path
    forgot two of them.
'''
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pandas as pd
from boto3.resources.base import ServiceResource
from pydantic import BaseModel

from schemas.ingest import (
    TEMPLATE_VERSION,
    IngestError,
    IngestResponse,
    IngestSummary,
    ValidationIssue
)
from schemas.clients import ClientSource
from services.clients import CLIENT_FRAME_COLUMNS, sync_master
from services.environment import load_and_validate_env_vars
from services.exceptions import ResourceNotFoundError
from services.ingest_files import serialize_dataframe
from services.ingest_utils import (
    attach_to_dataset,
    persist_dataset,
    read_stored_frame,
    upload_bytes
)
from services.logger_config import custom_logger as logger

# Only a slice of the issues travels in the JSON response / DynamoDB item
# (400 KB limit); the full set lives in the rejected CSV in S3.
ENV_VARS = load_and_validate_env_vars({
    'MAX_ISSUES_ON_RESPONSE': int,
    'TEMPLATES_S3_PREFIX': str,
})
MAX_ISSUES_ON_RESPONSE = ENV_VARS['MAX_ISSUES_ON_RESPONSE']
# The MIME type of the rejected-rows download. It stays in the code because it
# describes the format of the file, not a decision anybody would take
# differently: a CSV is served as a CSV.
CSV_CONTENT_TYPE = 'text/csv'
# What the log calls a load that came through the API instead of a file.
API_ORIGIN = 'API'
# The templates are static objects in the default bucket, not something the
# service builds: the format is fixed and the client is the one who complies
# with it. There is one per contract —ventas, cobros, stock, visitas— because
# a client who only sends yesterday's stock should not download a book with
# three sheets they will never fill in.
TEMPLATES_S3_PREFIX = ENV_VARS['TEMPLATES_S3_PREFIX'].strip('/')


def template_key(contract: str) -> str:
    '''
        The S3 key of one contract's template.

        Args:
            contract (str): Contract name, as the schema declares it.

        Returns:
            str: Full object key.
    '''
    return f'{TEMPLATES_S3_PREFIX}/plantilla_{contract}.xlsx'


def summary_of(item: dict[str, Any]) -> IngestSummary:
    '''
        The summary a stored dataset carries.

        Both the ingest response and the status response publish it, so it is
        read out of the item once: written twice, the two would answer the
        same question differently the first time a field is added.

        Args:
            item (dict[str, Any]): Stored dataset record.

        Returns:
            IngestSummary: Its counts and its date range.
    '''
    return IngestSummary(
        total_rows = item.get('total_rows', 0),
        valid_rows = item.get('valid_rows', 0),
        error_rows = item.get('error_rows', 0),
        unique_points_of_sale = item.get('unique_points_of_sale', 0),
        unique_products = item.get('unique_products', 0),
        date_range_start = item.get('date_range_start'),
        date_range_end = item.get('date_range_end')
    )


def to_ingest_response(
    item: dict[str, Any],
    already_stored: bool = False
) -> IngestResponse:
    '''
        Maps a persisted DynamoDB item into the public IngestResponse schema.

        Args:
            item (dict[str, Any]): Stored dataset record.
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
        summary = summary_of(item),
        issues = [ValidationIssue(**issue) for issue in item.get('issues', [])],
        created_at = item['created_at']
    )


def store_frame(
    frame: Any,
    folder: str,
    auth_token: str
) -> str | None:
    '''
        Stores a frame as a CSV under its folder and returns the object key.

        The accepted rows and the rejected ones are stored the same way and
        differ only in the folder, so it is one function and not two blocks
        that drift.

        Args:
            frame (pd.DataFrame): Rows to store.
            folder (str): Folder under the ingest prefix.
            auth_token (str): The caller's Authorization header.

        Returns:
            str | None: The object key, or None when there is nothing to store.
    '''
    if frame.empty:
        return None
    return upload_bytes(
        file_key = f'ingest/{folder}/{uuid4().hex}.csv',
        data = serialize_dataframe(frame, f'{folder}.csv'),
        content_type = CSV_CONTENT_TYPE,
        auth_token = auth_token
    )


def rows_frame(rows: Any) -> Any:
    '''
        Rows posted by an ERP as a canonical frame.

        The DTOs already carry the canonical names, so there is no header
        mapping to do: this is where the API skips the only step the file
        needs and rejoins the shared path.

        Args:
            rows (list[BaseModel]): Rows as the ERP posted them.

        Returns:
            pd.DataFrame: One row per DTO, canonical columns.
    '''
    return pd.DataFrame([row.model_dump() for row in rows])


def stored_companion_frame(
    dataset: dict[str, Any],
    spec: CompanionSpec,
    auth_token: str
) -> Any | None:
    '''
        The rows a dataset already holds for one companion.

        Args:
            dataset (dict[str, Any]): The dataset item.
            spec (CompanionSpec): Which companion to read.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            pd.DataFrame | None: The stored rows, or None when there are
                none or the companion cannot be merged.
    '''
    stored_key = dataset.get(f'{spec.name}_s3_key')
    if not stored_key or not spec.merge_keys:
        return None
    previous = read_stored_frame(str(stored_key), auth_token)
    return None if previous.empty else previous


def native_numbers(stored: dict[str, Any]) -> dict[str, Any]:
    '''
        Turns the Decimals DynamoDB returns back into plain numbers.

        Args:
            stored (dict[str, Any]): Attribute map as it came from the table.

        Returns:
            dict[str, Any]: The same map, with numbers Pydantic accepts.
    '''
    return {
        key: float(value) if isinstance(value, Decimal) else value
        for key, value in stored.items()
    }


def load_sales_frame(
    dataset: dict[str, Any],
    auth_token: str
) -> Any:
    '''
        Reads the normalized sales rows of a dataset back from S3.

        A companion load has to be married against what was actually stored,
        not against the file the client happens to be holding: the stored frame
        is the one every other service reads.

        Args:
            dataset (dict[str, Any]): The dataset item.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            pd.DataFrame: The normalized sales rows.

        Raises:
            ResourceNotFoundError: If the dataset has no stored file.
    '''
    file_key = dataset.get('file_s3_key')
    if not file_key:
        raise ResourceNotFoundError(detail = IngestError.DATASET_NOT_FOUND.value)
    return read_stored_frame(str(file_key), auth_token)


@dataclass(frozen = True)
class CompanionSpec:
    '''
        How one companion contract is stored: the name that prefixes its S3
        folder and its dataset attributes, and the response it answers with.

        The response models are parallel on purpose —`<name>_s3_key`, summary,
        issues— so one storage routine serves the three.
    '''
    name: str
    response_model: type[BaseModel]
    # What makes two rows THE SAME row. It is what lets an ERP push every day
    # without counting a payment twice on a retry, and what makes a stock push
    # for today replace today and leave last week alone. Empty means the
    # companion cannot be merged and a push always replaces.
    merge_keys: tuple[str, ...] = ()
    # Whether the sheet names clients and therefore feeds the master. Visits
    # do —they are the ones that reach a prospect nobody billed, and the ones
    # that carry the GPS reading of the door—; objectives do, because an
    # objective is set for the client the company means to activate. Payments
    # name invoices and the stock names products.
    #
    # It is READ here, in `store_companion`, and nowhere else. It used to be a
    # comment pretending to be configuration: every door fed the master with
    # its own copy of the call, and the `from-s3` door simply forgot, so the
    # same file loaded through a different endpoint gave a different master.
    names_clients: bool = False


async def store_companion(
    dynamodb_resource: ServiceResource,
    dataset: dict[str, Any],
    result: Any,
    spec: CompanionSpec,
    origin: tuple[str, str]
) -> BaseModel:
    '''
        Stores an accepted companion load and attaches it to its dataset.

        A new load REPLACES the previous one of the same kind: the dataset
        keeps one key per companion, so what the analysis reads is always the
        latest file and not an accumulation nobody can tell apart.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset (dict[str, Any]): Dataset the load belongs to.
            result (Any): Outcome of the companion pipeline: `accepted`,
                `issues` and `summary`.
            spec (CompanionSpec): Which companion this is.
            origin (tuple[str, str]): Filename for the log and the caller's
                Authorization header, forwarded to FILES.

        Returns:
            BaseModel: The companion's response: what got in, what did not,
                and why.
    '''
    filename, auth_token = origin
    dataset_id = str(dataset['dataset_id'])
    if spec.names_clients and len(result.accepted) > 0:
        result = with_known_clients(
            dynamodb_resource, str(dataset['owner_email']), result,
            ClientSource.API if filename == API_ORIGIN else ClientSource.FILE
        )
    has_rows = len(result.accepted) > 0
    issues = result.issues[:MAX_ISSUES_ON_RESPONSE]

    stored_key: str | None = None
    if has_rows:
        stored_key = upload_bytes(
            file_key = f'ingest/{spec.name}/{uuid4().hex}.csv',
            data = serialize_dataframe(result.accepted, f'{spec.name}.csv'),
            content_type = CSV_CONTENT_TYPE,
            auth_token = auth_token
        )
        attach_to_dataset(
            dynamodb_resource = dynamodb_resource,
            dataset_id = dataset_id,
            payload = {
                f'{spec.name}_s3_key': stored_key,
                f'{spec.name}_summary': result.summary.model_dump(),
                f'{spec.name}_issues': [issue.model_dump(mode = 'json') for issue in issues]
            }
        )

    message = (f'{spec.name.capitalize()} load for dataset {dataset_id} from "{filename}": '
               f'{result.summary.valid_rows} row(s), {len(result.issues)} issue(s).')
    logger.info(message)

    return spec.response_model(
        dataset_id = dataset_id,
        status = 'validated' if has_rows else 'failed',
        summary = result.summary,
        issues = issues,
        **{f'{spec.name}_s3_key': stored_key}
    )


def with_known_clients(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    result: Any,
    source: ClientSource
) -> Any:
    '''
        The validation result with its accepted rows passed through the client
        master: the master learns the clients and fills in what it already
        knew. Every door that loads sales goes through here.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            owner_email (str): The owner.
            result (Any): A validation result with `accepted` rows.
            source (ClientSource): The door the rows came through.

        Returns:
            Any: The same result, with the completed rows.
    '''
    return replace(result, accepted = sync_master(
        dynamodb_resource = dynamodb_resource,
        owner_email = owner_email,
        frame = result.accepted,
        columns = CLIENT_FRAME_COLUMNS,
        source = source
    ))


def store_new_dataset(
    dynamodb_resource: ServiceResource,
    owner: tuple[str, str],
    result: Any,
    origin: tuple[str, ClientSource]
) -> dict[str, Any]:
    '''
        Stores a sales dataset that did not exist: the client master learns
        from the accepted rows, the accepted and rejected rows go to S3, and
        the dataset is persisted.

        One function for every door that creates a dataset —a file read from
        S3, lines pushed by an ERP— so they cannot drift apart.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            owner (tuple[str, str]): The owner, and the Authorization header
                forwarded to FILES.
            result (Any): The partial validation (`ParseResult`).
            origin (tuple[str, ClientSource]): The content fingerprint, and
                the door the rows came through.

        Returns:
            dict[str, Any]: The persisted dataset.
    '''
    current_user, auth_token = owner
    fingerprint, source = origin
    has_valid_rows = len(result.accepted) > 0
    if has_valid_rows:
        result = with_known_clients(dynamodb_resource, current_user, result, source)
    # Accepted rows feed analytics, forecast and routes; the rejected ones go
    # to their own CSV so the client can fix just those and send them again.
    normalized_key = store_frame(result.accepted, 'normalized', auth_token)
    rejected_key = store_frame(result.rejected, 'rejected', auth_token)
    return persist_dataset(
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
