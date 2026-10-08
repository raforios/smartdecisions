'''
    The companion contracts pushed as JSON by the client's ERP.

    The second integration channel. It exists because of cadence: the sales
    file is loaded once and payments, stock and visits change every day, so
    re-uploading a whole workbook to add yesterday's payments is a chore, not
    an integration.

    Nothing is validated here. Each push is turned into a canonical frame and
    handed to the very same `validate_rows` the uploaded file goes through, so
    the two channels are judged by one contract and answer with one set of
    codes. What this module adds is the merge: a push lands on top of what is
    stored, and the companion's own key decides what counts as a repeat.
'''
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

import pandas as pd
from boto3.resources.base import ServiceResource
from fastapi import Request
from pydantic import BaseModel

from controllers.collections import SPEC as COLLECTIONS
from controllers.objectives import SPEC as OBJECTIVES
from controllers.common import (
    API_ORIGIN,
    MAX_ISSUES_ON_RESPONSE,
    CompanionSpec,
    load_sales_frame,
    native_numbers,
    rows_frame,
    store_companion,
    store_frame,
    store_new_dataset,
    stored_companion_frame,
    to_ingest_response,
    with_known_clients
)
from controllers.stock import SPEC as STOCK
from controllers.visits import SPEC as VISITS
from schemas.clients import ClientSource
from schemas.channels import (
    CollectionsPushSchema,
    ObjectivesPushSchema,
    SalesPushSchema,
    SalesRowsSchema,
    IngestFromS3CompanionRequest,
    LoadMode,
    StockPushSchema,
    VisitsPushSchema
)
from schemas.ingest import (
    CollectionsResponse,
    ObjectivesResponse,
    IngestResponse,
    StockResponse,
    VisitsResponse
)
from services.collections import parse_frame as parse_collections_frame
from services.collections import validate_rows as validate_collections
from services.objectives import parse_frame as parse_objectives_frame
from services.objectives import prepare_rows as prepare_objectives
from services.objectives import validate_rows as validate_objectives
from services.ingest import prepare_rows as prepare_sales_rows
from services.ingest import validate_rows_partial
from services.ingest_files import serialize_dataframe
from services.ingest_utils import (
    attach_to_dataset,
    content_fingerprint,
    find_dataset_by_fingerprint,
    read_stored_frame,
    get_owned_dataset,
)
from services.stock import parse_frame as parse_stock_frame
from services.stock import prepare_rows as prepare_stock
from services.stock import validate_rows as validate_stock
from services.logger_config import custom_logger as logger
from services.utils import audit_event, delete_stored_file, handle_service_errors
from services.visits import parse_frame as parse_visits_frame
from services.visits import prepare_rows as prepare_visits
from services.visits import validate_rows as validate_visits

# Each companion's validator, by name, so the merge can re-summarize whatever
# it just merged without the caller having to hand it over twice.
_VALIDATORS: dict = {
    COLLECTIONS.name: validate_collections,
    OBJECTIVES.name: validate_objectives,
    STOCK.name: validate_stock,
    VISITS.name: validate_visits,
}


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

# The controller signature is fixed by the route, and the three push
# controllers are the same adapter over their own pipeline — as the three file
# controllers already are. What varies is the spec and the pipeline.
# pylint: disable=too-many-arguments, too-many-positional-arguments, duplicate-code


def _merge_if_appending(
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
    if context.mode is not LoadMode.APPEND:
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


async def _push(
    dynamodb_resource: ServiceResource,
    dataset: dict,
    push: Any,
    spec: CompanionSpec,
    pipeline: tuple[Callable[[pd.DataFrame], pd.DataFrame], Callable[..., Any], str]
) -> BaseModel:
    '''
        Runs one pushed load: validate, merge, store.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset (dict): The dataset the load belongs to.
            push (Any): The push payload: `mode` and `rows`.
            spec (CompanionSpec): Which companion this is.
            pipeline (tuple): Its `prepare_rows` and its `validate_rows`.

        Returns:
            BaseModel: The companion's response.
    '''
    prepare, validate_rows, auth_token = pipeline
    sales = load_sales_frame(dataset, auth_token)
    result = validate_rows(prepare(rows_frame(push.rows)), sales, API_ORIGIN)
    result = _merge_if_appending(
        LoadContext(dataset, spec, push.mode, sales, validate_rows,
                    API_ORIGIN, auth_token),
        result
    )
    return await store_companion(dynamodb_resource, dataset, result, spec,
                                 (API_ORIGIN, auth_token))


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Objectives', 'UPLOAD')
async def push_objectives_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    push: ObjectivesPushSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> ObjectivesResponse:
    '''
        The ERP posts the objectives the commercial team set.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the objectives belong to.
            push (ObjectivesPushSchema): Mode and rows.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            ObjectivesResponse: Summary of what is stored and this push's issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    return await _push(
        dynamodb_resource = dynamodb_resource,
        dataset = dataset,
        push = push,
        spec = OBJECTIVES,
        # The ERP sends a client NAME, like the template does; the identifier
        # is derived here, exactly as the file door derives it. An identity
        # prepare left `pos_id` missing and the validator with nothing to key
        # on.
        pipeline = (prepare_objectives, validate_objectives, auth_token)
    )


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Collections', 'UPLOAD')
async def push_collections_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    push: CollectionsPushSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> CollectionsResponse:
    '''
        The ERP posts the payments collected since the last push.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the payments belong to.
            push (CollectionsPushSchema): Mode and rows.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            CollectionsResponse: Summary of what is stored and this push's issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    return await _push(
        dynamodb_resource = dynamodb_resource,
        dataset = dataset,
        push = push,
        spec = COLLECTIONS,
        pipeline = (lambda frame: frame, validate_collections, auth_token)
    )


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Stock', 'UPLOAD')
async def push_stock_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    push: StockPushSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> StockResponse:
    '''
        The ERP posts the stock of the day.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the snapshot belongs to.
            push (StockPushSchema): Mode and rows.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            StockResponse: Summary of what is stored and this push's issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    return await _push(
        dynamodb_resource = dynamodb_resource,
        dataset = dataset,
        push = push,
        spec = STOCK,
        pipeline = (prepare_stock, validate_stock, auth_token)
    )


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Visits', 'UPLOAD')
async def push_visits_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    push: VisitsPushSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> VisitsResponse:
    '''
        The ERP posts the visits of the day.

        Like the visits file, this one also feeds the client master: it is the
        load that reaches a prospect nobody billed and that carries the GPS
        reading of the door.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the visits belong to.
            push (VisitsPushSchema): Mode and rows.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            VisitsResponse: Summary of what is stored and this push's issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )

    return await _push(
        dynamodb_resource = dynamodb_resource,
        dataset = dataset,
        push = push,
        spec = VISITS,
        pipeline = (prepare_visits, validate_visits, auth_token)
    )


async def _from_s3(
    dynamodb_resource: ServiceResource,
    dataset: dict,
    payload: IngestFromS3CompanionRequest,
    spec: CompanionSpec,
    parse: tuple[Callable[..., Any], str]
) -> BaseModel:
    '''
        Runs one companion file staged in S3: download, validate, merge, store.

        The binary never crosses API Gateway, which caps a request at about
        10 MB. FILES puts the object there with a pre-signed URL and this reads
        it by its key — the same door the sales file already had, and the only
        one that works for a real ERP export.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset (dict): The dataset the load belongs to.
            payload (IngestFromS3CompanionRequest): Object key, name and mode.
            spec (CompanionSpec): Which companion this is.
            parse (Callable): Its `parse_and_validate`.

        Returns:
            BaseModel: The companion's response.
    '''
    parse_rows, auth_token = parse
    sales = load_sales_frame(dataset, auth_token)
    # FILES owns the bucket: the staged object comes back as rows, not bytes.
    raw = read_stored_frame(payload.file_key, auth_token)
    result = parse_rows(raw, sales, payload.file_name)
    result = _merge_if_appending(
        LoadContext(dataset, spec, payload.mode, sales,
                    _VALIDATORS[spec.name], payload.file_name, auth_token),
        result
    )
    stored = await store_companion(
        dynamodb_resource, dataset, result, spec, (payload.file_name, auth_token)
    )
    # The staged upload is temporary: once its rows are in, leaving it behind
    # turns the bucket into a graveyard nobody dares clean. Same as TRADE.
    delete_stored_file(payload.file_key, auth_token)
    return stored


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Collections', 'UPLOAD')
async def ingest_collections_from_s3_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    payload: IngestFromS3CompanionRequest,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> CollectionsResponse:
    '''
        Loads a payments file already staged in S3 by FILES.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the payments belong to.
            payload (IngestFromS3CompanionRequest): Object key, name and mode.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            CollectionsResponse: Summary of the load and its issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    return await _from_s3(dynamodb_resource, dataset, payload, COLLECTIONS,
                          (parse_collections_frame, auth_token))


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Stock', 'UPLOAD')
async def ingest_objectives_from_s3_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    payload: IngestFromS3CompanionRequest,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> ObjectivesResponse:
    '''
        Loads an objectives file already staged in S3 by FILES.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the objectives belong to.
            payload (IngestFromS3CompanionRequest): Object key, name and mode.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            ObjectivesResponse: Summary of the load and its issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    return await _from_s3(dynamodb_resource, dataset, payload, OBJECTIVES,
                          (parse_objectives_frame, auth_token))


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Stock', 'UPLOAD')
async def ingest_stock_from_s3_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    payload: IngestFromS3CompanionRequest,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> StockResponse:
    '''
        Loads a stock file already staged in S3 by FILES.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the snapshot belongs to.
            payload (IngestFromS3CompanionRequest): Object key, name and mode.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            StockResponse: Summary of the load and its issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    return await _from_s3(dynamodb_resource, dataset, payload, STOCK,
                          (parse_stock_frame, auth_token))


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Visits', 'UPLOAD')
async def ingest_visits_from_s3_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    payload: IngestFromS3CompanionRequest,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> VisitsResponse:
    '''
        Loads a visits file already staged in S3 by FILES, and feeds the client
        master with what it says about the clients.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the visits belong to.
            payload (IngestFromS3CompanionRequest): Object key, name and mode.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            VisitsResponse: Summary of the load and its issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    stored = await _from_s3(dynamodb_resource, dataset, payload, VISITS,
                            (parse_visits_frame, auth_token))
    return stored


# A sales line IS its invoice and its product: one line per product per
# invoice. That is what lets an ERP push the same day twice —a retry, or a
# correction to one line— without the invoice ending up counted twice.
_SALES_MERGE_KEYS: tuple[str, ...] = ('order_id', 'product_id')


def _merge_sales(
    dataset: dict[str, Any],
    accepted: Any,
    auth_token: str
) -> Any:
    '''
        Lands pushed sales lines on top of the ones the dataset already holds.

        The stored rows are put through the same contract before comparing,
        because they come back from CSV as text and a date that is a Timestamp
        on one side and a string on the other never matches.

        Args:
            dataset (dict[str, Any]): The dataset item.
            accepted (pd.DataFrame): The lines just accepted.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            pd.DataFrame: Stored lines and new lines, deduplicated.
    '''
    stored_key = dataset.get('file_s3_key')
    if not stored_key:
        return accepted
    previous = read_stored_frame(str(stored_key), auth_token)
    if previous.empty:
        return accepted
    aligned = validate_rows_partial(previous, API_ORIGIN).accepted
    merged = pd.concat([aligned, accepted], ignore_index = True)
    keys = [key for key in _SALES_MERGE_KEYS if key in merged.columns]
    if keys:
        merged = merged.drop_duplicates(subset = keys, keep = 'last')
    message = (f'Sales merge: {len(aligned)} stored + {len(accepted)} pushed = '
               f'{len(merged)} line(s).')
    logger.info(message)
    return merged.reset_index(drop = True)


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Dataset', 'UPDATE')
async def push_sales_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    push: SalesPushSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> IngestResponse:
    '''
        The client's ERP posts sales lines into a dataset it already owns.

        The API door of the main contract. It runs the same partial-acceptance
        pipeline the uploaded file runs —invalid lines are set aside with their
        code and the rest load— and feeds the client master exactly the same
        way, so pushing rows and uploading a workbook cannot diverge.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Dataset the lines belong to.
            push (SalesPushSchema): Mode and rows.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            IngestResponse: The dataset as it now stands.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    result = validate_rows_partial(prepare_sales_rows(rows_frame(push.rows)), API_ORIGIN)
    result = with_known_clients(dynamodb_resource, current_user, result, ClientSource.API)

    whole = result
    if push.mode is LoadMode.APPEND:
        merged = _merge_sales(dataset, result.accepted, auth_token)
        if len(merged) != len(result.accepted):
            whole = replace(validate_rows_partial(merged, API_ORIGIN),
                            issues = result.issues)

    file_key = store_frame(whole.accepted, 'normalized', auth_token)
    stored = attach_to_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        payload = {
            'file_s3_key': file_key,
            'status': 'validated' if len(whole.accepted) else 'failed',
            **whole.summary.model_dump(),
            'issues': [
                issue.model_dump(mode = 'json')
                for issue in result.issues[:MAX_ISSUES_ON_RESPONSE]
            ]
        }
    )
    message = (f'Dataset {dataset_id} received {len(push.rows)} pushed line(s) '
               f'({push.mode.value}); {whole.summary.valid_rows} stored.')
    logger.info(message)
    return to_ingest_response(native_numbers(stored))


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Dataset', 'CREATE')
async def create_sales_dataset_controller(
    dynamodb_resource: ServiceResource,
    rows: SalesRowsSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> IngestResponse:
    '''
        The client's ERP creates its sales dataset by posting lines, with no
        file to start from.

        The same partial acceptance and the same client master as the file
        door, through the same function that stores a new dataset. Identical
        content is the same dataset, so a retry returns the one it created.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            rows (SalesRowsSchema): The lines.
            current_user (str): Authenticated caller, owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            IngestResponse: The new dataset, or the one that already held
                these lines.
    '''
    frame = prepare_sales_rows(rows_frame(rows.rows))
    fingerprint = content_fingerprint(serialize_dataframe(frame, 'raw.csv'))
    existing = find_dataset_by_fingerprint(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        fingerprint = fingerprint
    )
    if existing is not None:
        message = (f'Dataset {existing["dataset_id"]} already holds these lines for '
                   f'{current_user}; returning it.')
        logger.info(message)
        return to_ingest_response(existing, already_stored = True)

    persisted = store_new_dataset(
        dynamodb_resource, (current_user, auth_token),
        validate_rows_partial(frame, API_ORIGIN), (fingerprint, ClientSource.API)
    )
    message = (f'Dataset {persisted["dataset_id"]} created for {current_user} from '
               f'{len(rows.rows)} pushed line(s).')
    logger.info(message)
    return to_ingest_response(native_numbers(persisted))
