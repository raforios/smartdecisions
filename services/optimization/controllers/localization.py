'''
    Planned and executed routes — orchestration between the HTTP layer and
    `services.localization*`. Ported from LOCALIZATION.

    Every controller receives the authenticated account as `current_user`; it
    is the owner of everything read or written here. `request` is consumed by
    @handle_service_errors for the usage log.
'''
from typing import List

from boto3.resources.base import ServiceResource
from fastapi import Request

from schemas.localization import (
    BulkUploadPlannedResponseSchema,
    ExecutedPointCreateSchema,
    ExecutedPointResponseSchema,
    ExecutedRouteCreateSchema,
    ExecutedRouteDetailSchema,
    ExecutedRouteFilterSchema,
    ExecutedRouteResponseSchema,
    ExecutedRouteUpdateSchema,
    GroupLastKnownLocationsResponseSchema,
    InferPlannedRouteSchema,
    PlannedPointRef,
    PlannedPointResponseSchema,
    PlannedPointSchema,
    PlannedPointUpdateSchema,
    PlannedRouteCreateSchema,
    PlannedRouteFilterRequestSchema,
    PlannedRouteResponseSchema,
    PlannedRouteUpdateSchema,
    PlannedRouteUpdateStatusSchema,
    PointsVisitedResponseSchema,
    RouteComparisonFullResponseSchema,
    RouteComparisonsResponseSchema
)
from services.localization import (
    add_planned_point,
    bulk_create_planned_routes,
    create_planned_route,
    delete_planned_point,
    delete_planned_route,
    filter_planned_routes,
    get_planned_route,
    infer_planned_route,
    list_planned_routes,
    to_point_response,
    to_route_response,
    update_planned_point,
    update_planned_route,
    update_planned_route_status
)
from services.localization_executed import (
    close_executed_route,
    create_executed_route,
    get_executed_route,
    last_known_locations,
    link_routes_to_plan,
    list_executed_routes,
    register_executed_point,
    reopen_executed_route,
    to_executed_detail,
    to_executed_point_response,
    to_executed_response
)
from services.localization_stats import (
    full_route_comparison,
    points_visited,
    route_comparisons
)
from services.utils import audit_event, handle_service_errors


# ---------------------------------------------------------------------------
# Planned routes
# ---------------------------------------------------------------------------
@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'PlannedRoute', 'CREATE')
async def create_planned_route_controller(
    dynamodb_resource: ServiceResource,
    route_data: PlannedRouteCreateSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Creates a planned route with its stops for the caller.
    '''
    route = create_planned_route(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        route_data = route_data
    )
    return to_route_response(route)


@handle_service_errors('OPTIMIZATION')
async def get_planned_route_controller(
    dynamodb_resource: ServiceResource,
    planned_route_id: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Returns one of the caller's planned routes.
    '''
    route = get_planned_route(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        route_id = planned_route_id
    )
    return to_route_response(route)


@handle_service_errors('OPTIMIZATION')
async def get_all_planned_routes_controller(
    dynamodb_resource: ServiceResource,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> List[PlannedRouteResponseSchema]:
    '''
        Returns every planned route of the caller.
    '''
    routes = list_planned_routes(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user
    )
    return [to_route_response(route) for route in routes]


@handle_service_errors('OPTIMIZATION')
async def filter_planned_routes_controller(
    dynamodb_resource: ServiceResource,
    filters: PlannedRouteFilterRequestSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> List[PlannedRouteResponseSchema]:
    '''
        Returns the caller's planned routes that match the filters.
    '''
    routes = filter_planned_routes(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        filters = filters
    )
    return [to_route_response(route) for route in routes]


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'PlannedRoute', 'UPDATE')
async def update_planned_route_controller(
    dynamodb_resource: ServiceResource,
    planned_route_id: str,
    route_data: PlannedRouteUpdateSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Changes header fields of a planned route.
    '''
    route = update_planned_route(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        route_id = planned_route_id,
        route_data = route_data
    )
    return to_route_response(route)


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'PlannedRoute', 'UPDATE_STATUS')
async def update_planned_route_status_controller(
    dynamodb_resource: ServiceResource,
    planned_route_id: str,
    status_data: PlannedRouteUpdateStatusSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Moves a planned route along its lifecycle.
    '''
    route = update_planned_route_status(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        route_id = planned_route_id,
        new_status = status_data.status
    )
    return to_route_response(route)


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'PlannedRoute', 'DELETE')
async def delete_planned_route_controller(
    dynamodb_resource: ServiceResource,
    planned_route_id: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Deletes a planned route still in creation; returns it as it was.
    '''
    route = delete_planned_route(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        route_id = planned_route_id
    )
    return to_route_response(route)


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'PlannedRoute', 'BULK_CREATE')
async def bulk_upload_planned_routes_controller(
    dynamodb_resource: ServiceResource,
    csv_text: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> BulkUploadPlannedResponseSchema:
    '''
        Imports the plan another system exported, as CSV.
    '''
    return bulk_create_planned_routes(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        csv_text = csv_text
    )


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'PlannedRoute', 'INFER')
async def infer_planned_route_controller(
    dynamodb_resource: ServiceResource,
    request_data: InferPlannedRouteSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        No plan was loaded: build it from what the seller visited that day and
        link the day's routes to it.
    '''
    day_routes = list_executed_routes(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        filters = ExecutedRouteFilterSchema(
            seller = request_data.seller,
            date_from = request_data.date,
            date_to = request_data.date
        )
    )
    plan = infer_planned_route(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        request = request_data,
        executed_routes = day_routes
    )
    link_routes_to_plan(
        dynamodb_resource = dynamodb_resource,
        routes = day_routes,
        planned_route_id = plan['id']
    )
    return to_route_response(plan)


# ---------------------------------------------------------------------------
# Planned stops
# ---------------------------------------------------------------------------
@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'PlannedPoint', 'CREATE')
async def add_planned_point_controller(
    dynamodb_resource: ServiceResource,
    planned_route_id: str,
    point_data: PlannedPointSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> PlannedPointResponseSchema:
    '''
        Adds a stop to a planned route in creation.
    '''
    route, point = add_planned_point(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        route_id = planned_route_id,
        point_data = point_data
    )
    return to_point_response(route['id'], point)


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'PlannedPoint', 'UPDATE')
async def update_planned_point_controller(
    dynamodb_resource: ServiceResource,
    point_ref: PlannedPointRef,
    point_data: PlannedPointUpdateSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> PlannedPointResponseSchema:
    '''
        Edits a stop of a planned route in creation. `point_ref` carries
        `planned_route_id` and `planned_point_id`.
    '''
    route, point = update_planned_point(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        route_id = point_ref.planned_route_id,
        point_id = point_ref.planned_point_id,
        point_data = point_data
    )
    return to_point_response(route['id'], point)


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'PlannedPoint', 'DELETE')
async def delete_planned_point_controller(
    dynamodb_resource: ServiceResource,
    point_ref: PlannedPointRef,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> PlannedRouteResponseSchema:
    '''
        Removes a stop from a planned route in creation; returns the route.
    '''
    route = delete_planned_point(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        route_id = point_ref.planned_route_id,
        point_id = point_ref.planned_point_id
    )
    return to_route_response(route)


# ---------------------------------------------------------------------------
# Executed routes
# ---------------------------------------------------------------------------
@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'ExecutedRoute', 'CREATE')
async def create_executed_route_controller(
    dynamodb_resource: ServiceResource,
    route_data: ExecutedRouteCreateSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ExecutedRouteResponseSchema:
    '''
        A seller opens a route, optionally against an active plan.
    '''
    route = create_executed_route(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        route_data = route_data
    )
    return to_executed_response(route)


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'ExecutedPoint', 'CREATE')
async def register_executed_point_controller(
    dynamodb_resource: ServiceResource,
    point_data: ExecutedPointCreateSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ExecutedPointResponseSchema:
    '''
        The device reports a position or a visit on an open route.
    '''
    route, point = register_executed_point(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        point_data = point_data
    )
    return to_executed_point_response(route['id'], point)


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'ExecutedRoute', 'CLOSE')
async def close_executed_route_controller(
    dynamodb_resource: ServiceResource,
    executed_route_id: str,
    update_data: ExecutedRouteUpdateSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ExecutedRouteResponseSchema:
    '''
        The seller ends the route.
    '''
    route = close_executed_route(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        executed_route_id = executed_route_id,
        update_data = update_data
    )
    return to_executed_response(route)


@handle_service_errors('OPTIMIZATION')
@audit_event('OPTIMIZATION', 'ExecutedRoute', 'REOPEN')
async def reopen_executed_route_controller(
    dynamodb_resource: ServiceResource,
    executed_route_id: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ExecutedRouteResponseSchema:
    '''
        Undoes a close made the same day.
    '''
    route = reopen_executed_route(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        executed_route_id = executed_route_id
    )
    return to_executed_response(route)


@handle_service_errors('OPTIMIZATION')
async def get_executed_route_controller(
    dynamodb_resource: ServiceResource,
    executed_route_id: str,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> ExecutedRouteDetailSchema:
    '''
        One executed route with every reported point.
    '''
    route = get_executed_route(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        executed_route_id = executed_route_id
    )
    return to_executed_detail(route)


@handle_service_errors('OPTIMIZATION')
async def list_executed_routes_controller(
    dynamodb_resource: ServiceResource,
    filters: ExecutedRouteFilterSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> List[ExecutedRouteResponseSchema]:
    '''
        The caller's executed routes in a period, by seller and/or plan.
    '''
    routes = list_executed_routes(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        filters = filters
    )
    return [to_executed_response(route) for route in routes]


@handle_service_errors('OPTIMIZATION')
async def get_last_known_locations_controller(
    dynamodb_resource: ServiceResource,
    sellers: List[str],
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> GroupLastKnownLocationsResponseSchema:
    '''
        Where each requested seller last reported from.
    '''
    return GroupLastKnownLocationsResponseSchema(locations = last_known_locations(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        sellers = sellers
    ))


# ---------------------------------------------------------------------------
# Comparison and statistics
# ---------------------------------------------------------------------------
@handle_service_errors('OPTIMIZATION')
async def get_route_comparisons_controller(
    dynamodb_resource: ServiceResource,
    planned_route_id: str,
    filters: ExecutedRouteFilterSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> RouteComparisonsResponseSchema:
    '''
        Every execution of a plan, scored.
    '''
    return route_comparisons(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        planned_route_id = planned_route_id,
        filters = filters
    )


@handle_service_errors('OPTIMIZATION')
async def get_full_route_comparison_controller(
    dynamodb_resource: ServiceResource,
    planned_route_id: str,
    filters: ExecutedRouteFilterSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> RouteComparisonFullResponseSchema:
    '''
        Plan and executions with their points, for the map.
    '''
    return full_route_comparison(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        planned_route_id = planned_route_id,
        filters = filters
    )


@handle_service_errors('OPTIMIZATION')
async def get_points_visited_controller(
    dynamodb_resource: ServiceResource,
    seller: str,
    filters: ExecutedRouteFilterSchema,
    current_user: str,
    request: Request # pylint: disable=unused-argument
) -> PointsVisitedResponseSchema:
    '''
        Every point a seller reported in a period.
    '''
    return points_visited(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        seller = seller,
        filters = filters
    )
