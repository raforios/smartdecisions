'''
    Planned and executed route items for DynamoDB.

    Ported from LOCALIZATION (MySQL, four tables) into two composite-key tables.
    The points of a route travel inside the route item: a route has a few dozen
    stops at most, so one read returns the whole route and there is no join to
    reproduce.

    The owner is part of the partition key on both tables — a client only ever
    queries its own partition, so a foreign route is indistinguishable from a
    missing one.
'''
from typing import List, Optional, TypedDict


class PlannedPointItem(TypedDict, total = False):
    '''
        One stop of a planned route, in visiting order.
    '''
    id: str
    point_name: str
    secuencial: int
    latitude: float
    longitude: float
    reference_data: Optional[str]
    client_id: Optional[str]


class PlannedRouteItem(TypedDict, total = False):
    '''
        A route the client planned — created in the app, uploaded from another
        system, or derived from what the sellers actually visited.

        Table: optimization_planned_routes
        Partition Key: owner_email (String)
        Sort Key:      id          (String, UUID)

        `route_code` is unique per owner; `seller` is who the route is assigned
        to, by the name the sales file uses.
    '''
    owner_email: str
    id: str
    route_code: str
    route_name: str
    description: Optional[str]
    seller: Optional[str]
    status: str
    created_at: str
    points: List[PlannedPointItem]


class ExecutedPointItem(TypedDict, total = False):
    '''
        One position a seller reported while running a route. When it is a
        visit, it also says who was visited and what came of it.
    '''
    id: str
    latitude: float
    longitude: float
    timestamp: str
    client_id: Optional[str]
    outcome: Optional[str]
    order_id: Optional[str]
    items: List[dict]


class ExecutedRouteItem(TypedDict, total = False):
    '''
        A route a seller actually ran, optionally against a planned one.

        Table: optimization_executed_routes
        Partition Key: owner_email (String)
        Sort Key:      id          (String, "{YYYYMMDDTHHMMSS}-{uuid8}")

        The sort key starts with the start time so a day or a period is one
        bounded Query on the owner's partition, with no index to maintain.
        The last reported position is copied onto the route so "where is the
        seller now" does not have to walk the point list.
    '''
    owner_email: str
    id: str
    seller: str
    planned_route_id: Optional[str]
    start_time: str
    end_time: Optional[str]
    start_latitude: float
    start_longitude: float
    max_distance_start_point: float
    end_latitude: Optional[float]
    end_longitude: Optional[float]
    max_distance_end_point: Optional[float]
    last_latitude: Optional[float]
    last_longitude: Optional[float]
    last_timestamp: Optional[str]
    points: List[ExecutedPointItem]
