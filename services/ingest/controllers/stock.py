'''
    Stock: the daily snapshot of the warehouse, married to the product
    catalogue of the sales dataset. Read, never written: this service holds
    no reservations of its own.
'''
from boto3.resources.base import ServiceResource
from fastapi import Request

from controllers.common import (
    CompanionSpec,
    load_sales_frame,
    store_companion,
    stored_companion_frame
)
from schemas.ingest import IngestError, StockDayResponse, StockResponse
from services.exceptions import ResourceNotFoundError
from services.ingest_utils import get_owned_dataset
from services.stock import parse_and_validate, stock_of_day
from services.utils import audit_event, handle_service_errors

# The controller signature is fixed by the route —resource, dataset, file,
# name, caller, request— and the three companion controllers are the same
# seven-line adapter over their own pipeline on purpose: what varies is the
# spec, and folding them into one would hide which process each route runs.
# pylint: disable=too-many-arguments, too-many-positional-arguments, duplicate-code

# The snapshot is per product and day, so pushing today replaces today and
# leaves every other day where it was.
SPEC = CompanionSpec(
    name = 'stock',
    response_model = StockResponse,
    merge_keys = ('snapshot_date', 'product_id')
)


@handle_service_errors('INGEST')
@audit_event('INGEST', 'Stock', 'UPLOAD')
async def ingest_stock_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    file_bytes: bytes,
    filename: str,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> StockResponse:
    '''
        Loads a stock snapshot against an existing sales dataset.

            1. Read the dataset the caller owns, and its stored sales rows.
            2. Validate the snapshot and marry it to the product catalogue.
            3. Store the accepted rows and attach them to the dataset.

        Its own endpoint because of cadence: the sales file is loaded once and
        the stock changes every day. A new load REPLACES the previous snapshot,
        so what is reported is always the latest photo.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the stock snapshot belongs to.
            file_bytes (bytes): Raw content of the uploaded file.
            filename (str): Original filename.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            StockResponse: Summary of the load and its issues.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    result = parse_and_validate(file_bytes, filename, load_sales_frame(dataset, auth_token))
    return await store_companion(dynamodb_resource, dataset, result, SPEC,
                                 (filename, auth_token))


@handle_service_errors('INGEST')
async def get_stock_day_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    day: str,
    current_user: str,
    auth_token: str,
    request: Request # pylint: disable=unused-argument
) -> StockDayResponse:
    '''
        The stored snapshot of one day, read back through FILES.

        Args:
            dynamodb_resource (ServiceResource): The DynamoDB resource.
            dataset_id (str): Sales dataset the snapshot belongs to.
            day (str): The day asked for, YYYY-MM-DD.
            current_user (str): Authenticated caller and owner of the dataset.
            auth_token (str): The caller's Authorization header, forwarded to FILES.

        Returns:
            StockDayResponse: One item per product of that day.

        Raises:
            ResourceNotFoundError: NO_STOCK_FOR_DAY when nothing was loaded for it.
    '''
    dataset = get_owned_dataset(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    stored = stored_companion_frame(dataset, SPEC, auth_token)
    items = stock_of_day(stored, day) if stored is not None else []
    if not items:
        raise ResourceNotFoundError(detail = IngestError.NO_STOCK_FOR_DAY.value)
    return StockDayResponse(dataset_id = dataset_id, date = day, items = items)
