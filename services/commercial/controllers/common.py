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
from collections.abc import Callable
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pandas as pd
from boto3.resources.base import ServiceResource
from fastapi import Request
from pydantic import BaseModel

from core.utils import load_parameters
from core.environment import load_and_validate_env_vars
from core.exceptions import ResourceNotFoundError, ServiceUnavailableError
from core.logger_config import custom_logger as logger
from core.utils import DEFAULT_BUCKET_PATH, delete_stored_file, store_file
from schemas.commercial import (
    TEMPLATE_VERSION,
    IngestError,
    IngestResponse,
    IngestSummary,
    ValidationIssue
)
from schemas.channels import LoadMode
from schemas.clients import ClientSource
from schemas.products import ProductSource
from services.clients import CLIENT_FRAME_COLUMNS, sync_master
from services.products import sync_products
from services.load_files import serialize_dataframe
from services.modules import sales_profile
from services.commercial_utils import (
    attach_to_dataset,
    content_fingerprint,
    find_dataset_by_fingerprint,
    persist_dataset,
    read_stored_frame
)

# Only a slice of the issues travels in the JSON response / DynamoDB item
# (400 KB limit); the full set lives in the rejected CSV in S3.
ENV_VARS = {
    **load_and_validate_env_vars({
        'TEMPLATES_S3_PREFIX': str
    }),
    **load_parameters({
        'MAX_ISSUES_ON_RESPONSE': int
    })
}
MAX_ISSUES_ON_RESPONSE = ENV_VARS['MAX_ISSUES_ON_RESPONSE']
# What the log calls a load that came through the API instead of a file.
API_ORIGIN = 'API'
# The templates are static objects in the default bucket, not something the
# service builds: the format is fixed and the client is the one who complies
# with it. There is one per contract (sales, collections, stock, visits) because
# a client who only sends yesterday's stock should not download a book with
# three sheets they will never fill in.
TEMPLATES_S3_PREFIX = ENV_VARS['TEMPLATES_S3_PREFIX'].strip('/')


def caller_token(request: Request | None) -> str:
    '''
        The caller's Authorization header, forwarded to FILES, ML_FUNCTIONS or
        QUOTES so they answer for the real user; empty when there is no request.

        Args:
            request (Request | None): The incoming request.

        Returns:
            str: The header, or an empty string.
    '''
    return (request.headers.get('authorization') if request is not None else None) or ''


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
    return store_file(
        file_key = f'{DEFAULT_BUCKET_PATH}/{folder}/{uuid4().hex}.csv',
        data = serialize_dataframe(frame, f'{folder}.csv'),
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
    # Whether every load lands on top of what is stored instead of replacing
    # it, by the merge keys. The stock does: each photo is kept with its date,
    # so the inventory has a history and the latest date is still today's.
    keeps_history: bool = False


@dataclass(frozen = True)
class LoadContext:
    '''
        What a merge needs to know, grouped so the signature stays readable.
    '''
    dataset: dict
    spec: CompanionSpec
    mode: LoadMode
    sales: Any
    validate_rows: Callable[..., Any]
    origin: str
    auth_token: str


def merge_if_appending(
    context: LoadContext,
    result: Any
) -> Any:
    '''
        Lands a load on top of what the dataset already holds.

        The summary ends up describing EVERYTHING stored, because that is what
        the analysis reads; the issues keep describing only this load, because
        those are the rows the caller can still fix. Reporting this load's own
        count as the total would say five payments when the dataset holds five
        hundred.

        Args:
            context (LoadContext): Dataset, spec, mode and how to re-validate.
            result (Any): Outcome of validating what just arrived.

        Returns:
            Any: The same result, or the merged one with this load's issues.
    '''
    # A companion that keeps its history never loses a day, whatever the mode.
    if context.mode is not LoadMode.APPEND and not context.spec.keeps_history:
        return result
    previous = stored_companion_frame(context.dataset, context.spec,
                                      context.auth_token)
    if previous is None:
        return result

    # The stored rows come back from CSV as text, so they are put through the
    # very same contract before being compared: a date that is a Timestamp on
    # one side and a string on the other is never equal, and the merge key
    # would silently stop deduplicating. That bug was caught by the retry test.
    aligned = context.validate_rows(previous, context.sales, context.origin).accepted
    merged = pd.concat([aligned, result.accepted], ignore_index = True)
    keys = [key for key in context.spec.merge_keys if key in merged.columns]
    if keys:
        merged = merged.drop_duplicates(subset = keys, keep = 'last')
    merged = merged.reset_index(drop = True)

    message = (f'{context.spec.name.capitalize()} merge: {len(aligned)} stored + '
               f'{len(result.accepted)} new = {len(merged)} row(s).')
    logger.info(message)
    if len(merged) == len(result.accepted):
        return result
    whole = context.validate_rows(merged, context.sales, context.origin)
    return replace(whole, issues = result.issues)


def dataset_with_content(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    fingerprint: str
) -> IngestResponse | None:
    '''
        The dataset that already holds this exact content, as the answer to
        loading it again: the same content twice is the same dataset, not a
        second identifier, a second copy in S3 and a second history row.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            owner_email (str): The owner, part of the lookup.
            fingerprint (str): The content's fingerprint.

        Returns:
            IngestResponse | None: That dataset, or None when it is new.
    '''
    existing = find_dataset_by_fingerprint(
        dynamodb_resource = dynamodb_resource,
        owner_email = owner_email,
        fingerprint = fingerprint
    )
    if existing is None:
        return None
    message = (f'Dataset {existing["dataset_id"]} already holds this content for '
               f'{owner_email}; returning it.')
    logger.info(message)
    return to_ingest_response(existing, already_stored = True)


def store_new_or_known(
    dynamodb_resource: ServiceResource,
    owner: tuple[str, str],
    frame: pd.DataFrame,
    validate: Callable[[pd.DataFrame], Any],
    source: ClientSource
) -> tuple[IngestResponse, bool]:
    '''
        A new dataset from rows that came without a file of their own —a
        staged file read through FILES, or lines an ERP posts—, or the one
        that already holds them. Fingerprinted over the canonical rows, so the
        same data sent as .xlsx, .csv or JSON is the one dataset it is.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            owner (tuple[str, str]): The owner, and the Authorization header
                forwarded to FILES.
            frame (pd.DataFrame): The rows as they came.
            validate (Callable[[pd.DataFrame], Any]): Their partial validation.
            source (ClientSource): The door the rows came through.

        Returns:
            tuple[IngestResponse, bool]: The dataset, and whether it is new.
    '''
    current_user, _ = owner
    fingerprint = content_fingerprint(serialize_dataframe(frame, 'raw.csv'))
    known = dataset_with_content(dynamodb_resource, current_user, fingerprint)
    if known is not None:
        return known, False
    persisted = store_new_dataset(dynamodb_resource, owner, validate(frame),
                                  (fingerprint, source))
    message = f'Dataset {persisted["dataset_id"]} created for {current_user}: {len(frame)} row(s).'
    logger.info(message)
    return to_ingest_response(native_numbers(persisted)), True


def retire_replaced_file(
    replaced_key: str | None,
    auth_token: str
) -> None:
    '''
        Removes, through FILES, the file a load has just replaced.

        A dataset keeps one key per file, so the previous object is unreachable
        once the new key is attached: left behind, every live sale would leave
        a whole copy of the dataset in the bucket. The new file is already in
        place, so a failure here is only logged —raising would make the queue
        retry a load that did get in, and append it twice.

        Args:
            replaced_key (str | None): The key the dataset held before; None
                when the dataset had no such file.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
    '''
    if not replaced_key:
        return
    try:
        delete_stored_file(replaced_key, auth_token)
    except ServiceUnavailableError as error:
        error_msg = f'Replaced file {replaced_key} left in the bucket: {error.detail}'
        logger.error(error_msg)


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
        result = with_known_masters(
            dynamodb_resource, str(dataset['owner_email']), result,
            ClientSource.API if filename == API_ORIGIN else ClientSource.FILE
        )
    has_rows = len(result.accepted) > 0
    issues = result.issues[:MAX_ISSUES_ON_RESPONSE]

    stored_key: str | None = None
    replaced_key = dataset.get(f'{spec.name}_s3_key')
    if has_rows:
        stored_key = store_file(
            file_key = f'{DEFAULT_BUCKET_PATH}/{spec.name}/{uuid4().hex}.csv',
            data = serialize_dataframe(result.accepted, f'{spec.name}.csv'),
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
        retire_replaced_file(replaced_key, auth_token)

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


def with_known_masters(
    dynamodb_resource: ServiceResource,
    owner_email: str,
    result: Any,
    source: ClientSource
) -> Any:
    '''
        The validation result with its accepted rows passed through the client
        and the product masters: each learns what the rows name and fills in
        what it already knew. Every door that loads sales goes through here; a
        frame without products leaves the product master as it was.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            owner_email (str): The owner.
            result (Any): A validation result with `accepted` rows.
            source (ClientSource): The door the rows came through.

        Returns:
            Any: The same result, with the completed rows.
    '''
    frame = sync_master(
        dynamodb_resource = dynamodb_resource,
        owner_email = owner_email,
        frame = result.accepted,
        columns = CLIENT_FRAME_COLUMNS,
        source = source
    )
    frame = sync_products(dynamodb_resource, owner_email, frame,
                          ProductSource.API if source is ClientSource.API else ProductSource.FILE)
    return replace(result, accepted = frame)


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
        result = with_known_masters(dynamodb_resource, current_user, result, source)
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
            'sales_profile': sales_profile(result.accepted).model_dump(),
            'template_version': TEMPLATE_VERSION,
            'file_fingerprint': fingerprint,
            **result.summary.model_dump(),
            'issues': [
                issue.model_dump(mode = 'json')
                for issue in result.issues[:MAX_ISSUES_ON_RESPONSE]
            ]
        }
    )
