'''
    Utility functions for Localization Microservice.
'''
import math
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from services.exceptions import (
    RegisterNotFoundError,
    RegisterAlreadyExistsError,
    InvalidInputError
)
from services.utils import (
    _handle_files_service
)
from models.localization import (
    PlannedRoute,
    PlannedPoint
)
from schemas.localization import (
    PlannedRouteBulkCreateSchema
)

# Geofencing Parameters
EARTH_RADIUS_KM = 6371

def _calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    '''
    Calculates the distance between two coordinates in meters using the Haversine formula.
    '''
    # Convert latitude and longitude from degrees to radians
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)

    # Haversine formula
    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    a = math.sin(delta_lat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * \
        math.sin(delta_lon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Distance in kilometers
    distance_km = EARTH_RADIUS_KM * c

    # Return distance in meters
    return distance_km * 1000

def _check_geofence_start_point(
    db: Session,
    planned_route_id: int,
    user_latitude: float,
    user_longitude: float,
    max_distance: float
):
    '''
        Checks if the user's current location is within the geofence of the planned route's
        starting point.
    '''
    # Find the starting point of the planned route (the one with secuencial=1)
    start_point = db.query(PlannedPoint).filter(
        PlannedPoint.planned_route_id == planned_route_id,
        PlannedPoint.secuencial == 1
    ).first()

    if not start_point:
        raise RegisterNotFoundError(
            detail = f'Starting point not found for planned route {planned_route_id}.'
        )

    distance = _calculate_distance(
        user_latitude, user_longitude, start_point.latitude, start_point.longitude
    )

    if distance > max_distance:
        raise InvalidInputError(
            detail = f'Distance: {distance:.2f} meters. Limit: {max_distance:.2f} meters.'
        )

def _process_localization_csv_data(
    rows: List[Dict[str, Any]],
    bulk_schema: PlannedRouteBulkCreateSchema
) -> Dict[str, Any]:
    '''
        Processes raw data from a CSV to group planned routes and their points.
    '''
    routes_data = {}
    for row in rows:
        try:
            row_data = bulk_schema(**row)
            route_key = (
                row_data.route_code,
                row_data.company_id
            )
            if route_key not in routes_data:
                routes_data[route_key] = {
                    'route_data': row_data.model_dump(
                        exclude = {
                            'point_name',
                            'secuencial',
                            'latitude',
                            'longitude',
                            'reference_data'
                        }),
                    'points_data': []
                }
            routes_data[route_key]['points_data'].append(
                row_data.model_dump(
                    exclude = {
                        'company_id',
                        'app_id',
                        'city_id',
                        'route_code',
                        'route_name'
                    })
            )
        except (ValueError, TypeError) as e:
            raise InvalidInputError(
                detail = f'Invalid data format in row: {row}. Error: {e}'
            ) from e
    return routes_data


async def _perform_atomic_db_insertion_for_localization(
    db: Session,
    routes_to_create: Dict[str, Any],
    file_name: str,
    auth_token: str
) -> Dict[str, int]:
    '''
        Performs atomic database insertion for planned routes and points.
    '''
    point_fields = {
        'point_name', 
        'secuencial', 
        'latitude', 
        'longitude', 
        'reference_data'
    }

    routes_created = 0
    points_created = 0
    with db.begin_nested():
        for route_key, data in routes_to_create.items():
            if db.query(PlannedRoute).filter_by(
                route_code = data['route_data']['route_code'],
                company_id = data['route_data']['company_id']
            ).first():
                await _handle_files_service(
                    action = 'delete',
                    file_name = file_name,
                    auth_token = auth_token
                )
                raise RegisterAlreadyExistsError(
                    detail = f'''Planned route with code {route_key[0]
                        } already exists for company ID {route_key[1]}.'''
                )

            planned_route = PlannedRoute(**data['route_data'])
            db.add(planned_route)
            db.flush()
            details = [
                PlannedPoint(
                    planned_route_id = planned_route.id,
                    **{k: v for k, v in detail.items() if k in point_fields}
                )
                for detail in data['points_data']
            ]
            db.add_all(details)
            routes_created += 1
            points_created += len(details)

    return {'routes_created': routes_created, 'points_created': points_created}
