'''
    Route Point Model for DynamoDB.
'''
from typing import TypedDict


class RoutePoint(TypedDict, total = False):
    '''
        Python model representing a single client geolocation point of a planned
        route in DynamoDB.

        Table: t_optimization_routes
        Partition Key: route_day_key (String, format: "{route_id}#{day}")
        Sort Key:      client_id     (Number)

        The composite partition key lets a single Query call retrieve all
        clients of a given (route_id, day) in O(items) without a Scan.
    '''
    route_day_key: str
    client_id: int
    route_id: int
    day: int
    latitude: float
    longitude: float
    client: str
