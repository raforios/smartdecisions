'''
    Controller-level tests: every analytics endpoint must return its response
    model fully built.

    These exist because the engine tests did not catch a real production
    failure: the engines were changed to return DTOs while the controllers
    still spread them with `**`, which raises TypeError only when the endpoint
    runs. Engines in isolation stayed green; the API returned 500.
'''
import asyncio
from datetime import date, timedelta

import pandas as pd
import pytest

from schemas.analytics import (
    CommercialSummaryResponse,
    ForecastResponse,
    PortfolioResponse,
    SegmentationResponse
)
from controllers import analytics as controllers


def _sales_frame() -> pd.DataFrame:
    '''
        Builds a normalized frame wide enough for every engine to produce rows.

        Returns:
            pd.DataFrame: Sales rows as ingest hands them over.
    '''
    start = date(2026, 1, 5)
    rows = []
    for index in range(120):
        day = start + timedelta(days = index * 3)
        rows.append({
            'date': pd.Timestamp(day),
            'order_id': f'F-{index // 2:04d}',
            'pos_id': f'PDV-{index % 8}',
            'pos_name': f'Tienda {index % 8}',
            'product_id': f'SKU-{index % 6}',
            'product_name': f'Producto {index % 6}',
            'category': ['Galletas', 'Lacteos'][index % 2],
            'channel': 'Tradicional',
            'region': 'Occidente',
            'city': 'La Paz',
            'zone': ['Sur', 'Centro'][index % 2],
            'seller': ['Ana', 'Juan'][index % 2],
            'latitude': -16.5 + (index % 8) * 0.01,
            'longitude': -68.1 - (index % 8) * 0.01,
            'quantity': 3 + index % 5,
            'unit_price': 8.5,
            'unit_cost': 6.0,
            'total_amount': round((3 + index % 5) * 8.5, 2),
        })
    return pd.DataFrame(rows)


@pytest.fixture(name = 'dataset')
def _dataset(monkeypatch) -> str:
    '''
        Serves the sales frame in place of the S3 round trip.

        Returns:
            str: The dataset id the controllers are called with.
    '''
    monkeypatch.setattr(
        controllers, 'get_dataset_metadata',
        lambda **_: {'file_s3_key': 'ingest/normalized/test.csv', 'status': 'validated'}
    )
    monkeypatch.setattr(controllers, 'load_dataframe_from_s3', lambda _: _sales_frame())
    return 'test-dataset-id'


def _call(controller, dataset_id: str, params: dict | None = None):
    '''
        Invokes a controller with the arguments every endpoint passes.

        Runs the coroutine with asyncio.run, the same way the TRADE tests do,
        so no extra test dependency is needed.

        Returns:
            Any: Whatever the controller returns.
    '''
    return asyncio.run(controller(
        dynamodb_resource = None,
        dataset_id = dataset_id,
        params = params or {},
        current_user = 'tester@bearsoft.com.bo',
        request = None
    ))


def test_commercial_summary_returns_a_full_response(dataset):
    '''The dashboard endpoint must build its response, blocks included.'''
    response = _call(controllers.commercial_summary_controller, dataset)

    assert isinstance(response, CommercialSummaryResponse)
    assert response.dataset_id == dataset
    assert response.kpis and response.monthly_trend
    assert response.growth.kpis
    assert response.concentration.clients.total_clients > 0
    assert response.efficiency.kpis
    assert response.margin.available is True


def test_portfolio_returns_a_full_response(dataset):
    '''Portfolio health must carry its KPIs and month-by-month movement.'''
    response = _call(controllers.portfolio_controller, dataset)

    assert isinstance(response, PortfolioResponse)
    assert response.dataset_id == dataset
    assert response.kpis and response.movement


def test_forecast_returns_a_full_response(dataset):
    '''The forecast endpoint must honour the requested method and horizon.'''
    response = _call(
        controllers.forecast_controller, dataset,
        {'method': 'linear', 'months_ahead': 3}
    )

    assert isinstance(response, ForecastResponse)
    assert response.dataset_id == dataset
    assert response.method == 'linear'
    assert response.months_ahead == 3
    assert response.series


def test_segmentation_returns_a_full_response(dataset):
    '''Segmentation must return the three tiers and the client rows.'''
    response = _call(controllers.segmentation_controller, dataset)

    assert isinstance(response, SegmentationResponse)
    assert response.dataset_id == dataset
    assert [tier.tier for tier in response.tiers] == ['HIGH', 'MEDIUM', 'LOW']
    assert response.clients
