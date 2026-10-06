'''
    Controller-level tests for the route plan endpoint.

    These exist because the engine tests did not catch a real production
    failure: `plan_day` was changed to return RouteStop DTOs while `build_day`
    still subscripted them like dicts, which only raises when the endpoint runs.
'''
import asyncio
from datetime import date, timedelta
from typing import Any
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from fastapi import HTTPException
from moto import mock_aws

from schemas.optimization import (
    OptimizationError,
    PlansBySellerResponse,
    PlansBySellerSchema,
    RoutePlanResponse
)
from controllers import optimization as controllers
from services import localization, optimization_utils
from services import optimization as optimization_service
from tests.dynamo_helpers import build_resource


def _sales_frame() -> pd.DataFrame:
    '''
        Builds a geocoded frame with enough clients to fill two days.

        Returns:
            pd.DataFrame: Sales rows as ingest hands them over.
    '''
    start = date(2026, 1, 5)
    return pd.DataFrame([
        {
            'date': pd.Timestamp(start + timedelta(days = index * 3)),
            'order_id': f'F-{index // 2:04d}',
            'pos_id': f'PDV-{index % 8}',
            'pos_name': f'Tienda {index % 8}',
            'product_id': f'SKU-{index % 5}',
            'product_name': f'Producto {index % 5}',
            'seller': ['Ana', 'Juan'][index % 2],
            'latitude': -16.5 + (index % 8) * 0.01,
            'longitude': -68.1 - (index % 8) * 0.01,
            'quantity': 3,
            'total_amount': 25.5,
        }
        for index in range(60)
    ])


@pytest.fixture(name = 'dataset')
def _dataset():
    '''
        Serves the sales frame in place of the Dynamo + S3 round trip.

        Returns:
            str: The dataset id the controller is called with.
    '''
    with patch.object(controllers, 'get_dataset_metadata',
                      lambda **_: {'file_s3_key': 'k', 'status': 'validated'}), \
         patch.object(controllers, 'load_dataframe_from_s3', lambda _: _sales_frame()):
        yield 'test-dataset-id'


def test_route_plan_returns_days_with_ordered_stops(dataset):
    '''The endpoint must build the full response, stops and geometry included.'''
    response = asyncio.run(controllers.route_plan_controller(
        dynamodb_resource = None,
        dataset_id = dataset,
        params = {'days': 2},
        current_user = 'tester@bearsoft.com.bo',
        request = None
    ))

    assert isinstance(response, RoutePlanResponse)
    assert [day.day for day in response.days] == [1, 2]
    first_day = response.days[0]
    assert first_day.stops
    assert [stop.stop_order for stop in first_day.stops] == list(
        range(1, len(first_day.stops) + 1)
    )
    assert all(stop.client and stop.segment for stop in first_day.stops)
    assert first_day.distance_km > 0


def _plans_by_seller(
    resource: Any,
    dataset_id: str
) -> PlansBySellerResponse:
    '''
        Runs the plans-by-seller controller for day 1 of a two-day split.

        Args:
            resource (Any): Mocked DynamoDB resource.
            dataset_id (str): The dataset the fixture serves.

        Returns:
            PlansBySellerResponse: What the endpoint answers.
    '''
    return asyncio.run(controllers.plans_by_seller_controller(
        dynamodb_resource = resource,
        dataset_id = dataset_id,
        body = PlansBySellerSchema(days = 2, day = 1, plan_date = date(2026, 10, 5)),
        current_user = 'tester@bearsoft.com.bo',
        request = None
    ))


def test_each_seller_gets_a_plan_from_their_own_portfolio(dataset):
    '''
        A plan for "everybody" put the whole team on one route and measured
        each seller against all of it. Each plan now holds only the clients
        the file says that seller sold to, and saving twice does not duplicate.
        No call goes to OSRM: the public router is asked when a plan is
        opened, not once per seller here.
    '''
    def _no_osrm(
        *_args: Any,
        **_kwargs: Any
    ) -> None:
        raise AssertionError('OSRM was called while splitting by seller')

    frame = _sales_frame()
    portfolios = {seller: set(rows['pos_id']) for seller, rows in frame.groupby('seller')}
    with mock_aws(), patch.object(optimization_service, 'road_trip', _no_osrm):
        resource = build_resource([(localization.PLANNED_ROUTES_TABLE, 'owner_email', 'id')])
        first = _plans_by_seller(resource, dataset)
        again = _plans_by_seller(resource, dataset)
        stored = localization.list_planned_routes(resource, 'tester@bearsoft.com.bo')

    assert sorted(plan.seller for plan in first.created) == ['Ana', 'Juan']
    assert sorted(again.already_planned) == ['Ana', 'Juan'] and not again.created
    assert len(stored) == 2
    for plan in stored:
        assert {stop['client_id'] for stop in plan['points']} <= portfolios[plan['seller']]
        assert plan['plan_date'] == '2026-10-05'


def test_a_dataset_of_another_owner_answers_like_a_missing_one():
    '''`CLAUDE.md` §8: a foreign dataset and no dataset are indistinguishable.'''
    table = Mock()
    table.get_item.return_value = {'Item': {
        'id': 'ds-1', 'owner_email': 'otra@empresa.com', 'status': 'validated'
    }}
    resource = Mock(Table = Mock(return_value = table))

    with pytest.raises(HTTPException) as foreign:
        optimization_utils.get_dataset_metadata(resource, 'ds-1', 'yo@empresa.com')
    assert foreign.value.status_code == 404
    assert optimization_utils.get_dataset_metadata(resource, 'ds-1')['id'] == 'ds-1'

    # And through the endpoint that plans from the file: the Histórico.
    with pytest.raises(HTTPException) as planned:
        asyncio.run(controllers.route_plan_controller(
            dynamodb_resource = resource,
            dataset_id = 'ds-1',
            params = {'days': 2},
            current_user = 'yo@empresa.com',
            request = None
        ))
    assert planned.value.status_code == 404


def test_plans_by_seller_can_start_at_the_company_base_point(dataset):
    '''
        Cases 7 and 8 of the routes spec: asked to, each plan starts at the
        company's base point without counting it as a stop; not asked, it has
        no fixed start; asked with no base point configured, refused.
    '''
    # pylint: disable=import-outside-toplevel
    import boto3
    from schemas.localization import RouteEndpointSchema
    from schemas.optimization_settings import RouteSettingsSchema
    from services import optimization_settings

    owner = 'tester@bearsoft.com.bo'
    body = PlansBySellerSchema(days = 2, day = 1, plan_date = date(2026, 10, 6),
                               start_at_base = True)
    with mock_aws():
        resource = build_resource([(localization.PLANNED_ROUTES_TABLE, 'owner_email', 'id')])
        boto3.resource('dynamodb', region_name = 'us-east-1').create_table(
            TableName = optimization_settings.SETTINGS_TABLE,
            KeySchema = [{'AttributeName': 'owner_email', 'KeyType': 'HASH'}],
            AttributeDefinitions = [{'AttributeName': 'owner_email', 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
        with pytest.raises(HTTPException) as unset:
            asyncio.run(controllers.plans_by_seller_controller(
                dynamodb_resource = resource, dataset_id = dataset, body = body,
                current_user = owner, request = None))
        assert unset.value.detail == OptimizationError.BASE_POINT_NOT_SET.value

        optimization_settings.save_route_settings(resource, owner, RouteSettingsSchema(
            base_point = RouteEndpointSchema(name = 'Depósito', latitude = -16.54,
                                             longitude = -68.07)))
        asyncio.run(controllers.plans_by_seller_controller(
            dynamodb_resource = resource, dataset_id = dataset, body = body,
            current_user = owner, request = None))
        stored = localization.list_planned_routes(resource, owner)

    assert stored and all(plan['start_point']['name'] == 'Depósito' for plan in stored)
    assert all(plan.get('end_point') is None for plan in stored)
    assert all(stop['point_name'] != 'Depósito' for plan in stored for stop in plan['points'])
