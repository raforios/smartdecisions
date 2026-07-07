'''
    Road-network projection via the public OSRM API.

    Replaces the heavy `osmnx` + `networkx` road-graph download (which pulled
    geopandas, shapely, fiona, pyproj, scipy and scikit-learn into the Lambda
    package) with lightweight HTTP calls to OSRM. The package stays small
    while each route segment is still projected onto real street geometry.
'''
import os
from typing import Any, Dict, Tuple

import requests

from services.exceptions import ServiceUnavailableError
from services.logger_config import custom_logger as logger


# OSRM demo server by default; override with a self-hosted instance in prod.
OSRM_BASE_URL = os.getenv('OSRM_BASE_URL', 'https://router.project-osrm.org')
_REQUEST_TIMEOUT_SECONDS = 10


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
            detail = 'El servicio de ruteo vial (OSRM) no está disponible.'
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
            detail = 'OSRM no devolvió una ruta para el segmento solicitado.'
        )

    best_route = routes[0]
    geometry = best_route.get('geometry', {}).get('coordinates', [])
    return {
        'distance': float(best_route.get('distance', 0.0)),
        'duration': float(best_route.get('duration', 0.0)),
        'geometry': geometry
    }
