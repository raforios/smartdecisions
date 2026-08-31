'''
    Road-network projection via the public OSRM API.

    Replaces the heavy `osmnx` + `networkx` road-graph download (which pulled
    geopandas, shapely, fiona, pyproj, scipy and scikit-learn into the Lambda
    package) with lightweight HTTP calls to OSRM. The package stays small
    while each route segment is still projected onto real street geometry.
'''
from typing import Any, Dict, Tuple

import requests

from schemas.optimization import OptimizationError
from services.exceptions import ServiceUnavailableError
from services.environment import load_and_validate_env_vars
from services.logger_config import custom_logger as logger


# OSRM demo server by default; override with a self-hosted instance in prod.
_SETTINGS = load_and_validate_env_vars({}, optional_env_vars = {
    'OSRM_BASE_URL': str,
    'OSRM_REQUEST_TIMEOUT_SECONDS': int,
})
OSRM_BASE_URL = _SETTINGS['OSRM_BASE_URL'] or 'https://router.project-osrm.org'
_REQUEST_TIMEOUT_SECONDS = _SETTINGS['OSRM_REQUEST_TIMEOUT_SECONDS'] or 10


def _fetch_osrm_route(coordinates: str) -> Dict[str, Any]:
    '''
        Calls OSRM for a coordinate pair and returns the parsed JSON payload.

        Raises:
            ServiceUnavailableError: If OSRM is unreachable.
    '''
    url = f'{OSRM_BASE_URL}/route/v1/driving/{coordinates}'
    query = {'overview': 'full', 'geometries': 'geojson'}
    try:
        response = requests.get(url, params = query, timeout = _REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as error:
        error_msg = f'OSRM request failed for segment {coordinates}: {error}'
        logger.error(error_msg)
        raise ServiceUnavailableError(
            detail = OptimizationError.ROUTING_SERVICE_UNAVAILABLE.value
        ) from error


def road_segment(
    origin: Tuple[float, float],
    destination: Tuple[float, float]
) -> Dict[str, Any]:
    '''
        Projects a single origin → destination segment onto the road network
        using OSRM and returns its real driving distance, duration and the
        polyline geometry along the streets.

        Args:
            origin (Tuple[float, float]): (latitude, longitude) of the start.
            destination (Tuple[float, float]): (latitude, longitude) of the end.

        Returns:
            Dict[str, Any]: Keys `distance` (meters), `duration` (seconds) and
                `geometry` (list of [longitude, latitude] pairs).

        Raises:
            ServiceUnavailableError: If OSRM is unreachable or returns no route.
    '''
    origin_lat, origin_lon = origin
    destination_lat, destination_lon = destination
    coordinates = f'{origin_lon},{origin_lat};{destination_lon},{destination_lat}'

    payload = _fetch_osrm_route(coordinates)

    routes = payload.get('routes') or []
    if not routes:
        error_msg = f'OSRM returned no route for segment {coordinates}.'
        logger.error(error_msg)
        raise ServiceUnavailableError(
            detail = OptimizationError.ROUTING_SERVICE_NO_ROUTE.value
        )

    best_route = routes[0]
    geometry = best_route.get('geometry', {}).get('coordinates', [])
    return {
        'distance': float(best_route.get('distance', 0.0)),
        'duration': float(best_route.get('duration', 0.0)),
        'geometry': geometry
    }


def road_trip(stops: list[tuple[float, float]]) -> Dict[str, Any]:
    '''
        Projects a whole ordered route onto the street network in ONE call.

        The previous design asked OSRM for each leg separately, so a 30-stop
        route meant 30 chained requests against a rate-limited public demo
        server — slow, and the reason the map sometimes never finished loading.
        OSRM accepts the full coordinate list and returns the complete geometry,
        so the cost is a single request per day regardless of the stop count.

        Args:
            stops (list[tuple[float, float]]): Ordered (latitude, longitude)
                pairs of the visit sequence.

        Returns:
            Dict[str, Any]: Keys `distance` (metres), `duration` (seconds) and
                `geometry` (list of [longitude, latitude] pairs along the
                streets). An empty geometry when there is nothing to draw.

        Raises:
            ServiceUnavailableError: If OSRM is unreachable.
    '''
    if len(stops) < 2:
        return {'distance': 0.0, 'duration': 0.0, 'geometry': []}

    coordinates = ';'.join(f'{lon},{lat}' for lat, lon in stops)
    payload = _fetch_osrm_route(coordinates)

    routes = payload.get('routes') or []
    if not routes:
        # A missing projection must not lose the plan: the stops and their order
        # are still correct, the map just falls back to straight lines.
        error_msg = f'OSRM returned no route for a trip of {len(stops)} stops.'
        logger.warning(error_msg)
        return {'distance': 0.0, 'duration': 0.0, 'geometry': []}

    best = routes[0]
    return {
        'distance': float(best.get('distance', 0.0)),
        'duration': float(best.get('duration', 0.0)),
        'geometry': best.get('geometry', {}).get('coordinates', [])
    }
