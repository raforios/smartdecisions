'''
    Optimization: routes handler.

    Mirrors the legacy monolith endpoints (`api/routes/optimization.py`):
    `/data_model`, `/distances`, `/optimal_route`, `/distance_matrix`, `/route`.
    Same query-string contract (route_id, day, dist) so existing notebook /
    frontend clients only need to swap the base URL.
'''
from typing import Dict, List
from fastapi import APIRouter, Depends, File, Path, Request, UploadFile, status
from boto3.resources.base import ServiceResource

from controllers.optimization import (
    route_plan_controller,
    bulk_upload_routes_controller,
    data_ordered_controller,
    optimization_algorithm_controller,
    preparing_data_controller,
    simulation_algorithm_controller
)
from schemas.optimization import (
    OptimizationError,
    PlanQueryParams,
    RoutePlanResponse,
    BulkUploadResponse,
    DataMapResponse,
    OptimizationQueryParams,
    OptimizationResponse,
    RouteResponse
)
from services.exceptions import InvalidInputError
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_user

router = APIRouter(prefix = '/v1/optimization', tags = ['Optimization'])


@router.get(
    '/data_model',
    response_model = List[DataMapResponse],
    status_code = status.HTTP_200_OK,
    summary = 'Base map data for a (route_id, day)',
    description = 'Returns the geolocated client points tagged with start/middle/end colors.'
)
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
        f'User: {current_user}. Retrieving base data for '
        f'route_id={query_params.route_id} day={query_params.day}.'
    )
    logger.info(message)
    return await preparing_data_controller(
        dynamodb_resource = dynamodb_resource,
        route_id = query_params.route_id,
        day = query_params.day,
        request = request,
        current_user = current_user
    )


@router.get(
    '/distances',
    response_model = List[OptimizationResponse],
    status_code = status.HTTP_200_OK,
    summary = 'Ordered linear distances between points',
    description = 'Returns the ordered (origin, target, distance) triples for the route.'
)
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
        f'User: {current_user}. Computing distances for '
        f'route_id={query_params.route_id} day={query_params.day}.'
    )
    logger.info(message)
    return await data_ordered_controller(
        dynamodb_resource = dynamodb_resource,
        route_id = query_params.route_id,
        day = query_params.day,
        request = request,
        current_user = current_user
    )


@router.get(
    '/optimal_route',
    response_model = List[RouteResponse],
    status_code = status.HTTP_200_OK,
    summary = 'Optimized route projected on the road network (OSRM)',
    description = (
        'Returns the per-segment optimized route with real road distance, '
        'duration and street geometry.'
    )
)
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
        f'User: {current_user}. Optimizing route route_id={query_params.route_id} '
        f'day={query_params.day} dist={query_params.dist}.'
    )
    logger.info(message)
    return await optimization_algorithm_controller(
        dynamodb_resource = dynamodb_resource,
        route_id = query_params.route_id,
        day = query_params.day,
        request = request,
        current_user = current_user
    )


@router.get(
    '/distance_matrix',
    response_model = Dict,
    status_code = status.HTTP_200_OK,
    summary = 'Geodesic distance matrix between all points',
    description = (
        'Returns the symmetric distance matrix (in meters) between every '
        'pair of client points.'
    )
)
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
        f'User: {current_user}. Building distance matrix for '
        f'route_id={query_params.route_id} day={query_params.day}.'
    )
    logger.info(message)
    return await simulation_algorithm_controller(
        dynamodb_resource = dynamodb_resource,
        route_id = query_params.route_id,
        day = query_params.day,
        request = request,
        current_user = current_user
    )


@router.get(
    '/route',
    response_model = List[RouteResponse],
    status_code = status.HTTP_200_OK,
    summary = 'Per-segment route data (alias of /optimal_route)',
    description = 'Mirrors the legacy /route endpoint kept for notebook compatibility.'
)
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
        f'User: {current_user}. Building route segments for '
        f'route_id={query_params.route_id} day={query_params.day} '
        f'dist={query_params.dist}.'
    )
    logger.info(message)
    return await optimization_algorithm_controller(
        dynamodb_resource = dynamodb_resource,
        route_id = query_params.route_id,
        day = query_params.day,
        request = request,
        current_user = current_user
    )


@router.post(
    '/routes/bulk-upload',
    response_model = BulkUploadResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'Upload route points from a CSV',
    description = (
        'Accepts a CSV with columns route_id, day, client_id, latitude, '
        'longitude (+ optional client name). All rows must share the same '
        '(route_id, day); re-upload of the same pair replaces the previous '
        'content.'
    )
)
async def bulk_upload_routes_endpoint(
    request: Request,
    file: UploadFile = File(...),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint to bulk-upload route points via CSV.
    '''
    filename = file.filename or ''
    if not filename.lower().endswith(('.csv', '.txt')):
        raise InvalidInputError(detail = 'Solo se aceptan archivos .csv o .txt.')
    raw_bytes = await file.read()
    if not raw_bytes:
        raise InvalidInputError(detail = OptimizationError.EMPTY_UPLOAD.value)
    try:
        csv_text = raw_bytes.decode('utf-8-sig')
    except UnicodeDecodeError as e:
        raise InvalidInputError(
            detail = 'El archivo no pudo decodificarse como UTF-8.'
        ) from e
    message = f'Bulk-uploading routes CSV "{filename}" from {current_user}.'
    logger.info(message)
    return await bulk_upload_routes_controller(
        dynamodb_resource = dynamodb_resource,
        csv_text = csv_text,
        current_user = current_user,
        request = request
    )


@router.get(
    '/plan/{dataset_id}',
    response_model = RoutePlanResponse,
    status_code = status.HTTP_200_OK,
    summary = 'Visit plan derived from an ingested sales dataset',
    description = (
        'Builds a week of visit routes from the sales file the user already '
        'uploaded: the clients are the ones who bought in the period, the visit '
        'days come from clustering them geographically, and each day is ordered '
        'with a 2-opt tour projected onto real streets via OSRM. Every stop '
        'carries its purchase value and segment, so the rep sees who they are '
        'visiting and not just a pin on a map.'
    )
)
async def route_plan_endpoint(
    request: Request,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    query_params: PlanQueryParams = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(get_current_user)
):
    '''
        Endpoint returning the visit plan for a dataset_id.
    '''
    message = (
        f'User: {current_user}. Planning routes for dataset {dataset_id} '
        f'({query_params.days} day(s), seller={query_params.seller}).'
    )
    logger.info(message)
    return await route_plan_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        params = query_params.model_dump(),
        current_user = current_user,
        request = request
    )
