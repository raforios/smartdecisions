'''
    Analytics: routes handler.
'''
from fastapi import APIRouter, Depends, Path, Query, Request, status
from boto3.resources.base import ServiceResource

from controllers.analytics import (
    commercial_summary_controller,
    forecast_controller,
    get_pdv_opportunities_controller,
    get_results_controller,
    run_analytics_controller,
    segmentation_controller
)
from schemas.analytics import (
    AnalyticsPdvResponse,
    AnalyticsResultsResponse,
    AnalyticsRunResponse,
    CommercialSummaryResponse,
    ForecastResponse,
    SegmentationResponse
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/analytics', tags = ['Analytics'])


@router.get(
    '/summary/{dataset_id}',
    response_model = CommercialSummaryResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Commercial summary (KPIs, rankings, distributions, trend)',
    description = (
        'Reads the normalized dataset and returns the general sales dashboard: '
        'headline KPIs, best/worst client, top/bottom products, breakdowns by '
        'category/channel/region/seller and the monthly trend. Read-only.'
    )
)
async def commercial_summary_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint returning the commercial summary for a dataset_id.
    '''
    message = f'Commercial summary for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await commercial_summary_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        current_user = current_user,
        request = request
    )


@router.get(
    '/forecast/{dataset_id}',
    response_model = ForecastResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Demand forecast (linear trend / moving average, total or by category)',
    description = (
        'Projects future monthly sales from the normalized dataset. Choose the '
        'method (linear / moving_average), the horizon in months and whether to '
        'split by category. Read-only.'
    )
)
async def forecast_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    method: str = Query('linear', pattern = '^(linear|moving_average)$'),
    months_ahead: int = Query(3, ge = 1, le = 12),
    group_by: str = Query(None, pattern = '^(categoria)$'),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint returning the demand forecast for a dataset_id.
    '''
    message = f'Forecast for dataset {dataset_id} ({method}, {months_ahead}m) by {current_user}.'
    logger.info(message)
    return await forecast_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        params = {'method': method, 'months_ahead': months_ahead, 'group_by': group_by},
        current_user = current_user,
        request = request
    )


@router.get(
    '/segmentation/{dataset_id}',
    response_model = SegmentationResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Customer value segmentation (Alto / Medio / Bajo)',
    description = (
        'Reads the normalized dataset and classifies clients into value tiers '
        'by their total purchases, so the team can prioritize. Read-only.'
    )
)
async def segmentation_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint returning the customer segmentation for a dataset_id.
    '''
    message = f'Segmentation for dataset {dataset_id} requested by {current_user}.'
    logger.info(message)
    return await segmentation_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        current_user = current_user,
        request = request
    )


@router.post(
    '/run/{dataset_id}',
    response_model = AnalyticsRunResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Run the affinity × drop size engine on a previously ingested dataset',
    description = (
        'Reads the dataset from the ingest service (S3 via FILES bucket), '
        'computes association rules with a lightweight Apriori, weights each '
        'rule by the expected drop size of the consequent product and '
        'returns the top N opportunities per point of sale, ranked by '
        'expected monetary impact.'
    )
)
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
    return await run_analytics_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        current_user = current_user,
        request = request
    )


@router.get(
    '/results/{dataset_id}',
    response_model = AnalyticsResultsResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Get the latest analytics run for a dataset',
    description = 'Returns the most recent persisted run (summary + opportunities).'
)
async def get_results_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to retrieve the latest analytics results for a dataset.
    '''
    message = f'User: {current_user}. Retrieving analytics results for dataset {dataset_id}.'
    logger.info(message)
    return await get_results_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        request = request,
        current_user = current_user
    )


@router.get(
    '/results/{dataset_id}/pdv/{pdv_id}',
    response_model = AnalyticsPdvResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Get the top opportunities for a single point of sale',
    description = 'Filters the latest run to the recommendations targeting one PdV.'
)
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
    message = f'User: {current_user}. Retrieving opportunities for dataset {dataset_id} / pdv {
            pdv_id}.'
    logger.info(message)
    return await get_pdv_opportunities_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        pdv_id = pdv_id,
        request = request,
        current_user = current_user
    )
