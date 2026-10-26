'''
    Optimization controllers: the visit plan drawn from a sales dataset and
    one plan per seller. The clusters and the stop order are asked of
    ML_FUNCTIONS; the street geometry, of OSRM.
'''
import pandas as pd
from boto3.resources.base import ServiceResource
from fastapi import Request

from controllers.common import caller_token
from schemas.optimization import (
    DEFAULT_PLAN_DAYS,
    PlansBySellerResponse,
    PlansBySellerSchema,
    RoutePlanResponse
)
from services.optimization import (
    assign_days,
    available_sellers,
    build_client_points,
    build_day,
    scope_to_period
)
from services.analytics_utils import get_dataset_metadata
from services.localization_sources import SalesSource, plans_by_seller
from services.utils import audit_event, handle_service_errors, read_file_rows


@handle_service_errors('COMMERCIAL')
async def route_plan_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    params: dict,
    current_user: str,
    request: Request
) -> RoutePlanResponse:
    '''
        Builds a visit plan straight from an ingested sales dataset.

        The clients are the ones who actually bought in the period, the visit
        days come from clustering those clients geographically, and the order
        within each day is the 2-opt tour projected onto real streets. Nothing
        here is read from the legacy route table. The dataset is read with its
        owner as part of the lookup: another account's answers like a missing one.
    '''
    metadata = get_dataset_metadata(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    dataframe = pd.DataFrame(read_file_rows(metadata['file_s3_key'], caller_token(request)))
    dataframe = scope_to_period(dataframe, params)

    sellers = available_sellers(dataframe)
    auth_token = caller_token(request)
    clients = build_client_points(dataframe, auth_token, seller = params.get('seller'))
    clients = assign_days(clients, int(params.get('days') or DEFAULT_PLAN_DAYS), auth_token)

    days = [
        build_day(clients, day, auth_token)
        for day in sorted(clients['day'].unique())
    ]
    return RoutePlanResponse(
        dataset_id = dataset_id,
        sellers = sellers,
        seller = params.get('seller'),
        total_clients = int(len(clients)),
        days = [day for day in days if day.stops]
    )


@handle_service_errors('COMMERCIAL')
@audit_event('COMMERCIAL', 'PlannedRoute', 'BULK_CREATE')
async def plans_by_seller_controller(
    dynamodb_resource: ServiceResource,
    dataset_id: str,
    body: PlansBySellerSchema,
    current_user: str,
    request: Request
) -> PlansBySellerResponse:
    '''
        One plan per seller from that seller's portfolio in the sales file.

        The dataset is read with its owner as part of the lookup: a dataset of
        another account answers like a missing one.
    '''
    metadata = get_dataset_metadata(
        dynamodb_resource = dynamodb_resource,
        dataset_id = dataset_id,
        owner_email = current_user
    )
    auth_token = caller_token(request)
    dataframe = scope_to_period(
        pd.DataFrame(read_file_rows(metadata['file_s3_key'], auth_token)),
        body.model_dump(include = {'date_from', 'date_to'})
    )
    return plans_by_seller(
        dynamodb_resource = dynamodb_resource,
        owner_email = current_user,
        source = SalesSource(dataset_id = dataset_id, dataframe = dataframe,
                             auth_token = auth_token),
        request = body
    )
