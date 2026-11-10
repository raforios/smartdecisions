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
from typing import Any

import pandas as pd
from boto3.resources.base import ServiceResource
from fastapi import Request
from pydantic import BaseModel

from core.utils import audit_event, delete_stored_file, handle_service_errors
from controllers.collections import SPEC as COLLECTIONS
from controllers.objectives import SPEC as OBJECTIVES
from controllers.common import (
    LoadContext,
    merge_if_appending,
    API_ORIGIN,
    CompanionSpec,
    load_sales_frame,
    rows_frame,
    store_companion
)
from controllers.purchases_load import SPEC as PURCHASES
from controllers.sales_load import create_sales_dataset, push_sales
from controllers.stock import SPEC as STOCK
from controllers.visits import SPEC as VISITS
from schemas.channels import (
    CollectionsPushSchema,
    ObjectivesPushSchema,
    SalesPushSchema,
    SalesRowsSchema,
    IngestFromS3CompanionRequest,
    LoadMode,
    PurchasesPushSchema,
    StockPushSchema,
    VisitsPushSchema
)
from schemas.commercial import (
    CollectionsResponse,
    ObjectivesResponse,
    IngestResponse,
    PurchasesResponse,
    StockResponse,
    VisitsResponse
)
from services.collections import parse_frame as parse_collections_frame
from services.collections import validate_rows as validate_collections
from services.objectives_load import parse_frame as parse_objectives_frame
from services.objectives_load import prepare_rows as prepare_objectives
from services.objectives_load import validate_rows as validate_objectives
from services.commercial import fill_product_ids
from services.commercial_utils import (
    get_owned_dataset,
    list_datasets_for_owner,
    read_stored_frame
)
from services.purchases_load import parse_frame as parse_purchases_frame
from services.purchases_load import validate_rows as validate_purchases
from services.stock_load import parse_frame as parse_stock_frame
from services.stock_load import prepare_rows as prepare_stock
from services.stock_load import validate_rows as validate_stock
from services.visits import parse_frame as parse_visits_frame
from services.visits import prepare_rows as prepare_visits
from services.visits import validate_rows as validate_visits

# Each companion's validator, by name, so the merge can re-summarize whatever
# it just merged without the caller having to hand it over twice.
_VALIDATORS: dict = {
    COLLECTIONS.name: validate_collections,
    OBJECTIVES.name: validate_objectives,
    PURCHASES.name: validate_purchases,
    STOCK.name: validate_stock,
    VISITS.name: validate_visits,
}


# The controller signature is fixed by the route, and the three push
# controllers are the same adapter over their own pipeline — as the three file
# controllers already are. What varies is the spec and the pipeline.
# pylint: disable=too-many-arguments, too-many-positional-arguments, duplicate-code


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
    result = merge_if_appending(
        LoadContext(dataset, spec, push.mode, sales, validate_rows,
                    API_ORIGIN, auth_token),
        result
    )
    return await store_companion(dynamodb_resource, dataset, result, spec,
                                 (API_ORIGIN, auth_token))


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Objectives', 'UPLOAD')
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


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Collections', 'UPLOAD')
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


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Stock', 'UPLOAD')
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


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Visits', 'UPLOAD')
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
    result = merge_if_appending(
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


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Collections', 'UPLOAD')
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


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Stock', 'UPLOAD')
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


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Stock', 'UPLOAD')
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


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Visits', 'UPLOAD')
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


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Dataset', 'UPDATE')
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
    return await push_sales(dynamodb_resource, dataset_id, push, current_user, auth_token)


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Dataset', 'CREATE')
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
    return await create_sales_dataset(dynamodb_resource, rows, current_user, auth_token)


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Purchases', 'UPLOAD')
async def push_purchases_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    push: PurchasesPushSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> PurchasesResponse:
    '''
        The ERP posts the purchases made.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the purchases belong to.
            push (PurchasesPushSchema): Mode and rows.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            PurchasesResponse: Summary of what is stored and this push's issues.
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
        spec = PURCHASES,
        pipeline = (fill_product_ids, validate_purchases, auth_token)
    )


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Purchases', 'UPLOAD')
async def ingest_purchases_from_s3_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    payload: IngestFromS3CompanionRequest,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> PurchasesResponse:
    '''
        Loads a purchases file already staged in S3 by FILES.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the purchases belong to.
            payload (IngestFromS3CompanionRequest): Object key, name and mode.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            PurchasesResponse: Summary of the load and its issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    return await _from_s3(dynamodb_resource, dataset, payload, PURCHASES,
                          (parse_purchases_frame, auth_token))


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Dataset', 'UPLOAD')
async def live_sales_controller(
    dynamodb_resource: ServiceResource,
    rows: SalesRowsSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> IngestResponse:
    '''
        Sales that arrive as they happen —SmartBilling's till, later the
        chat— go to the company's most recent dataset, appended; a company
        with none gets one created (Rafael, 6-nov-2026). Both paths validate
        and feed the masters exactly as the push and create doors do.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            rows (SalesRowsSchema): The lines.
            current_user (str): Authenticated caller, owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            IngestResponse: The dataset the lines went into.
    '''
    latest = list_datasets_for_owner(dynamodb_resource, current_user, limit = 1)
    if not latest:
        return await create_sales_dataset(dynamodb_resource, rows, current_user, auth_token)
    return await push_sales(dynamodb_resource, str(latest[0]['dataset_id']),
                             SalesPushSchema(rows = rows.rows, mode = LoadMode.APPEND),
                             current_user, auth_token)


def _latest_owned(
    dynamodb_resource: ServiceResource,
    current_user: str
) -> dict[str, Any] | None:
    '''
        The company's most recent dataset, where what arrives live belongs.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            current_user (str): Authenticated caller, owner of the dataset.

        Returns:
            dict[str, Any] | None: The dataset; None while the company has no sales.
    '''
    latest = list_datasets_for_owner(dynamodb_resource, current_user, limit = 1)
    if not latest:
        return None
    return get_owned_dataset(dynamodb_resource = dynamodb_resource,
                             dataset_id = str(latest[0]['dataset_id']),
                             owner_email = current_user)


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Stock', 'UPLOAD')
async def live_stock_controller(
    dynamodb_resource: ServiceResource,
    push: StockPushSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> StockResponse:
    '''
        The shelf as SmartBilling holds it, sent at every movement (Rafael,
        8-nov-2026): today's photo of each product in the latest dataset, so
        Inventory reads the real stock and not only an uploaded one. A
        company with no sales yet has no dataset to attach it to; the next
        movement sends the whole shelf again.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            push (StockPushSchema): Mode and rows.
            current_user (str): Authenticated caller, owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            StockResponse: Summary of what is stored and this push's issues.
    '''
    dataset = _latest_owned(dynamodb_resource, current_user)
    if dataset is None:
        return StockResponse(dataset_id = '', status = 'failed')
    return await _push(dynamodb_resource = dynamodb_resource, dataset = dataset, push = push,
                       spec = STOCK, pipeline = (prepare_stock, validate_stock, auth_token))


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'Purchases', 'UPLOAD')
async def live_purchases_controller(
    dynamodb_resource: ServiceResource,
    push: PurchasesPushSchema,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> PurchasesResponse:
    '''
        A purchase as SmartBilling receives it (Rafael, 8-nov-2026), into the
        latest dataset, so Purchases reads what the shop really bought.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            push (PurchasesPushSchema): Mode and rows.
            current_user (str): Authenticated caller, owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.
            request (Request): Incoming request, used by the decorators.

        Returns:
            PurchasesResponse: Summary of what is stored and this push's issues.
    '''
    dataset = _latest_owned(dynamodb_resource, current_user)
    if dataset is None:
        return PurchasesResponse(dataset_id = '', status = 'failed')
    return await _push(dynamodb_resource = dynamodb_resource, dataset = dataset, push = push,
                       spec = PURCHASES,
                       pipeline = (fill_product_ids, validate_purchases, auth_token))
