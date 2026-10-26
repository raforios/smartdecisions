'''
    Optimization: routes handler. The visit plan drawn from a sales dataset
    and one plan per seller from each seller's portfolio.
'''
from fastapi import APIRouter, Depends, Path, Request, status
from boto3.resources.base import ServiceResource

from controllers.optimization import (
    plans_by_seller_controller,
    route_plan_controller
)
from schemas.localization import MANAGEMENT_ROLES
from schemas.optimization import (
    PlansBySellerResponse,
    PlansBySellerSchema,
    PlanQueryParams,
    RoutePlanResponse
)
from services.db_connection import GET_DB_DEPENDENCY
from services.logger_config import custom_logger as logger
from services.security import get_current_owner, require_roles

router = APIRouter(prefix = '/v1/commercial', tags = ['Optimization'])


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
    current_user: str = Depends(get_current_owner)
) -> RoutePlanResponse:
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


@router.post(
    '/plan/{dataset_id}/by-seller',
    response_model = PlansBySellerResponse,
    status_code = status.HTTP_201_CREATED,
    summary = 'One plan per seller, from each seller\'s portfolio',
    description = (
        'Splits each seller\'s own clients —the ones the sales file says they '
        'sold to— into days by proximity, and saves the requested day as that '
        'seller\'s plan for the given date. The order is the local 2-opt tour: '
        'the street geometry is drawn when a plan is opened, not once per '
        'seller here.'
    )
)
async def plans_by_seller_endpoint(
    request: Request,
    body: PlansBySellerSchema,
    dataset_id: str = Path(..., min_length = 8, max_length = 64),
    dynamodb_resource: ServiceResource = Depends(GET_DB_DEPENDENCY),
    current_user: str = Depends(require_roles(*MANAGEMENT_ROLES))
) -> PlansBySellerResponse:
    '''
        Endpoint creating one plan per seller from a dataset.
    '''
    message = (f'User: {current_user}. Plans by seller from dataset {dataset_id}: '
               f'day {body.day} of {body.days}, for {body.plan_date}.')
    logger.info(message)
    return await plans_by_seller_controller(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        body = body,
        current_user = current_user,
        request = request
    )
