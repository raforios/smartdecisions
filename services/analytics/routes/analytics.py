'''
    Analytics: routes handler.
'''
from fastapi import APIRouter, Depends, Path, Request, status
from boto3.resources.base import ServiceResource

from controllers.analytics import (
    get_pdv_opportunities_controller,
    get_results_controller,
    run_analytics_controller
)
from schemas.analytics import (
    AnalyticsPdvResponse,
    AnalyticsResultsResponse,
    AnalyticsRunResponse
)
from services.db_connection import GET_DB_DEPENDENCY
from services.events_emitter import log_usage
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/analytics', tags = ['Analytics'])

MICROSERVICE_NAME = 'ANALYTICS'


@router.post(
    '/run/{dataset_id}',
    response_model = AnalyticsRunResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Run the affinity × drop size engine on a previously ingested dataset',
    description = (
        'Reads the dataset from the ingest service (S3 via FILES bucket), '
        'computes association rules with mlxtend (Apriori), weights each '
        'rule by the expected drop size of the consequent product and '
        'returns the top N opportunities per point of sale, ranked by '
        'expected monetary impact.'
    )
)
@log_usage(MICROSERVICE_NAME)
async def run_analytics_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to run the analytics pipeline on a dataset_id.
    '''
    message = f'Running analytics for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return run_analytics_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        current_user = current_user
    )


@router.get(
    '/results/{dataset_id}',
    response_model = AnalyticsResultsResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Get the latest analytics run for a dataset',
    description = 'Returns the most recent persisted run (summary + opportunities).'
)
@log_usage(MICROSERVICE_NAME)
async def get_results_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve the latest analytics results for a dataset.
    '''
    message = f'Retrieving analytics results for dataset {dataset_id}.'
    logger.info(message)
    return get_results_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id
    )


@router.get(
    '/results/{dataset_id}/pdv/{pdv_id}',
    response_model = AnalyticsPdvResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Get the top opportunities for a single point of sale',
    description = 'Filters the latest run to the recommendations targeting one PdV.'
)
@log_usage(MICROSERVICE_NAME)
async def get_pdv_opportunities_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    pdv_id: str = Path(..., min_length = 1, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve opportunities filtered by point of sale.
    '''
    message = f'Retrieving opportunities for dataset {dataset_id} / pdv {pdv_id}.'
    logger.info(message)
    return get_pdv_opportunities_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        pdv_id = pdv_id
    )
