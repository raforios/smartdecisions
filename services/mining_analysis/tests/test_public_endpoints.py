'''
    Smoke tests for the public mineral-report endpoints — reachable without a
    JWT, answering 200 with the expected payload shape.

    They run against DynamoDB (moto), which is what the deployment serves:
    the route resolves the resource through GET_DB_DEPENDENCY and hands it
    down, exactly as in production. The relational branch of the same reports
    is covered by `test_reports.py`.
'''
from datetime import date

import boto3
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from moto import mock_aws

from models.mining_analysis_dyb import MineralItem, MiningPriceItem
from routes.public_reports import router as public_reports_router
from services import prices_dyb, prices_store
from services.db_connection import GET_DB_DEPENDENCY
from services.mining_analysis import OFFICIAL_MINERALS

# Two days of tin, the pair the assertions below read: 21.0 then 22.0.
TIN_PRICES = ((date(2026, 4, 10), 21.0), (date(2026, 4, 11), 22.0))


@pytest.fixture(name = 'public_client')
def _public_client(monkeypatch):
    '''
        A client for the public router backed by a mocked DynamoDB holding the
        official catalogue and two tin quotations.

        Args:
            monkeypatch: Pins the store to the DynamoDB backend, whatever
                .env says, so the suite never depends on deployment config.

        Returns:
            TestClient: Ready to hit the public endpoints anonymously.
    '''
    monkeypatch.setattr(prices_store, 'BACKEND', prices_store.DYNAMODB_BACKEND)
    with mock_aws():
        resource = boto3.resource('dynamodb', region_name = 'us-east-1')
        resource.create_table(
            TableName = prices_dyb.MINERALS_TABLE,
            KeySchema = [{'AttributeName': 'mineral_id', 'KeyType': 'HASH'}],
            AttributeDefinitions = [{'AttributeName': 'mineral_id', 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
        resource.create_table(
            TableName = prices_dyb.PRICES_TABLE,
            KeySchema = [{'AttributeName': 'mineral_id', 'KeyType': 'HASH'},
                         {'AttributeName': 'date', 'KeyType': 'RANGE'}],
            AttributeDefinitions = [{'AttributeName': 'mineral_id', 'AttributeType': 'S'},
                                    {'AttributeName': 'date', 'AttributeType': 'S'}],
            BillingMode = 'PAY_PER_REQUEST'
        )
        for index, catalog in enumerate(OFFICIAL_MINERALS, start = 1):
            prices_dyb.put_mineral(resource, MineralItem(
                mineral_id = str(index), name = catalog['name'], unit = catalog['unit'],
                chemical_symbol = catalog['chemical_symbol'], quoted_in = catalog['quoted_in']
            ))
        # Keyed by symbol rather than searched: a bare next() inside this
        # generator fixture would raise StopIteration where pytest reads it.
        catalogue_ids = {catalog['chemical_symbol']: str(index)
                         for index, catalog in enumerate(OFFICIAL_MINERALS, start = 1)}
        tin_id = catalogue_ids['Sn']
        prices_dyb.put_prices_batch(resource, [
            MiningPriceItem(mineral_id = tin_id, date = day, price_low = price, price_high = price)
            for day, price in TIN_PRICES
        ])

        app = FastAPI()
        app.include_router(public_reports_router)
        app.dependency_overrides[GET_DB_DEPENDENCY] = lambda: resource
        try:
            yield TestClient(app)
        finally:
            app.dependency_overrides.clear()


def test_public_daily_returns_200_without_auth(public_client):
    '''Public daily endpoint must respond without an Authorization header.'''
    response = public_client.get('/v1/mining-analysis/public/reports/daily',
                                 params = {'date': '2026-04-11'})
    assert response.status_code == 200
    body = response.json()
    assert body['ref_date'] == '2026-04-11'
    estano = next(r for r in body['rows'] if r['mineral'] == 'Estaño')
    assert estano['price_low'] == 22.0
    assert estano['previous_price_low'] == 21.0
    # Two decimals, like every published percentage: the exact value is
    # 4.7619…, and what travels is what a reader would be shown.
    assert estano['change_pct'] == pytest.approx(4.76, abs = 1e-9)


def test_public_biweekly_returns_200_without_auth(public_client):
    '''Public biweekly endpoint must respond without an Authorization header.'''
    response = public_client.get('/v1/mining-analysis/public/reports/biweekly',
                                 params = {'year': 2026, 'month': 4, 'half': 1})
    assert response.status_code == 200
    body = response.json()
    assert body['year'] == 2026 and body['month'] == 4 and body['half'] == 1
    estano = next(r for r in body['rows'] if r['mineral'] == 'Estaño')
    assert estano['avg_price_low'] == pytest.approx(21.5)
    assert estano['sample_size'] == 2


def test_public_biweekly_history_returns_200_without_auth(public_client):
    '''The history endpoint must return at least the populated period.'''
    response = public_client.get(
        '/v1/mining-analysis/public/reports/biweekly/history')
    assert response.status_code == 200
    body = response.json()
    keys = [(p['year'], p['month'], p['half']) for p in body['periods']]
    assert (2026, 4, 1) in keys


def test_responses_carry_codes_and_no_prose(public_client):
    '''
        Every report answers with a stable code, never with a sentence.

        The backend returns data and codes; the wording belongs to the frontend
        and to the interpretation layer. A regression here is invisible until
        someone builds a screen on top of an English phrase.
    '''
    cases = (
        ('/v1/mining-analysis/public/reports/daily',
         {'date': '2026-04-11'}, 'DAILY_REPORT_GENERATED'),
        ('/v1/mining-analysis/public/reports/biweekly',
         {'year': 2026, 'month': 4, 'half': 1}, 'BIWEEKLY_REPORT_GENERATED'),
        ('/v1/mining-analysis/public/reports/biweekly/history',
         {'date_from': '2026-04-01', 'date_to': '2026-04-30'},
         'BIWEEKLY_HISTORY_GENERATED'),
    )

    for path, params, expected in cases:
        body = public_client.get(path, params = params).json()
        assert body['result'] == expected
        assert body['status'] == 'success'
        assert 'message' not in body
