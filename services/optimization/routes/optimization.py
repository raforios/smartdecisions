'''
    Optimization: routes handler.

    Mirrors the legacy monolith endpoints (`api/routes/optimization.py`):
    `/data_model`, `/distances`, `/optimal_route`, `/distance_matrix`, `/route`.
    Same query-string contract (route_id, day, dist) so existing notebook /
    frontend clients only need to swap the base URL.
'''
from typing import Dict, List
from fastapi import APIRouter, Depends, Request, status
from boto3.resources.base import ServiceResource

from controllers.optimization import (
    data_ordered_controller,
    optimization_algorithm_controller,
    preparing_data_controller,
    simulation_algorithm_controller
)
from schemas.optimization import (
    DataMapResponse,
    OptimizationQueryParams,
    OptimizationResponse,
    RouteResponse
)
from services.db_connection import GET_DB_DEPENDENCY
from services.events_emitter import log_usage
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/optimization', tags = ['Optimization'])

MICROSERVICE_NAME = 'OPTIMIZATION'


@router.get(
    '/data_model',
    response_model = List[DataMapResponse],
    status_code = status.HTTP_200_OK,
    summary = 'Base map data for a (route_id, day)',
    description = 'Returns the geolocated client points tagged with start/middle/end colors.'
)
@log_usage(MICROSERVICE_NAME)
async def get_base_data_endpoint(
    request: Request,
    query_params: OptimizationQueryParams = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint mirroring legacy GET /api/v1/optimization/data_model.
    '''
    message = (
        f'Retrieving base data for route_id={query_params.route_id} '
        f'day={query_params.day}.'
    )
    logger.info(message)
    return await preparing_data_controller(
        dynamodb_resource = dynamodb_resource,
        route_id = query_params.route_id,
        day = query_params.day
    )


@router.get(
    '/distances',
    response_model = List[OptimizationResponse],
    status_code = status.HTTP_200_OK,
    summary = 'Ordered linear distances between points',
    description = 'Returns the ordered (origin, target, distance) triples for the route.'
)
@log_usage(MICROSERVICE_NAME)
async def get_distances_endpoint(
    request: Request,
    query_params: OptimizationQueryParams = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint mirroring legacy GET /api/v1/optimization/distances.
    '''
    message = (
        f'Computing distances for route_id={query_params.route_id} '
        f'day={query_params.day}.'
    )
    logger.info(message)
    return await data_ordered_controller(
        dynamodb_resource = dynamodb_resource,
        route_id = query_params.route_id,
        day = query_params.day
    )


@router.get(
    '/optimal_route',
    response_model = List[RouteResponse],
    status_code = status.HTTP_200_OK,
    summary = 'Optimized route projected on OSM road network',
    description = 'Returns the per-segment optimized route, including OSM node ids and shortest paths.'
)
@log_usage(MICROSERVICE_NAME)
async def get_optimal_route_endpoint(
    request: Request,
    query_params: OptimizationQueryParams = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint mirroring legacy GET /api/v1/optimization/optimal_route.
    '''
    message = (
        f'Optimizing route route_id={query_params.route_id} '
        f'day={query_params.day} dist={query_params.dist}.'
    )
    logger.info(message)
    return await optimization_algorithm_controller(
        dynamodb_resource = dynamodb_resource,
        route_id = query_params.route_id,
        day = query_params.day,
        dist = query_params.dist,
        current_user = current_user
    )


@router.get(
    '/distance_matrix',
    response_model = Dict,
    status_code = status.HTTP_200_OK,
    summary = 'Geodesic distance matrix between all points',
    description = 'Returns the symmetric distance matrix (in meters) between every pair of client points.'
)
@log_usage(MICROSERVICE_NAME)
async def get_distance_matrix_endpoint(
    request: Request,
    query_params: OptimizationQueryParams = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint mirroring legacy GET /api/v1/optimization/distance_matrix.
    '''
    message = (
        f'Building distance matrix for route_id={query_params.route_id} '
        f'day={query_params.day}.'
    )
    logger.info(message)
    return await simulation_algorithm_controller(
        dynamodb_resource = dynamodb_resource,
        route_id = query_params.route_id,
        day = query_params.day
    )


@router.get(
    '/route',
    response_model = List[RouteResponse],
    status_code = status.HTTP_200_OK,
    summary = 'Per-segment route data (alias of /optimal_route)',
    description = 'Mirrors the legacy /route endpoint kept for notebook compatibility.'
)
@log_usage(MICROSERVICE_NAME)
async def get_route_endpoint(
    request: Request,
    query_params: OptimizationQueryParams = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint mirroring legacy GET /api/v1/optimization/route.
    '''
    message = (
        f'Building route segments for route_id={query_params.route_id} '
        f'day={query_params.day} dist={query_params.dist}.'
    )
    logger.info(message)
    return await optimization_algorithm_controller(
        dynamodb_resource = dynamodb_resource,
        route_id = query_params.route_id,
        day = query_params.day,
        dist = query_params.dist,
        current_user = current_user
    )
