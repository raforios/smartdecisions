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

from fastapi import HTTPException

from schemas.analytics import (
    AnalyticsError,
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


class _FakeTable: # pylint: disable=too-few-public-methods
    '''A DynamoDB table that applies the scan filter it is given.'''

    def __init__(self, items):
        self._items = items

    def scan(self, **kwargs):
        '''Filters the stored items the way DynamoDB would.'''
        condition = kwargs.get('FilterExpression')
        expression = condition.get_expression() if condition else None
        return {'Items': [item for item in self._items if _matches(item, expression)]}


def _matches(item, expression):
    '''
        Evaluates the boto3 condition tree against one item.

        Only the two operators this filter uses — equality and AND — because a
        fuller emulator would be more code than the thing under test.
    '''
    if expression is None:
        return True
    operator = expression['operator']
    if operator == 'AND':
        return all(_matches(item, part.get_expression())
                   for part in expression['values'])
    attribute, expected = expression['values']
    return item.get(attribute.name) == expected


class _FakeResource: # pylint: disable=too-few-public-methods
    '''Stands in for the DynamoDB resource.'''

    def __init__(self, items):
        self._items = items

    def Table(self, _name): # pylint: disable=invalid-name
        '''Mirrors the boto3 resource API.'''
        return _FakeTable(self._items)


def _run_item(owner: str) -> dict:
    '''
        A persisted analytics run.

        Args:
            owner (str): Email stamped as the owner.

        Returns:
            dict: The stored record.
    '''
    return {
        'id': 'run-1',
        'run_id': 'run-1',
        'dataset_id': 'ds-001',
        'owner_email': owner,
        'status': 'READY',
        'summary': {
            'total_pos_with_opportunities': 8,
            'total_opportunities': 24,
            'total_expected_value': 15300.5,
            'affinity_rules_evaluated': 120,
            'parameters': {'min_support': 0.02},
        },
        'opportunities': [],
        'created_at': '2026-08-10T12:00:00-04:00',
    }


def test_a_run_of_another_client_is_not_readable():
    '''
        The owner is part of the scan filter, so somebody else's run is
        indistinguishable from one that does not exist.

        Analytics is the module that carries the commercial reading of a
        client's sales — who their best points of sale are and what they are
        failing to sell. Reading another company's is worse than reading the
        raw file.
    '''
    resource = _FakeResource([_run_item('otra@empresa.com')])

    with pytest.raises(HTTPException) as failure:
        asyncio.run(controllers.get_results_controller(
            dynamodb_resource = resource,
            dataset_id = 'ds-001',
            request = None,
            current_user = 'yo@miempresa.com'
        ))

    assert AnalyticsError.RUN_NOT_FOUND.value in str(failure.value.detail)


def test_the_owner_reads_their_own_run():
    '''The filter must not get in the way of whoever owns the run.'''
    resource = _FakeResource([_run_item('yo@miempresa.com')])

    response = asyncio.run(controllers.get_results_controller(
        dynamodb_resource = resource,
        dataset_id = 'ds-001',
        request = None,
        current_user = 'yo@miempresa.com'
    ))

    assert response.dataset_id == 'ds-001'
    assert response.run_id == 'run-1'


class _RunsTable: # pylint: disable=too-few-public-methods
    '''A DynamoDB table that applies the owner filter of a scan.'''

    def __init__(self, items):
        self._items = items

    def scan(self, **kwargs):
        '''Returns the rows whose owner matches the filter.'''
        attribute, expected = kwargs['FilterExpression'].get_expression()['values']
        return {'Items': [item for item in self._items
                          if item.get(attribute.name) == expected]}


class _RunsResource: # pylint: disable=too-few-public-methods
    '''Stands in for the DynamoDB resource.'''

    def __init__(self, items):
        self._items = items

    def Table(self, _name): # pylint: disable=invalid-name
        '''Mirrors the boto3 resource API.'''
        return _RunsTable(self._items)


def _stored_run(owner: str, run_id: str, created_at: str) -> dict:
    '''
        A persisted run row.

        Args:
            owner (str): Owner email.
            run_id (str): Identifier.
            created_at (str): ISO timestamp.

        Returns:
            dict: The record as DynamoDB holds it.
    '''
    return {
        'id': run_id, 'run_id': run_id, 'dataset_id': 'ds-1',
        'owner_email': owner, 'status': 'completed',
        'summary': {'total_opportunities': 964,
                    'total_pos_with_opportunities': 260,
                    'total_expected_value': 15300.5},
        'created_at': created_at,
    }


def test_the_analysis_history_only_lists_your_own():
    '''
        The panel reads the first row as "your last analysis". Showing another
        client's would be worse than showing none.
    '''
    resource = _RunsResource([
        _stored_run('yo@miempresa.com', 'run-mine', '2026-09-01T10:00:00-04:00'),
        _stored_run('otra@empresa.com', 'run-theirs', '2026-09-03T10:00:00-04:00'),
    ])

    response = asyncio.run(controllers.list_runs_controller(
        dynamodb_resource = resource, request = None,
        current_user = 'yo@miempresa.com', limit = 20
    ))

    assert response.count == 1
    assert response.runs[0].run_id == 'run-mine'
    assert response.runs[0].total_opportunities == 964


def test_the_analysis_history_comes_back_newest_first():
    '''Order is part of the contract: the first row is "the last analysis".'''
    resource = _RunsResource([
        _stored_run('yo@miempresa.com', 'viejo', '2026-08-01T10:00:00-04:00'),
        _stored_run('yo@miempresa.com', 'nuevo', '2026-09-03T21:00:00-04:00'),
    ])

    response = asyncio.run(controllers.list_runs_controller(
        dynamodb_resource = resource, request = None,
        current_user = 'yo@miempresa.com', limit = 20
    ))

    assert [run.run_id for run in response.runs] == ['nuevo', 'viejo']
