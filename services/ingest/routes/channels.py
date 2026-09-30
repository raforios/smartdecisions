'''
    Companion contracts — HTTP layer of the API channel.

    The other door of the same three contracts. `POST /{dataset_id}/<name>`
    takes the file; these take the rows, so the client's ERP pushes yesterday's
    payments without anybody exporting a workbook.
'''
from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Depends, Header, Path as PathParam, Request, status

from controllers.channels import (
    ingest_collections_from_s3_controller,
    ingest_objectives_from_s3_controller,
    push_sales_controller,
    ingest_stock_from_s3_controller,
    ingest_visits_from_s3_controller,
    push_collections_controller,
    push_objectives_controller,
    push_stock_controller,
    push_visits_controller
)
from schemas.channels import (
    CollectionsPushSchema,
    ObjectivesPushSchema,
    SalesPushSchema,
    IngestFromS3CompanionRequest,
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
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner

router = APIRouter(prefix = '/v1/ingest', tags = ['Daily data (API)'])

# A FastAPI endpoint declares its dependencies as parameters —resource,
# token, caller, body— so the five-argument budget does not describe it.
# pylint: disable=too-many-arguments, too-many-positional-arguments

_DATASET_ID = PathParam(..., min_length = 8, max_length = 64)

_APPEND_NOTE = (
    'Default mode is APPEND: the rows land on top of what is stored and the '
    'contract\'s own key decides what is a repeat, so a retry does not count '
    'twice. Send REPLACE to make this load the whole one, as the file does. '
    'The summary describes everything stored; the issues, only this push.'
)


@router.post(
    '/{dataset_id}/objectives/rows',
    response_model = ObjectivesResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Push the monthly objectives, from an ERP',
    description = ('An objective is a client, a month and an amount. '
                   'Re-sending a month corrects it. ') + _APPEND_NOTE
)
async def push_objectives_endpoint(
    request: Request,
    push: ObjectivesPushSchema,
    dataset_id: str = _DATASET_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    authorization: str = Header(None),
    current_user: str = Depends(get_current_owner)
) -> ObjectivesResponse:
    '''
        Endpoint to push monthly objectives as JSON.
    '''
    message = (f'User: {current_user}. Pushing {len(push.rows)} objective(s) '
               f'({push.mode.value}) to dataset {dataset_id}.')
    logger.info(message)
    return await push_objectives_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        push = push,
        current_user = current_user,
        auth_token = authorization,
        request = request
    )


@router.post(
    '/{dataset_id}/collections/rows',
    response_model = CollectionsResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Push the payments collected, from an ERP',
    description = 'A payment is its invoice, its date and its amount. ' + _APPEND_NOTE
)
async def push_collections_endpoint(
    request: Request,
    push: CollectionsPushSchema,
    dataset_id: str = _DATASET_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    authorization: str = Header(None),
    current_user: str = Depends(get_current_owner)
) -> CollectionsResponse:
    '''
        Endpoint to push payments as JSON.
    '''
    message = (f'User: {current_user}. Pushing {len(push.rows)} payment(s) '
               f'({push.mode.value}) to dataset {dataset_id}.')
    logger.info(message)
    return await push_collections_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        push = push,
        current_user = current_user,
        auth_token = authorization,
        request = request
    )


@router.post(
    '/{dataset_id}/stock/rows',
    response_model = StockResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Push the stock of the day, from an ERP',
    description = ('The snapshot is per product and day, so pushing today '
                   'replaces today and leaves every other day alone. ' + _APPEND_NOTE)
)
async def push_stock_endpoint(
    request: Request,
    push: StockPushSchema,
    dataset_id: str = _DATASET_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    authorization: str = Header(None),
    current_user: str = Depends(get_current_owner)
) -> StockResponse:
    '''
        Endpoint to push the day's stock as JSON.
    '''
    message = (f'User: {current_user}. Pushing {len(push.rows)} stock row(s) '
               f'({push.mode.value}) to dataset {dataset_id}.')
    logger.info(message)
    return await push_stock_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        push = push,
        current_user = current_user,
        auth_token = authorization,
        request = request
    )


@router.post(
    '/{dataset_id}/visits/rows',
    response_model = VisitsResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Push the visits of the day, from an ERP',
    description = ('Feeds the client master too: this is the load that reaches '
                   'a prospect nobody billed. ' + _APPEND_NOTE)
)
async def push_visits_endpoint(
    request: Request,
    push: VisitsPushSchema,
    dataset_id: str = _DATASET_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    authorization: str = Header(None),
    current_user: str = Depends(get_current_owner)
) -> VisitsResponse:
    '''
        Endpoint to push the day's visits as JSON.
    '''
    message = (f'User: {current_user}. Pushing {len(push.rows)} visit(s) '
               f'({push.mode.value}) to dataset {dataset_id}.')
    logger.info(message)
    return await push_visits_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        push = push,
        current_user = current_user,
        auth_token = authorization,
        request = request
    )


@router.post(
    '/{dataset_id}/sales/rows',
    response_model = IngestResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Push sales lines from an ERP',
    description = (
        'The API door of the main contract, for a client whose ERP is the '
        'system of record. A sales line is its invoice and its product, so '
        'pushing the same day twice —a retry, or a correction to one line— '
        'does not count the invoice twice. Default mode is APPEND; send '
        'REPLACE to make this push the whole dataset. Invalid lines are set '
        'aside with their code and the rest load, exactly as in the file.'
    )
)
async def push_sales_endpoint(
    request: Request,
    push: SalesPushSchema,
    dataset_id: str = PathParam(..., min_length = 8, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    authorization: str = Header(None),
    current_user: str = Depends(get_current_owner)
) -> IngestResponse:
    '''
        Endpoint to push sales lines as JSON.
    '''
    message = (f'User: {current_user}. Pushing {len(push.rows)} sales line(s) '
               f'({push.mode.value}) to dataset {dataset_id}.')
    logger.info(message)
    return await push_sales_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        push = push,
        current_user = current_user,
        auth_token = authorization,
        request = request
    )


# ---------------------------------------------------------------------------
# The file channel for a real export: FILES puts it in S3, this reads the key.
# ---------------------------------------------------------------------------
_S3_NOTE = (
    'For a file too big for the 10 MB of API Gateway. FILES uploads it to S3 '
    'with a pre-signed URL and this reads it by its key, so the binary never '
    'crosses the gateway. Default mode is REPLACE, as the multipart upload '
    'does; send APPEND to add it to what is already stored.'
)


@router.post(
    '/{dataset_id}/objectives/from-s3',
    response_model = ObjectivesResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Load an objectives file already staged in S3',
    description = _S3_NOTE
)
async def ingest_objectives_from_s3_endpoint(
    request: Request,
    payload: IngestFromS3CompanionRequest,
    dataset_id: str = _DATASET_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    authorization: str = Header(None),
    current_user: str = Depends(get_current_owner)
) -> ObjectivesResponse:
    '''
        Endpoint to load an objectives file from S3.
    '''
    message = (f'User: {current_user}. Loading objectives "{payload.file_key}" '
               f'({payload.mode.value}) into dataset {dataset_id}.')
    logger.info(message)
    return await ingest_objectives_from_s3_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        payload = payload,
        current_user = current_user,
        auth_token = authorization,
        request = request
    )


@router.post(
    '/{dataset_id}/collections/from-s3',
    response_model = CollectionsResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Load a payments file already staged in S3',
    description = _S3_NOTE
)
async def ingest_collections_from_s3_endpoint(
    request: Request,
    payload: IngestFromS3CompanionRequest,
    dataset_id: str = _DATASET_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    authorization: str = Header(None),
    current_user: str = Depends(get_current_owner)
) -> CollectionsResponse:
    '''
        Endpoint to load a payments file from S3.
    '''
    message = (f'User: {current_user}. Loading payments "{payload.file_key}" '
               f'({payload.mode.value}) into dataset {dataset_id}.')
    logger.info(message)
    return await ingest_collections_from_s3_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        payload = payload,
        current_user = current_user,
        auth_token = authorization,
        request = request
    )


@router.post(
    '/{dataset_id}/stock/from-s3',
    response_model = StockResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Load a stock file already staged in S3',
    description = _S3_NOTE
)
async def ingest_stock_from_s3_endpoint(
    request: Request,
    payload: IngestFromS3CompanionRequest,
    dataset_id: str = _DATASET_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    authorization: str = Header(None),
    current_user: str = Depends(get_current_owner)
) -> StockResponse:
    '''
        Endpoint to load a stock file from S3.
    '''
    message = (f'User: {current_user}. Loading stock "{payload.file_key}" '
               f'({payload.mode.value}) into dataset {dataset_id}.')
    logger.info(message)
    return await ingest_stock_from_s3_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        payload = payload,
        current_user = current_user,
        auth_token = authorization,
        request = request
    )


@router.post(
    '/{dataset_id}/visits/from-s3',
    response_model = VisitsResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Load a visits file already staged in S3',
    description = _S3_NOTE
)
async def ingest_visits_from_s3_endpoint(
    request: Request,
    payload: IngestFromS3CompanionRequest,
    dataset_id: str = _DATASET_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    authorization: str = Header(None),
    current_user: str = Depends(get_current_owner)
) -> VisitsResponse:
    '''
        Endpoint to load a visits file from S3.
    '''
    message = (f'User: {current_user}. Loading visits "{payload.file_key}" '
               f'({payload.mode.value}) into dataset {dataset_id}.')
    logger.info(message)
    return await ingest_visits_from_s3_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        payload = payload,
        current_user = current_user,
        auth_token = authorization,
        request = request
    )
