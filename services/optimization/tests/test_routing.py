'''
    Unit tests for the OSRM road-network projection client (services.routing).

    The OSRM HTTP layer is mocked so the tests stay offline and deterministic.
'''
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.exceptions import ServiceUnavailableError
from services.routing import road_segment


def _osrm_payload() -> dict:
    '''
        Builds a minimal but valid OSRM `/route` response with one route.
    '''
    return {
        'routes': [
            {
                'distance': 1234.5,
                'duration': 321.0,
                'geometry': {
                    'coordinates': [[-68.15, -16.50], [-68.145, -16.505]]
                }
            }
        ]
    }


def test_road_segment_returns_distance_duration_and_geometry() -> None:
    '''
        A successful OSRM response is mapped to distance, duration and the
        street polyline as [longitude, latitude] pairs.
    '''
    response = MagicMock()
    response.json.return_value = _osrm_payload()
    response.raise_for_status.return_value = None

    with patch('services.routing.requests.get', return_value = response) as mock_get:
        result = road_segment((-16.50, -68.15), (-16.505, -68.145))

    assert result['distance'] == 1234.5
    assert result['duration'] == 321.0
    assert result['geometry'] == [[-68.15, -16.50], [-68.145, -16.505]]
    # OSRM expects longitude,latitude order in the path: lon first.
    called_url = mock_get.call_args.args[0]
    assert '-68.15,-16.5;-68.145,-16.505' in called_url


def test_road_segment_raises_service_unavailable_on_network_error() -> None:
    '''
        A network/HTTP failure surfaces as ServiceUnavailableError (HTTP 503).
    '''
    with patch('services.routing.requests.get',
               side_effect = requests.RequestException('boom')):
        with pytest.raises(ServiceUnavailableError):
            road_segment((-16.50, -68.15), (-16.505, -68.145))


def test_road_segment_raises_service_unavailable_when_no_route() -> None:
    '''
        An empty `routes` list (OSRM could not resolve the segment) raises
        ServiceUnavailableError instead of returning a malformed segment.
    '''
    response = MagicMock()
    response.json.return_value = {'routes': []}
    response.raise_for_status.return_value = None

    with patch('services.routing.requests.get', return_value = response):
        with pytest.raises(ServiceUnavailableError):
            road_segment((-16.50, -68.15), (-16.505, -68.145))
