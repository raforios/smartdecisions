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
from typing import Any, TypedDict


class PlannedPointItem(TypedDict, total = False):
    '''
        One stop of a planned route, in visiting order.
    '''
    id: str
    point_name: str
    secuencial: int
    latitude: float
    longitude: float
    reference_data: str | None
    client_id: str | None


class PlannedRouteItem(TypedDict, total = False):
    '''
        A route the client planned — created in the app, uploaded from another
        system, or derived from what the sellers actually visited.

        Table: optimization_planned_routes
        Partition Key: owner_email (String)
        Sort Key:      id          (String, UUID)

        `route_code` is unique per owner; `seller` is who the route is assigned
        to, by the name the sales file uses.

        `plan_date` is what tells a plan apart from a template, and the future
        apart from the past: the planning screen asks from today on and the
        history screen asks backwards. A route without it is a reusable
        template that belongs to no day. Stored as 'YYYY-MM-DD' text, which
        compares and sorts correctly in DynamoDB.
    '''
    owner_email: str
    id: str
    route_code: str
    route_name: str
    description: str | None
    seller: str | None
    plan_date: str | None
    status: str
    created_at: str
    points: list[PlannedPointItem]
    # Where the route starts and ends, when the plan fixes it ({name,
    # latitude, longitude}). Absent: open, the seller starts and ends anywhere.
    start_point: dict[str, Any] | None
    end_point: dict[str, Any] | None


class ExecutedPointItem(TypedDict, total = False):
    '''
        One position a seller reported while running a route. When it is a
        visit, it also says who was visited and what came of it.
    '''
    id: str
    latitude: float
    longitude: float
    timestamp: str
    client_id: str | None
    outcome: str | None
    order_id: str | None
    items: list[dict]


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
    planned_route_id: str | None
    start_time: str
    end_time: str | None
    start_latitude: float
    start_longitude: float
    max_distance_start_point: float
    end_latitude: float | None
    end_longitude: float | None
    max_distance_end_point: float | None
    last_latitude: float | None
    last_longitude: float | None
    last_timestamp: str | None
    points: list[ExecutedPointItem]
