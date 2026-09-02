'''
    Controller-level tests for the route plan endpoint.

    These exist because the engine tests did not catch a real production
    failure: `plan_day` was changed to return RouteStop DTOs while `build_day`
    still subscripted them like dicts, which only raises when the endpoint runs.
'''
import asyncio
from datetime import date, timedelta
from unittest.mock import patch

import pandas as pd
import pytest

from schemas.optimization import RoutePlanResponse
from controllers import optimization as controllers


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
