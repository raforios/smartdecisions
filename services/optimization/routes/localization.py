'''
    Planned and executed routes — HTTP layer. Ported from LOCALIZATION and
    mounted under the same prefix as the planning endpoints, so the frontend
    talks to one service for everything about routes.
'''
from typing import List

from boto3.resources.base import ServiceResource
from fastapi import APIRouter, Body, Depends, Path, Query, Request, status
from pydantic import BaseModel

from controllers.localization import (
    add_planned_point_controller,
    bulk_upload_planned_routes_controller,
    close_executed_route_controller,
    create_executed_route_controller,
    get_executed_route_controller,
    get_last_known_locations_controller,
    list_executed_routes_controller,
    register_executed_point_controller,
    reopen_executed_route_controller,
    create_planned_route_controller,
    delete_planned_point_controller,
    delete_planned_route_controller,
    filter_planned_routes_controller,
    get_all_planned_routes_controller,
    get_planned_route_controller,
    infer_planned_route_controller,
    get_points_visited_controller,
    get_route_comparisons_controller,
    get_full_route_comparison_controller,
    update_planned_point_controller,
    update_planned_route_controller,
    update_planned_route_status_controller
)
from schemas.localization import (
    BulkUploadPlannedResponseSchema,
    CallerClaims,
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
    FIELD_ROLES,
    MANAGEMENT_ROLES,
    PointsVisitedResponseSchema,
    TrackingRole,
    RouteComparisonFullResponseSchema,
    RouteComparisonsResponseSchema
)
from routes.common import csv_upload_text, get_caller
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import require_roles

router = APIRouter(prefix = '/v1/optimization', tags = ['Route tracking'])

_ROUTE_ID = Path(..., min_length = 8, max_length = 64, description = 'Planned route id.')
_EXECUTED_ID = Path(..., min_length = 8, max_length = 64, description = 'Executed route id.')


def own_seller(
    caller: CallerClaims,
    payload: BaseModel
) -> BaseModel:
    '''
        For a SELLER, pins `seller` to their own email on whatever they send —
        a route start or a listing filter — so they neither run routes as
        somebody else nor read somebody else's. Anyone else passes through.

        Args:
            caller (CallerClaims): Who is calling.
            payload (BaseModel): A model with a `seller` field.

        Returns:
            BaseModel: The same model, `seller` overridden when it must be.
    '''
    if caller.role == TrackingRole.SELLER.value:
        return payload.model_copy(update = {'seller': caller.email})
    return payload


# ---------------------------------------------------------------------------
# Planned routes
# ---------------------------------------------------------------------------
@router.post(
    '/routes/planned',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Create a planned route with its stops',
    description = 'The route starts IN CREATION; activate it once its stops are final.'
)
async def create_planned_route_endpoint(
    request: Request,
    route_data: PlannedRouteCreateSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> PlannedRouteResponseSchema:
    '''
        Endpoint to create a planned route.
    '''
    message = f'User: {current_user}. Creating planned route {route_data.route_code}.'
    logger.info(message)
    return await create_planned_route_controller(
        dynamodb_resource = dynamodb_resource,
        route_data = route_data,
        current_user = current_user,
        request = request
    )


@router.get(
    '/routes/planned',
    response_model = List[PlannedRouteResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'List the planned routes of the caller'
)
async def get_all_planned_routes_endpoint(
    request: Request,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*FIELD_ROLES))
) -> List[PlannedRouteResponseSchema]:
    '''
        Endpoint to list planned routes.
    '''
    message = f'User: {current_user}. Listing planned routes.'
    logger.info(message)
    return await get_all_planned_routes_controller(
        dynamodb_resource = dynamodb_resource,
        current_user = current_user,
        request = request
    )


@router.post(
    '/routes/planned/filter',
    response_model = List[PlannedRouteResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'Filter the planned routes of the caller',
    description = 'Any combination of ids, code, name fragment, status and seller.'
)
async def filter_planned_routes_endpoint(
    request: Request,
    filters: PlannedRouteFilterRequestSchema = Body(
        default_factory = PlannedRouteFilterRequestSchema
    ),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*FIELD_ROLES))
) -> List[PlannedRouteResponseSchema]:
    '''
        Endpoint to filter planned routes.
    '''
    message = f'User: {current_user}. Filtering planned routes.'
    logger.info(message)
    return await filter_planned_routes_controller(
        dynamodb_resource = dynamodb_resource,
        filters = filters,
        current_user = current_user,
        request = request
    )


@router.post(
    '/routes/planned/bulk-upload',
    response_model = BulkUploadPlannedResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Import planned routes from a CSV',
    description = (
        'One row per stop with the route header repeated: route_code, route_name, '
        'point_name, secuencial, latitude, longitude (+ optional description, seller, '
        'reference_data, client_id). All-or-nothing; routes start IN CREATION.'
    )
)
async def bulk_upload_planned_routes_endpoint(
    request: Request,
    csv_text: str = Depends(csv_upload_text),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> BulkUploadPlannedResponseSchema:
    '''
        Endpoint to bulk-upload planned routes.
    '''
    message = f'User: {current_user}. Bulk-uploading planned routes.'
    logger.info(message)
    return await bulk_upload_planned_routes_controller(
        csv_text = csv_text,
        dynamodb_resource = dynamodb_resource,
        current_user = current_user,
        request = request
    )


@router.post(
    '/routes/planned/infer',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Build the plan from what a seller visited on a day',
    description = (
        'For days that ran without a plan: the visits become the stops in the '
        'order they happened, and the day\'s executions get linked to the new plan.'
    )
)
async def infer_planned_route_endpoint(
    request: Request,
    request_data: InferPlannedRouteSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> PlannedRouteResponseSchema:
    '''
        Endpoint to infer a planned route.
    '''
    message = (
        f'User: {current_user}. Inferring plan of {request_data.seller} on {request_data.date}.'
    )
    logger.info(message)
    return await infer_planned_route_controller(
        dynamodb_resource = dynamodb_resource,
        request_data = request_data,
        current_user = current_user,
        request = request
    )


@router.get(
    '/routes/planned/{planned_route_id}',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Get one planned route with its stops'
)
async def get_planned_route_endpoint(
    request: Request,
    planned_route_id: str = _ROUTE_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*FIELD_ROLES))
) -> PlannedRouteResponseSchema:
    '''
        Endpoint to read a planned route.
    '''
    message = f'User: {current_user}. Reading planned route {planned_route_id}.'
    logger.info(message)
    return await get_planned_route_controller(
        dynamodb_resource = dynamodb_resource,
        planned_route_id = planned_route_id,
        current_user = current_user,
        request = request
    )


@router.patch(
    '/routes/planned/{planned_route_id}',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Update the header of a planned route'
)
async def update_planned_route_endpoint(
    request: Request,
    route_data: PlannedRouteUpdateSchema,
    planned_route_id: str = _ROUTE_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> PlannedRouteResponseSchema:
    '''
        Endpoint to update a planned route.
    '''
    message = f'User: {current_user}. Updating planned route {planned_route_id}.'
    logger.info(message)
    return await update_planned_route_controller(
        dynamodb_resource = dynamodb_resource,
        planned_route_id = planned_route_id,
        route_data = route_data,
        current_user = current_user,
        request = request
    )


@router.patch(
    '/routes/planned/{planned_route_id}/status',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Change the status of a planned route',
    description = 'IN CREATION -> ACTIVE, then ACTIVE <-> INACTIVE.'
)
async def update_planned_route_status_endpoint(
    request: Request,
    status_data: PlannedRouteUpdateStatusSchema,
    planned_route_id: str = _ROUTE_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> PlannedRouteResponseSchema:
    '''
        Endpoint to change a planned route's status.
    '''
    message = (
        f'User: {current_user}. Planned route {planned_route_id} -> {status_data.status.value}.'
    )
    logger.info(message)
    return await update_planned_route_status_controller(
        dynamodb_resource = dynamodb_resource,
        planned_route_id = planned_route_id,
        status_data = status_data,
        current_user = current_user,
        request = request
    )


@router.delete(
    '/routes/planned/{planned_route_id}',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Delete a planned route still in creation'
)
async def delete_planned_route_endpoint(
    request: Request,
    planned_route_id: str = _ROUTE_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> PlannedRouteResponseSchema:
    '''
        Endpoint to delete a planned route.
    '''
    message = f'User: {current_user}. Deleting planned route {planned_route_id}.'
    logger.info(message)
    return await delete_planned_route_controller(
        dynamodb_resource = dynamodb_resource,
        planned_route_id = planned_route_id,
        current_user = current_user,
        request = request
    )


# ---------------------------------------------------------------------------
# Planned stops
# ---------------------------------------------------------------------------
@router.post(
    '/routes/planned/{planned_route_id}/points',
    response_model = PlannedPointResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Add a stop to a planned route in creation'
)
async def add_planned_point_endpoint(
    request: Request,
    point_data: PlannedPointSchema,
    planned_route_id: str = _ROUTE_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> PlannedPointResponseSchema:
    '''
        Endpoint to add a stop.
    '''
    message = f'User: {current_user}. Adding stop to planned route {planned_route_id}.'
    logger.info(message)
    return await add_planned_point_controller(
        dynamodb_resource = dynamodb_resource,
        planned_route_id = planned_route_id,
        point_data = point_data,
        current_user = current_user,
        request = request
    )


@router.patch(
    '/routes/planned/{planned_route_id}/points/{planned_point_id}',
    response_model = PlannedPointResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Edit a stop of a planned route in creation'
)
async def update_planned_point_endpoint(
    request: Request,
    point_data: PlannedPointUpdateSchema,
    point_ref: PlannedPointRef = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> PlannedPointResponseSchema:
    '''
        Endpoint to edit a stop.
    '''
    message = (
        f'User: {current_user}. Updating stop {point_ref.planned_point_id} '
        f'of planned route {point_ref.planned_route_id}.'
    )
    logger.info(message)
    return await update_planned_point_controller(
        dynamodb_resource = dynamodb_resource,
        point_ref = point_ref,
        point_data = point_data,
        current_user = current_user,
        request = request
    )


@router.delete(
    '/routes/planned/{planned_route_id}/points/{planned_point_id}',
    response_model = PlannedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Remove a stop from a planned route in creation'
)
async def delete_planned_point_endpoint(
    request: Request,
    point_ref: PlannedPointRef = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> PlannedRouteResponseSchema:
    '''
        Endpoint to remove a stop.
    '''
    message = (
        f'User: {current_user}. Removing stop {point_ref.planned_point_id} '
        f'from planned route {point_ref.planned_route_id}.'
    )
    logger.info(message)
    return await delete_planned_point_controller(
        dynamodb_resource = dynamodb_resource,
        point_ref = point_ref,
        current_user = current_user,
        request = request
    )


# ---------------------------------------------------------------------------
# Executed routes
# ---------------------------------------------------------------------------
@router.post(
    '/routes/executed',
    response_model = ExecutedRouteResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'A seller starts a route',
    description = 'With `planned_route_id`, the plan must be ACTIVE and the start '
                  'within `max_distance_start_point` metres of its first stop.'
)
async def create_executed_route_endpoint(
    request: Request,
    route_data: ExecutedRouteCreateSchema,
    caller: CallerClaims = Depends(get_caller),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*FIELD_ROLES))
) -> ExecutedRouteResponseSchema:
    '''
        Endpoint to open an executed route. A seller can only open their own:
        the route is theirs whatever the body says.
    '''
    route_data = own_seller(caller, route_data)
    message = f'User: {current_user}. {route_data.seller} starts a route.'
    logger.info(message)
    return await create_executed_route_controller(
        dynamodb_resource = dynamodb_resource,
        route_data = route_data,
        current_user = current_user,
        request = request
    )


@router.get(
    '/routes/executed',
    response_model = List[ExecutedRouteResponseSchema],
    status_code = status.HTTP_200_OK,
    summary = 'List executed routes',
    description = 'Bounded by start date, narrowed by seller and/or planned route.'
)
async def list_executed_routes_endpoint(
    request: Request,
    filters: ExecutedRouteFilterSchema = Depends(),
    caller: CallerClaims = Depends(get_caller),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*FIELD_ROLES))
) -> List[ExecutedRouteResponseSchema]:
    '''
        Endpoint to list executed routes. A seller only sees their own.
    '''
    filters = own_seller(caller, filters)
    message = f'User: {current_user}. Listing executed routes.'
    logger.info(message)
    return await list_executed_routes_controller(
        dynamodb_resource = dynamodb_resource,
        filters = filters,
        current_user = current_user,
        request = request
    )


@router.post(
    '/routes/executed/points',
    response_model = ExecutedPointResponseSchema,
    status_code = status.HTTP_201_CREATED,
    summary = 'Report a position or a visit on an open route'
)
async def register_executed_point_endpoint(
    request: Request,
    point_data: ExecutedPointCreateSchema,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*FIELD_ROLES))
) -> ExecutedPointResponseSchema:
    '''
        Endpoint to register an executed point.
    '''
    message = f'User: {current_user}. Point on executed route {point_data.executed_route_id}.'
    logger.info(message)
    return await register_executed_point_controller(
        dynamodb_resource = dynamodb_resource,
        point_data = point_data,
        current_user = current_user,
        request = request
    )


@router.get(
    '/routes/executed/last-location',
    response_model = GroupLastKnownLocationsResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Where each seller last reported from',
    description = 'Repeat `sellers` for each name: sellers=Ana&sellers=Juan.'
)
async def get_last_known_locations_endpoint(
    request: Request,
    sellers: List[str] = Query(..., min_length = 1),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> GroupLastKnownLocationsResponseSchema:
    '''
        Endpoint for the live view.
    '''
    message = f'User: {current_user}. Locating {len(sellers)} seller(s).'
    logger.info(message)
    return await get_last_known_locations_controller(
        dynamodb_resource = dynamodb_resource,
        sellers = sellers,
        current_user = current_user,
        request = request
    )


@router.get(
    '/routes/executed/{executed_route_id}',
    response_model = ExecutedRouteDetailSchema,
    status_code = status.HTTP_200_OK,
    summary = 'One executed route with every reported point'
)
async def get_executed_route_endpoint(
    request: Request,
    executed_route_id: str = _EXECUTED_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*FIELD_ROLES))
) -> ExecutedRouteDetailSchema:
    '''
        Endpoint to read an executed route.
    '''
    message = f'User: {current_user}. Reading executed route {executed_route_id}.'
    logger.info(message)
    return await get_executed_route_controller(
        dynamodb_resource = dynamodb_resource,
        executed_route_id = executed_route_id,
        current_user = current_user,
        request = request
    )


@router.patch(
    '/routes/executed/{executed_route_id}',
    response_model = ExecutedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'A seller ends a route',
    description = 'Against a plan, the end must be within `max_distance_end_point` '
                  'metres of its last stop.'
)
async def close_executed_route_endpoint(
    request: Request,
    update_data: ExecutedRouteUpdateSchema,
    executed_route_id: str = _EXECUTED_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*FIELD_ROLES))
) -> ExecutedRouteResponseSchema:
    '''
        Endpoint to close an executed route.
    '''
    message = f'User: {current_user}. Closing executed route {executed_route_id}.'
    logger.info(message)
    return await close_executed_route_controller(
        dynamodb_resource = dynamodb_resource,
        executed_route_id = executed_route_id,
        update_data = update_data,
        current_user = current_user,
        request = request
    )


@router.patch(
    '/routes/executed/{executed_route_id}/reopen',
    response_model = ExecutedRouteResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Reopen a route closed by mistake, the same day'
)
async def reopen_executed_route_endpoint(
    request: Request,
    executed_route_id: str = _EXECUTED_ID,
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*FIELD_ROLES))
) -> ExecutedRouteResponseSchema:
    '''
        Endpoint to reopen an executed route.
    '''
    message = f'User: {current_user}. Reopening executed route {executed_route_id}.'
    logger.info(message)
    return await reopen_executed_route_controller(
        dynamodb_resource = dynamodb_resource,
        executed_route_id = executed_route_id,
        current_user = current_user,
        request = request
    )


# ---------------------------------------------------------------------------
# Comparison and statistics
# ---------------------------------------------------------------------------
@router.get(
    '/routes/comparison/{planned_route_id}',
    response_model = RouteComparisonFullResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Plan and executions with their points',
    description = 'For the map: the planned stops and every execution in the period, '
                  'optionally one seller.'
)
async def get_full_route_comparison_endpoint(
    request: Request,
    planned_route_id: str = _ROUTE_ID,
    filters: ExecutedRouteFilterSchema = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> RouteComparisonFullResponseSchema:
    '''
        Endpoint for the full comparison.
    '''
    message = f'User: {current_user}. Full comparison of planned route {planned_route_id}.'
    logger.info(message)
    return await get_full_route_comparison_controller(
        dynamodb_resource = dynamodb_resource,
        planned_route_id = planned_route_id,
        filters = filters,
        current_user = current_user,
        request = request
    )


@router.get(
    '/statistics/route-comparisons/{planned_route_id}',
    response_model = RouteComparisonsResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Score every execution of a plan',
    description = 'A planned stop counts as visited when a reported point names its client '
                  'or falls within the configured radius of it.'
)
async def get_route_comparisons_endpoint(
    request: Request,
    planned_route_id: str = _ROUTE_ID,
    filters: ExecutedRouteFilterSchema = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> RouteComparisonsResponseSchema:
    '''
        Endpoint for the scored comparisons.
    '''
    message = f'User: {current_user}. Scoring executions of planned route {planned_route_id}.'
    logger.info(message)
    return await get_route_comparisons_controller(
        dynamodb_resource = dynamodb_resource,
        planned_route_id = planned_route_id,
        filters = filters,
        current_user = current_user,
        request = request
    )


@router.get(
    '/statistics/sellers/{seller}/points-visited',
    response_model = PointsVisitedResponseSchema,
    status_code = status.HTTP_200_OK,
    summary = 'Every point a seller reported in a period'
)
async def get_points_visited_endpoint(
    request: Request,
    seller: str = Path(..., min_length = 1, max_length = 128),
    filters: ExecutedRouteFilterSchema = Depends(),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> PointsVisitedResponseSchema:
    '''
        Endpoint for a seller's visited points.
    '''
    message = f'User: {current_user}. Points visited by {seller}.'
    logger.info(message)
    return await get_points_visited_controller(
        dynamodb_resource = dynamodb_resource,
        seller = seller,
        filters = filters,
        current_user = current_user,
        request = request
    )
